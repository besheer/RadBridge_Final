"""Doctor viewer selection and short-lived, study-scoped Weasis delivery."""
import re
import secrets
import tempfile
from urllib.parse import quote
from xml.etree import ElementTree as ET

import pydicom
from flask import Blueprint, Response, abort, make_response, redirect, request, send_file
from itsdangerous import URLSafeTimedSerializer, BadData

VIEWERS = {'OHIF', 'WEASIS'}
MAX_AGE = 1200
ORTHANC_ID = re.compile(r'[a-fA-F0-9-]{36,45}')


def preference(m, profile):
    value = m.user_profile_settings(profile).get('image_viewer', 'OHIF')
    return value if isinstance(value, str) and value in VIEWERS else 'OHIF'


def save_preference(m, profile, value):
    if not isinstance(value, str) or value not in VIEWERS:
        abort(400)
    settings = m.user_profile_settings(profile)
    settings['image_viewer'] = value
    profile.settings_json = m.json.dumps(settings, separators=(',', ':'))


def register(m):
    bp = Blueprint('viewer_choice', __name__)

    def allowed(user, order):
        if not m.doctor_case_access_allowed(user, order):
            abort(403)
        permissions = user.role.permissions()
        if user.role.code.upper() != 'SUPER_ADMIN':
            if '*' not in permissions and 'reports.view' not in permissions:
                abort(403)
            if user.branch_id and user.branch_id != order.branch_id:
                abort(403)

    def orthanc(path, **kwargs):
        return m.requests.get(m.PACS_ORTHANC_URL.rstrip('/') + path,
                              auth=m._orthanc_auth(), allow_redirects=False,
                              timeout=(10, 60), **kwargs)

    def data(path):
        try:
            with orthanc(path) as response:
                if response.status_code != 200:
                    abort(502, description='Imaging service unavailable. / خدمة الصور غير متاحة.')
                return response.json()
        except m.requests.RequestException:
            abort(502, description='Imaging service unavailable. / خدمة الصور غير متاحة.')

    def checked_study(order):
        study_id = str(order.pacs_study_id or '')
        if not ORTHANC_ID.fullmatch(study_id):
            abort(409, description='No linked imaging study. / لا توجد دراسة صور مرتبطة.')
        ok, reason = m.pacs_demographic_gate(order)
        if not ok:
            abort(409, description='Imaging matching requires review. / مطابقة الصور تحتاج مراجعة.')
        detail = data('/studies/' + study_id)
        tags = detail.get('MainDicomTags') or {}
        patient = detail.get('PatientMainDicomTags') or {}
        uid = str(tags.get('StudyInstanceUID') or '')
        pid = str(order.patient.patient_id or '').strip()
        if (detail.get('ID') != study_id or not uid or not pid
                or str(patient.get('PatientID') or '').strip() != pid
                or (order.study_instance_uid and order.study_instance_uid != uid)
                or str(tags.get('AccessionNumber') or '').strip() != str(order.accession or '').strip()):
            abort(409, description='Study matching changed; return to RadBridge. / راجع مطابقة الحالة في RadBridge.')
        return detail

    def signer():
        return URLSafeTimedSerializer(m.app.secret_key, salt='radbridge-weasis-read-v1')

    def issue(user, order, detail):
        return signer().dumps({'purpose': 'WEASIS_READ', 'user': user.id, 'order': order.id,
            'study': order.pacs_study_id, 'uid': detail['MainDicomTags']['StudyInstanceUID'],
            'patient': order.patient.patient_id, 'nonce': secrets.token_urlsafe(12)})

    def authorize(token, order_id):
        try:
            payload = signer().loads(token, max_age=MAX_AGE)
        except BadData:
            abort(403)
        if not isinstance(payload, dict) or payload.get('purpose') != 'WEASIS_READ' or payload.get('order') != order_id:
            abort(403)
        user = m.db.session.get(m.User, payload.get('user'))
        order = m.db.session.get(m.Order, order_id)
        allowed(user, order)
        if payload.get('study') != order.pacs_study_id or payload.get('patient') != order.patient.patient_id:
            abort(403)
        detail = checked_study(order)
        if payload.get('uid') != detail['MainDicomTags']['StudyInstanceUID']:
            abort(403)
        return user, order, detail

    def protected(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def open_case(order):
        user = m.current_user()
        allowed(user, order)
        profile = m.UserProfile.query.filter_by(user_id=user.id).first()
        viewer = request.args.get('viewer') or preference(m, profile)
        if viewer not in VIEWERS:
            abort(400)
        if viewer == 'OHIF':
            url = m.ohif_url_for_order(order) if order.pacs_study_id else None
            if not url:
                abort(409, description='No linked imaging study. / لا توجد دراسة صور مرتبطة.')
            return protected(redirect(url))
        detail = checked_study(order)
        token = issue(user, order, detail)
        manifest = m.RIS_PUBLIC_URL + m.url_for('viewer_choice.manifest', order_id=order.id, token=token)
        launch = 'weasis://?'+quote('$dicom:get -w "'+manifest+'"', safe='')
        response = make_response(m.render_template('viewer_launch.html', order=order,
            launch_url=launch, preferred_viewer=preference(m, profile),
            save_token=preference_token()))
        return protected(response)

    def preference_token():
        from flask import session
        if not session.get('viewer_choice_csrf'):
            session['viewer_choice_csrf'] = secrets.token_urlsafe(32)
        return session['viewer_choice_csrf']

    @bp.get('/doctor/cases/<int:order_id>/viewers')
    @m.require_perm('reports.view')
    def choose(order_id):
        order = m.Order.query.get_or_404(order_id)
        user = m.current_user()
        allowed(user, order)
        profile = m.UserProfile.query.filter_by(user_id=user.id).first()
        return protected(make_response(m.render_template('viewer_choice.html', order=order,
            preferred_viewer=preference(m, profile), save_token=preference_token())))

    @bp.post('/doctor/viewer-preference')
    @m.require_perm('reports.view')
    def save():
        from flask import session
        if not m.doctor_workspace_user(m.current_user()):
            abort(403)
        csrf = request.form.get('csrf_token') or ''
        if not csrf or not secrets.compare_digest(csrf, session.get('viewer_choice_csrf', '')):
            abort(403)
        profile = m.get_user_profile()
        save_preference(m, profile, request.form.get('viewer'))
        m.audit('USER_IMAGE_VIEWER_SAVE', 'user_profile', profile.id or '', request.form['viewer'])
        m.db.session.commit()
        m.flash('تم حفظ عارض الصور الافتراضي. / Default image viewer saved.', 'success')
        order_id = request.form.get('order_id', type=int)
        return redirect(m.url_for('viewer_choice.choose', order_id=order_id) if order_id else m.url_for('my_profile'))

    @bp.get('/viewer/weasis/<int:order_id>/<token>/manifest.xml')
    def manifest(order_id, token):
        user, order, detail = authorize(token, order_id)
        instances = data('/studies/' + order.pacs_study_id + '/instances')
        if not isinstance(instances, list) or not instances or len(instances) > 20000:
            abort(409)
        root = ET.Element('manifest', xmlns='http://www.weasis.org/xsd/2.5')
        base = m.RIS_PUBLIC_URL + m.url_for('viewer_choice.manifest', order_id=order_id, token=token).rsplit('/', 1)[0]
        arc = ET.SubElement(root, 'arcQuery', arcId='1001', baseUrl=base,
                            requireOnlySOPInstanceUID='false', additionnalParameters='')
        patient = ET.SubElement(arc, 'Patient', {k: str(v) for k, v in (detail.get('PatientMainDicomTags') or {}).items()
            if k in {'PatientID', 'PatientName', 'PatientSex', 'PatientBirthDate'}})
        study = ET.SubElement(patient, 'Study', {k: str(v) for k, v in detail['MainDicomTags'].items()
            if k in {'StudyInstanceUID', 'StudyID', 'StudyDate', 'StudyTime', 'StudyDescription', 'AccessionNumber'}})
        series_nodes = {}
        for item in instances:
            instance_id = str(item.get('ID') or '')
            series_id = str(item.get('ParentSeries') or '')
            if not ORTHANC_ID.fullmatch(instance_id) or not ORTHANC_ID.fullmatch(series_id):
                abort(409)
            if series_id not in series_nodes:
                series = data('/series/' + series_id)
                if series.get('ParentStudy') != order.pacs_study_id:
                    abort(409)
                st = series.get('MainDicomTags') or {}
                if not st.get('SeriesInstanceUID'):
                    abort(409)
                series_nodes[series_id] = ET.SubElement(study, 'Series', {k: str(v) for k, v in st.items()
                    if k in {'SeriesInstanceUID', 'SeriesNumber', 'SeriesDescription', 'Modality'}})
            tags = item.get('MainDicomTags') or {}
            if not tags.get('SOPInstanceUID'):
                abort(409)
            ET.SubElement(series_nodes[series_id], 'Instance', SOPInstanceUID=str(tags['SOPInstanceUID']),
                InstanceNumber=str(tags.get('InstanceNumber') or '0'), DirectDownloadFile='/instances/'+instance_id+'.dcm')
        return protected(Response(ET.tostring(root, encoding='utf-8', xml_declaration=True), mimetype='application/xml'))

    @bp.get('/viewer/weasis/<int:order_id>/<token>/instances/<instance_id>.dcm')
    def instance(order_id, token, instance_id):
        user, order, detail = authorize(token, order_id)
        if not ORTHANC_ID.fullmatch(instance_id):
            abort(404)
        info = data('/instances/' + instance_id)
        series_id = str(info.get('ParentSeries') or '')
        if not ORTHANC_ID.fullmatch(series_id):
            abort(403)
        series = data('/series/' + series_id)
        if series.get('ParentStudy') != order.pacs_study_id:
            abort(403)
        stream = tempfile.TemporaryFile(mode='w+b')
        try:
            with orthanc('/instances/' + instance_id + '/file', stream=True) as upstream:
                if upstream.status_code != 200:
                    abort(502)
                size = 0
                for chunk in upstream.iter_content(1024*1024):
                    size += len(chunk)
                    if size > 512*1024*1024:
                        abort(413)
                    stream.write(chunk)
            stream.seek(0)
            from dicom_export_routes import HeaderReader
            ds = pydicom.dcmread(HeaderReader(stream, size), stop_before_pixels=True)
            if (str(getattr(ds, 'StudyInstanceUID', '')) != detail['MainDicomTags']['StudyInstanceUID']
                    or str(getattr(ds, 'PatientID', '')) != order.patient.patient_id
                    or str(getattr(ds, 'SOPInstanceUID', '')) != str((info.get('MainDicomTags') or {}).get('SOPInstanceUID') or '')):
                abort(409)
            m.db.session.expire_all()
            authorize(token, order_id)
            stream.seek(0)
            response = send_file(stream, mimetype='application/dicom', conditional=False, etag=False)
            response.call_on_close(stream.close)
            return protected(response)
        except Exception:
            stream.close()
            raise

    m.app.register_blueprint(bp)
    m.open_image_viewer_case = open_case
    m.image_viewer_preference = lambda profile: preference(m, profile)
    m.save_image_viewer_preference = lambda profile, value: save_preference(m, profile, value)
    return bp
