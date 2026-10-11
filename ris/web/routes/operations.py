"""Runtime-bound web.routes.operations; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0436(_rb):
    @_rb.app.route('/admin/dictionary',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_dictionary():
        if _rb.request.method=='POST':
            key=(_rb.request.form.get('key') or '').strip()
            row=_rb.DictionaryEntry.query.filter_by(key=key).first()
            if not row:
                row=_rb.DictionaryEntry(key=key);_rb.db.session.add(row)
            row.module=(_rb.request.form.get('module') or 'GLOBAL').upper()
            row.label_en=(_rb.request.form.get('label_en') or key).strip()
            row.label_ar=(_rb.request.form.get('label_ar') or '').strip()
            row.active=_rb.request.form.get('active')=='1'
            _rb.db.session.commit();return _rb.redirect(_rb.url_for('admin_dictionary'))
        q=(_rb.request.args.get('q') or '').strip()
        rows=_rb.DictionaryEntry.query
        if q:
            rows=rows.filter(_rb.or_(
                _rb.DictionaryEntry.key.ilike(f'%{q}%'),
                _rb.DictionaryEntry.label_en.ilike(f'%{q}%'),
                _rb.DictionaryEntry.label_ar.ilike(f'%{q}%'),
                _rb.DictionaryEntry.module.ilike(f'%{q}%')
            ))
        return _rb.render_template('admin_dictionary.html',rows=rows.order_by(_rb.DictionaryEntry.module,_rb.DictionaryEntry.key).all(),q=q)
    return admin_dictionary


def install_0441(_rb):
    @_rb.app.post('/admin/dictionary/<int:entry_id>/reset')
    @_rb.require_perm('users.view')
    def admin_dictionary_reset(entry_id):
        row=_rb.DictionaryEntry.query.get_or_404(entry_id)
        d=_rb.DEFAULT_UI_MAP.get(row.key)
        if not d:
            _rb.flash('No built-in default exists for this dictionary key.','warning')
            return _rb.redirect(_rb.url_for('admin_dictionary'))
        row.module=d['module'];row.label_en=d['en'];row.label_ar=d['ar'];row.active=True
        _rb.db.session.commit()
        _rb.flash('Dictionary entry reset to default.','success')
        return _rb.redirect(_rb.url_for('admin_dictionary'))
    return admin_dictionary_reset


def install_0443(_rb):
    @_rb.app.route('/admin/ribbon-designer',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_ribbon_designer():
        if _rb.request.method=='POST':
            key=(_rb.request.form.get('action_key') or '').strip()
            row=_rb.RibbonAction.query.filter_by(action_key=key).first()
            if not row:
                row=_rb.RibbonAction(action_key=key)
                _rb.db.session.add(row)
            row.label_en=(_rb.request.form.get('label_en') or key).strip()
            row.label_ar=(_rb.request.form.get('label_ar') or '').strip()
            row.icon=(_rb.request.form.get('icon') or '•').strip()
            row.route_name=(_rb.request.form.get('route_name') or '').strip()
            row.required_permission=(_rb.request.form.get('required_permission') or '').strip()
            row.context=(_rb.request.form.get('context') or 'GLOBAL').strip().upper()
            row.order_no=_rb.request.form.get('order_no',type=int) or 100
            row.active=_rb.request.form.get('active')=='1'
            _rb.db.session.commit()
            _rb.flash('Ribbon action saved.','success')
            return _rb.redirect(_rb.url_for('admin_ribbon_designer'))

        rows=_rb.RibbonAction.query.order_by(
            _rb.RibbonAction.context,_rb.RibbonAction.order_no
        ).all()
        return _rb.render_template('admin_ribbon_designer.html',rows=rows)
    return admin_ribbon_designer


def install_0462(_rb):
    @_rb.app.route('/admin/referrers', methods=['GET','POST'])
    @_rb.require_perm('referrers.manage')
    def admin_referrers():
        if _rb.request.method=='POST':
            r=_rb.ReferringDoctor(
                code=_rb.request.form['code'].strip().upper(),
                name=_rb.request.form['name'].strip(),
                specialty=_rb.request.form.get('specialty','').strip(),
                phone=_rb.request.form.get('phone','').strip(),
                organization=_rb.request.form.get('organization','').strip(),
                active=True
            )
            _rb.db.session.add(r); _rb.audit('REFERRER_CREATE','referring_doctor','',r.code); _rb.db.session.commit()
            _rb.flash('Referring doctor added.','success')
        return _rb.render_template('admin_referrers.html',rows=_rb.ReferringDoctor.query.order_by(_rb.ReferringDoctor.name).all())
    return admin_referrers


def install_0466(_rb):
    @_rb.app.route('/admin/import-export', methods=['GET','POST'])
    @_rb.login_required
    def admin_import_export():
        if _rb.request.method == 'GET':
            if not (
                _rb.has_perm('*')
                or _rb.has_perm('import.manage')
                or _rb.has_perm('export.view')
            ):
                _rb.abort(403)

        if _rb.request.method=='POST':
            if not _rb.has_perm('import.manage'): _rb.abort(403)
            entity=_rb.request.form.get('entity')
            f=_rb.request.files.get('file')
            if not f: _rb.flash('Choose a CSV file.','danger'); return _rb.redirect(_rb.url_for('admin_import_export'))
            text_data=f.stream.read().decode('utf-8-sig',errors='replace')
            reader=_rb.csv.DictReader(_rb.io.StringIO(text_data))
            inserted=updated=errors=0
            for row in reader:
                try:
                    if entity=='procedures':
                        code=(row.get('code') or '').strip().upper()
                        if not code: raise ValueError('code required')
                        p=_rb.Procedure.query.filter_by(code=code).first()
                        if not p:
                            p=_rb.Procedure(code=code); _rb.db.session.add(p); inserted+=1
                        else: updated+=1
                        p.name=(row.get('name') or code).strip()
                        p.name_ar=(row.get('name_ar') or '').strip()
                        p.category=(row.get('category') or '').strip()
                        p.modality=(row.get('modality') or 'OT').strip().upper()
                        p.body_part=(row.get('body_part') or '').strip()
                        p.base_price=float(row.get('base_price') or 0)
                        p.duration_min=int(float(row.get('duration_min') or 20))
                        p.contrast=str(row.get('contrast') or '').strip().lower() in ('1','true','yes','y')
                        p.active=True
                    elif entity=='contracts':
                        code=(row.get('code') or '').strip().upper()
                        if not code: raise ValueError('code required')
                        c=_rb.Contract.query.filter_by(code=code).first()
                        if not c:
                            c=_rb.Contract(code=code); _rb.db.session.add(c); inserted+=1
                        else: updated+=1
                        c.name=(row.get('name') or code).strip()
                        c.patient_share_percent=float(row.get('patient_share_percent') or 0)
                        c.discount_percent=float(row.get('discount_percent') or 0)
                        c.approval_required=str(row.get('approval_required') or '').strip().lower() in ('1','true','yes','y')
                        c.active=True
                    elif entity=='consumables':
                        code=(row.get('code') or '').strip().upper()
                        if not code: raise ValueError('code required')
                        c=_rb.Consumable.query.filter_by(code=code).first()
                        if not c:
                            c=_rb.Consumable(code=code); _rb.db.session.add(c); inserted+=1
                        else: updated+=1
                        c.name=(row.get('name') or code).strip()
                        c.unit=(row.get('unit') or 'unit').strip()
                        c.stock_qty=float(row.get('stock_qty') or 0)
                        c.reorder_level=float(row.get('reorder_level') or 0)
                        c.unit_cost=float(row.get('unit_cost') or 0)
                        c.active=True
                    else:
                        raise ValueError('unsupported entity')
                except Exception:
                    errors+=1
            _rb.db.session.commit(); _rb.audit('IMPORT',entity,'',f'inserted={inserted} updated={updated} errors={errors}')
            _rb.db.session.commit(); _rb.flash(f'Import complete: {inserted} inserted, {updated} updated, {errors} errors.','success')
            return _rb.redirect(_rb.url_for('admin_import_export'))
        return _rb.render_template('admin_import_export.html')
    return admin_import_export


def install_0467(_rb):
    @_rb.app.route('/admin/export/<entity>.csv')
    @_rb.login_required
    def admin_export_entity(entity):
        if not _rb.has_perm('export.view') and not _rb.has_perm('*'): _rb.abort(403)
        s=_rb.io.StringIO(); w=_rb.csv.writer(s)
        if entity=='procedures':
            w.writerow(['code','name','name_ar','category','modality','body_part','base_price','duration_min','contrast'])
            for p in _rb.Procedure.query.order_by(_rb.Procedure.modality,_rb.Procedure.name):
                w.writerow([p.code,p.name,p.name_ar,p.category,p.modality,p.body_part,p.base_price,p.duration_min,int(bool(p.contrast))])
        elif entity=='contracts':
            w.writerow(['code','name','patient_share_percent','discount_percent','approval_required'])
            for c in _rb.Contract.query.order_by(_rb.Contract.name):
                w.writerow([c.code,c.name,c.patient_share_percent,c.discount_percent,int(bool(c.approval_required))])
        elif entity=='consumables':
            w.writerow(['code','name','unit','stock_qty','reorder_level','unit_cost'])
            for c in _rb.Consumable.query.order_by(_rb.Consumable.name):
                w.writerow([c.code,c.name,c.unit,c.stock_qty,c.reorder_level,c.unit_cost])
        elif entity=='devices':
            w.writerow(['branch','name','modality','ae_title','ip','port','room','priority','active'])
            for d in _rb.Device.query.order_by(_rb.Device.branch_id,_rb.Device.modality,_rb.Device.priority):
                w.writerow([d.branch.name if d.branch else '',d.name,d.modality,d.ae_title,d.ip,d.port,d.room,d.priority,int(bool(d.active))])
        else:
            _rb.abort(404)
        return _rb.send_file(_rb.io.BytesIO(s.getvalue().encode('utf-8-sig')),as_attachment=True,
            download_name=f'{entity}.csv',mimetype='text/csv; charset=utf-8')
    return admin_export_entity


def install_0478(_rb):
    @_rb.app.route('/admin/company',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_company():
        profile=_rb.get_company_profile()
        if _rb.request.method=='POST':
            for key in ['name_en','name_ar','address_en','address_ar','phone','mobile','email','website']:
                setattr(profile,key,(_rb.request.form.get(key) or '').strip())
            f=_rb.request.files.get('logo')
            if f and f.filename:
                ext=_rb.Path(f.filename).suffix.lower()
                if ext not in ('.png','.jpg','.jpeg','.webp'):
                    _rb.flash('Logo must be PNG/JPG/WEBP.','danger');return _rb.redirect(_rb.url_for('admin_company'))
                folder=_rb.Path(_rb.ATTACHMENT_DIR)/'company';folder.mkdir(parents=True,exist_ok=True)
                path=folder/('logo'+ext);f.save(path);profile.logo_path=str(path)
            _rb.audit('COMPANY_PROFILE_UPDATE','company_profile',profile.id,'Branding updated');_rb.db.session.commit()
            _rb.flash('Company branding saved.','success');return _rb.redirect(_rb.url_for('admin_company'))
        return _rb.render_template('admin_company.html',profile=profile)
    return admin_company


def install_0480(_rb):
    @_rb.app.route('/admin/sticker-templates',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_sticker_templates():
        t=_rb.get_default_sticker_template()
        if _rb.request.method=='POST':
            t.name=(_rb.request.form.get('name') or t.name).strip();t.width_mm=float(_rb.request.form.get('width_mm') or t.width_mm);t.height_mm=float(_rb.request.form.get('height_mm') or t.height_mm)
            t.bilingual=_rb.request.form.get('bilingual')=='1';t.show_logo=_rb.request.form.get('show_logo')=='1';t.show_qr=_rb.request.form.get('show_qr')=='1';t.show_barcode=_rb.request.form.get('show_barcode')=='1'
            fields=[x for x in _rb.request.form.getlist('fields') if x in _rb.DEFAULT_STICKER_LABELS];t.fields_json=_rb.json.dumps(fields or _rb.DEFAULT_STICKER_FIELDS)
            labels={}
            for key in fields or _rb.DEFAULT_STICKER_FIELDS:
                labels[key]={'en':(_rb.request.form.get('label_en_'+key) or _rb.DEFAULT_STICKER_LABELS[key]['en']).strip(),
                             'ar':(_rb.request.form.get('label_ar_'+key) or _rb.DEFAULT_STICKER_LABELS[key]['ar']).strip()}
            t.labels_json=_rb.json.dumps(labels,ensure_ascii=False);_rb.audit('STICKER_TEMPLATE_UPDATE','sticker_template',t.id,'Sticker design updated');_rb.db.session.commit()
            _rb.flash('Sticker template saved.','success');return _rb.redirect(_rb.url_for('admin_sticker_templates'))
        return _rb.render_template('admin_sticker_templates.html',template=t,fields=_rb._sticker_fields(t),labels=_rb._sticker_labels(t))
    return admin_sticker_templates


def install_0547(_rb):
    @_rb.app.route('/admin')
    @_rb.app.route('/admin/')
    @_rb.login_required
    def admin_home():
        admin_perms = (
            'users.view',
            'users.manage',
            'roles.manage',
            'branches.manage',
            'devices.manage',
            'procedures.view',
            'contracts.manage',
            'inventory.manage',
            'audit.view',
            'backup.view',
            'assignment.manage',
            'pacs.discovery.view',
            'pacs.destinations.manage',
            'pacs.archive.manage',
            'financial.view',
            'storage.targets.view',
            'storage.cloud.view',
            'analytics.executive.view',
        )
        if not _rb.has_perm('*') and not any(_rb.has_perm(p) for p in admin_perms):
            _rb.abort(403)

        from admin_control_center import visible_sections
        sections = visible_sections(_rb.has_perm, _rb.url_for, _rb.app.view_functions)
        return _rb.render_template('admin.html', sections=sections)
    return admin_home


def install_0548(_rb):
    @_rb.app.route('/admin/users',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_users():
        from user_access_policy import CONTACT_FIELDS,contacts,parse_contacts,save_contacts,require_manage_target
        if _rb.request.method=='POST':
            if not (_rb.has_perm('*') or _rb.has_perm('users.manage')): _rb.abort(403)
            try:data=parse_contacts(_rb.request.form)
            except ValueError as exc:_rb.flash(str(exc),'danger');return _rb.redirect(_rb.url_for('admin_users'))
            role=_rb.Role.query.get_or_404(_rb.request.form.get('role_id',type=int))
            require_manage_target(role=role)
            from clinical_scope import parse_form,save as save_clinical_scope
            try:scope=parse_form(_rb._reporting_support_sys.modules[_rb.__name__],_rb.request.form,role)
            except ValueError as exc:_rb.flash(str(exc),'danger');return _rb.redirect(_rb.url_for('admin_users'))
            username=_rb.request.form['username'].strip()
            password=_rb.request.form.get('password','')
            if _rb.User.query.filter_by(username=username).first():
                _rb.flash('Username already exists.','danger'); return _rb.redirect(_rb.url_for('admin_users'))
            if len(password)<10:
                _rb.flash('Temporary password must be at least 10 characters.','danger'); return _rb.redirect(_rb.url_for('admin_users'))
            u=_rb.User(username=username,full_name=_rb.request.form['full_name'].strip(),
                   password_hash=_rb.generate_password_hash(password),
                   role_id=int(_rb.request.form['role_id']),branch_id=(int(_rb.request.form['branch_id']) if _rb.request.form.get('branch_id') else None),
                   active=True,must_change_password=True)
            _rb.db.session.add(u); _rb.db.session.flush(); save_contacts(u,data,_rb.request.form); save_clinical_scope(_rb._reporting_support_sys.modules[_rb.__name__],u,scope); _rb.audit('USER_CONTACTS_SAVE','user',u.id,'Contact fields updated'); _rb.audit('USER_CREATE','user','',u.username); _rb.db.session.commit(); _rb.flash('User created. Temporary password must be changed at first login.','success')
        return _rb.render_template('admin_users.html',users=_rb.User.query.order_by(_rb.User.username).all(),roles=_rb.Role.query.order_by(_rb.Role.name).all(),branches=_rb.Branch.query.order_by(_rb.Branch.name).all(),contact_fields=CONTACT_FIELDS,user_contacts=contacts,user_profiles={x.user_id:x for x in _rb.UserProfile.query.all()})
    return admin_users


def install_0549(_rb):
    @_rb.app.post('/admin/users/<int:user_id>/toggle')
    @_rb.require_perm('users.manage')
    def admin_user_toggle(user_id):
        u=_rb.User.query.get_or_404(user_id)
        from user_access_policy import require_manage_target
        require_manage_target(user=u)
        if u.id==_rb.current_user().id and u.active:
            _rb.flash('You cannot disable your own account.','danger'); return _rb.redirect(_rb.url_for('admin_users'))
        u.active=not u.active; _rb.audit('USER_TOGGLE','user',u.id,str(u.active)); _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('admin_users'))
    return admin_user_toggle


def install_0550(_rb):
    @_rb.app.post('/admin/users/<int:user_id>/edit')
    @_rb.require_perm('users.manage')
    def admin_user_edit(user_id):
        u=_rb.User.query.get_or_404(user_id)
        from user_access_policy import require_manage_target
        require_manage_target(user=u)
        from user_access_policy import parse_contacts,save_contacts,contacts
        try:data=parse_contacts(_rb.request.form,contacts(u))
        except ValueError as exc:_rb.flash(str(exc),'danger');return _rb.redirect(_rb.url_for('admin_users'))
        role=_rb.Role.query.get_or_404(_rb.request.form.get('role_id',type=int))
        require_manage_target(role=role)
        if u.id==_rb.current_user().id and (_rb.request.form.get('active')!='1' or (u.role and u.role.code=='SUPER_ADMIN' and role.code!='SUPER_ADMIN')):
            _rb.flash('Cannot disable or demote your own administrator session.','danger');return _rb.redirect(_rb.url_for('admin_users'))
        old_role=u.role.code if u.role else ''
        u.full_name=_rb.request.form.get('full_name',u.full_name).strip() or u.full_name
        u.role_id=int(_rb.request.form['role_id'])
        u.branch_id=int(_rb.request.form['branch_id']) if _rb.request.form.get('branch_id') else None
        u.active=_rb.request.form.get('active')=='1'
        save_contacts(u,data,_rb.request.form)
        from clinical_scope import CLINICAL_ROLES,save as save_clinical_scope
        if role.code.upper() not in CLINICAL_ROLES:save_clinical_scope(_rb._reporting_support_sys.modules[_rb.__name__],u,None)
        _rb.audit('USER_CONTACTS_SAVE','user',u.id,'Contact fields updated')
        _rb.audit('USER_EDIT','user',u.id,f'role {old_role}->{_rb.Role.query.get(u.role_id).code if u.role_id else ""}; active={u.active}')
        _rb.db.session.commit(); _rb.flash('User updated.','success')
        return _rb.redirect(_rb.url_for('admin_users'))
    return admin_user_edit


def install_0557(_rb):
    @_rb.app.route('/admin/branches/<int:branch_id>/edit',methods=['GET','POST'])
    @_rb.require_perm('branches.manage')
    def admin_branch_edit(branch_id):
        b=_rb.Branch.query.get_or_404(branch_id)
        if _rb.request.method=='POST':
            import re
            code=(_rb.request.form.get('code') or '').strip().upper();name=(_rb.request.form.get('name') or '').strip()
            if not re.fullmatch(r'[A-Z0-9_-]{1,20}',code) or not name or len(name)>120:
                _rb.flash('Valid branch code and name are required.','danger');return _rb.redirect(_rb.url_for('admin_branch_edit',branch_id=b.id))
            if _rb.Branch.query.filter(_rb.Branch.code==code,_rb.Branch.id!=b.id).first():
                _rb.flash('Branch code already exists.','danger');return _rb.redirect(_rb.url_for('admin_branch_edit',branch_id=b.id))
            b.code=code;b.name=name;b.active=_rb.request.form.get('active')=='1'
            b.reception_collection_enabled=_rb.request.form.get('reception_collection_enabled')=='1'
            _rb.audit('BRANCH_EDIT','branch',b.id,'code='+code+'; active='+str(b.active))
            _rb.db.session.commit();_rb.flash('Branch saved. / تم حفظ الفرع.','success');return _rb.redirect(_rb.url_for('admin_branches'))
        return _rb.render_template('admin_branch_edit.html',branch=b)
    return admin_branch_edit


def install_0558(_rb):
    @_rb.app.route('/admin/devices',methods=['GET','POST'])
    @_rb.require_perm('devices.manage')
    def admin_devices():
        if _rb.request.method=='POST':
            d=_rb.Device(branch_id=int(_rb.request.form['branch_id']),name=_rb.request.form['name'].strip(),modality=_rb.request.form['modality'],
                     ae_title=_rb.request.form['ae_title'].strip().upper(),ip=_rb.request.form.get('ip','').strip(),
                     port=int(_rb.request.form.get('port') or 104),room=_rb.request.form.get('room','').strip(),
                     priority=int(_rb.request.form.get('priority') or 100),active=True)
            _rb.db.session.add(d); _rb.audit('DEVICE_CREATE','device','',f'{d.name} {d.ae_title}'); _rb.db.session.commit(); _rb.flash('Device added.','success')
        return _rb.render_template('admin_devices.html',devices=_rb.Device.query.order_by(_rb.Device.branch_id,_rb.Device.modality,_rb.Device.priority).all(),branches=_rb.Branch.query.filter_by(active=True).all())
    return admin_devices


def install_0575(_rb):
    @_rb.app.route('/admin/audit')
    @_rb.require_perm('audit.view')
    def admin_audit():
        action=(_rb.request.args.get('action') or '').strip()[:100]
        username=(_rb.request.args.get('username') or '').strip()[:80]
        ip=(_rb.request.args.get('ip') or '').strip()[:80]
        entity=(_rb.request.args.get('entity') or '').strip()[:80]
        q=_rb.AuditLog.query
        if action:q=q.filter(_rb.AuditLog.action.ilike(f'%{action}%'))
        if username:q=q.filter(_rb.AuditLog.username.ilike(f'%{username}%'))
        if ip:q=q.filter(_rb.AuditLog.ip.ilike(f'%{ip}%'))
        if entity:q=q.filter(_rb.AuditLog.entity.ilike(f'%{entity}%'))
        rows=q.order_by(_rb.AuditLog.id.desc()).limit(1000).all()
        since=_rb.datetime.utcnow()-_rb.timedelta(hours=24)
        failed_24h=_rb.AuditLog.query.filter(_rb.AuditLog.action=='LOGIN_FAILED',_rb.AuditLog.created_at>=since).count()
        successful_24h=_rb.AuditLog.query.filter(_rb.AuditLog.action=='LOGIN',_rb.AuditLog.created_at>=since).count()
        return _rb.render_template('admin_audit.html',rows=rows,action=action,username=username,ip=ip,entity=entity,
            failed_24h=failed_24h,successful_24h=successful_24h,
            cancellation_count=_rb.AuditLog.query.filter(_rb.AuditLog.action.in_([
                'APPOINTMENT_CANCELLED_ADMIN','ORDER_CANCELLED_ADMIN','ORDER_REFERRAL_REMOVED'])).count())
    return admin_audit


def install_0596(_rb):
    @_rb.app.get('/admin/cancellation-center/preview')
    @_rb.require_perm('data.cancel.case')
    def granular_delete_preview_home():
        return _rb.render_template(
            'admin_cancellation_preview.html'
        )
    return granular_delete_preview_home


def install_0636(_rb):
    @_rb.app.get('/admin/data-deletion-center')
    @_rb.require_perm('*')
    def admin_data_deletion_center():
        term=(_rb.request.args.get('q') or '').strip()
        orders,appointments=_rb.cancellation_search_rows(term)
        return _rb.render_template(
            'admin_data_deletion_center.html',
            q=term,
            orders=orders,
            appointments=appointments,
        )
    return admin_data_deletion_center


def install_0637(_rb):
    @_rb.app.get('/admin/cancellation-center')
    @_rb.require_perm('data.cancel.case')
    def admin_cancellation_center():
        term=(_rb.request.args.get('q') or '').strip();orders,appointments=_rb.cancellation_search_rows(term)
        return _rb.render_template('admin_cancellation_center.html',q=term,orders=orders,appointments=appointments)
    return admin_cancellation_center


def install_0641(_rb):
    @_rb.app.route('/admin/roles',methods=['GET','POST'])
    @_rb.require_perm('roles.manage')
    def admin_roles():
        if _rb.request.method=='POST':
            role=_rb.Role.query.get_or_404(int(_rb.request.form['role_id']))
            from user_access_policy import NO_REPORT_EDIT,require_manage_target
            require_manage_target(role=role)
            proposed=_rb.request.form.getlist('permissions')
            actor=_rb.current_user()
            if actor.role.code!='SUPER_ADMIN' and not set(proposed).issubset(set(actor.role.permissions())):_rb.abort(403)
            if role.code in NO_REPORT_EDIT and ('reports.edit' in proposed or '*' in proposed):
                _rb.flash('This department must not receive report editing permission.','danger');return _rb.redirect(_rb.url_for('admin_roles',role=role.id))
            role.permissions_json=_rb.json.dumps(proposed)
            _rb.audit('ROLE_PERMISSIONS_EDIT','role',role.id,role.code)
            _rb.db.session.commit(); _rb.flash('Role permissions updated.','success')
            return _rb.redirect(_rb.url_for('admin_roles',role=role.id))
        roles=_rb.Role.query.order_by(_rb.Role.name).all()
        selected=_rb.Role.query.get(_rb.request.args.get('role',type=int)) if _rb.request.args.get('role') else (roles[0] if roles else None)
        from user_access_policy import permission_catalog
        return _rb.render_template('admin_roles.html',roles=roles,selected=selected,all_permissions=permission_catalog())
    return admin_roles


def install_0642(_rb):
    @_rb.app.get('/admin/access-review')
    @_rb.require_perm('roles.manage')
    def admin_access_review():
        from user_access_policy import route_catalog,page_access
        roles=_rb.Role.query.order_by(_rb.Role.name).all()
        selected=_rb.Role.query.get_or_404(_rb.request.args.get('role',type=int)) if _rb.request.args.get('role') else roles[0]
        rows=route_catalog()
        sections=sorted({row['section'] for row in rows})
        section=_rb.request.args.get('section','')
        if section:rows=[row for row in rows if row['section']==section]
        return _rb.render_template('admin_access_review.html',roles=roles,selected=selected,rows=rows,page_access=page_access,sections=sections,section=section)
    return admin_access_review


def install_0643(_rb):
    @_rb.app.route('/admin/branches',methods=['GET','POST'])
    @_rb.require_perm('branches.manage')
    def admin_branches():
        if _rb.request.method=='POST' and _rb.request.form.get('action')=='collection_policy':
            b=_rb.Branch.query.filter_by(id=_rb.request.form.get('branch_id',type=int)).with_for_update().first_or_404()
            b.reception_collection_enabled=_rb.request.form.get('reception_collection_enabled')=='1'
            _rb.audit('BRANCH_RECEPTION_COLLECTION','branch',b.id,'enabled='+str(b.reception_collection_enabled))
            _rb.db.session.commit()
            _rb.flash('Reception collection policy saved. / تم حفظ إعداد تحصيل الاستقبال.','success')
            return _rb.redirect(_rb.url_for('admin_branches'))
        if _rb.request.method=='POST':
            b=_rb.Branch(code=_rb.request.form['code'].strip().upper(),name=_rb.request.form['name'].strip(),active=True,reception_collection_enabled=_rb.request.form.get('reception_collection_enabled')=='1')
            _rb.db.session.add(b); _rb.audit('BRANCH_CREATE','branch','',b.code+'; reception_collection='+str(b.reception_collection_enabled)); _rb.db.session.commit(); _rb.flash('Branch added.','success')
        return _rb.render_template('admin_branches.html',branches=_rb.Branch.query.order_by(_rb.Branch.name).all())
    return admin_branches


def install_0648(_rb):
    @_rb.app.route('/admin/field-rules',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_field_rules():
        if _rb.request.method=='POST':
            row=_rb.FieldRule.query.get_or_404(_rb.request.form.get('rule_id',type=int))
            dtype=(_rb.request.form.get('data_type') or 'ANY').upper()
            required=_rb.request.form.get('required')=='1';visible=_rb.request.form.get('visible')=='1'
            lengths=[_rb.request.form.get(k,type=int) for k in ('min_length','max_length','exact_length')]
            if dtype not in ('ANY','NUMBERS','LETTERS','ALPHANUM') or (required and not visible) or any(v is not None and v<0 for v in lengths) or (lengths[0] is not None and lengths[1] is not None and lengths[0]>lengths[1]):
                _rb.flash('Invalid rule: a required field must be visible; lengths must be consistent.','danger')
                return _rb.redirect(_rb.url_for('admin_field_rules'))
            if row.field_key=='patient.name' and (not required or not visible):
                _rb.flash('Patient identity name must remain visible and required.','danger')
                return _rb.redirect(_rb.url_for('admin_field_rules'))
            _rb.audit('REGISTRATION_FIELD_RULE_UPDATE','field_rule',row.id,f'field={row.field_key};required={required};visible={visible};type={dtype}')
            row.data_type=dtype
            row.min_length=_rb.request.form.get('min_length',type=int); row.max_length=_rb.request.form.get('max_length',type=int)
            row.exact_length=_rb.request.form.get('exact_length',type=int); row.required=_rb.request.form.get('required')=='1'
            row.visible=_rb.request.form.get('visible')=='1'; row.updated_by=_rb.current_user().id
            _rb.db.session.commit(); return _rb.redirect(_rb.url_for('admin_field_rules'))
        return _rb.render_template('admin_field_rules.html',rows=_rb.FieldRule.query.order_by(_rb.FieldRule.field_key).all())
    return admin_field_rules


def install_0651(_rb):
    @_rb.app.route('/admin/company-legal',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_company_legal():
        bid=_rb.request.args.get('branch_id',type=int) or _rb.request.form.get('branch_id',type=int)
        branch=_rb.Branch.query.get(bid) if bid else _rb.Branch.query.order_by(_rb.Branch.id).first()
        row=_rb.CompanyLegalProfile.query.filter_by(branch_id=branch.id).first() if branch else None
        if _rb.request.method=='POST' and branch:
            if not row: row=_rb.CompanyLegalProfile(branch_id=branch.id); _rb.db.session.add(row)
            for f in ['legal_name','commercial_register','tax_card','tax_number','phone1','phone2','email','website','address','receipt_note_ar','receipt_note_en']:
                setattr(row,f,(_rb.request.form.get(f) or '').strip())
            _rb.db.session.commit(); return _rb.redirect(_rb.url_for('admin_company_legal',branch_id=branch.id))
        return _rb.render_template('admin_company_legal.html',row=row,branch=branch,branches=_rb.Branch.query.order_by(_rb.Branch.name).all())
    return admin_company_legal


def install_0680(_rb):
    @_rb.app.route('/admin/qa-control')
    @_rb.require_perm('users.view')
    def admin_qa_control():
        runs=_rb.QARun.query.order_by(_rb.QARun.id.desc()).limit(30).all()

        latest=runs[0] if runs else None

        failed=[]
        if latest:
            failed=_rb.QATestResult.query.filter_by(
                run_id=latest.id,
                status='FAIL'
            ).order_by(
                _rb.QATestResult.severity.desc(),
                _rb.QATestResult.id
            ).all()

        return _rb.render_template(
            'admin_qa_control.html',
            runs=runs,
            latest=latest,
            failed=failed,
            configured=bool(_rb.QA_N8N_RUN_WEBHOOK)
        )
    return admin_qa_control


def install_0681(_rb):
    @_rb.app.post('/admin/qa-control/run')
    @_rb.require_perm('users.view')
    def admin_qa_control_run():
        run_type=(_rb.request.form.get('run_type') or 'FULL').strip().upper()

        allowed={
            'FULL',
            'REGISTRATION',
            'APPROVAL',
            'PACS',
            'ASSIGNMENT',
            'OPEN_POOL',
            'OFFER',
            'DOCTOR',
            'COORDINATOR',
            'OHIF',
            'IMAGING_AI',
            'REPORTING',
            'SIGNATURE'
        }

        if run_type not in allowed:
            run_type='FULL'

        row=_rb.QARun(
            run_type=run_type,
            status='STARTING',
            release_name='v5.35',
            environment='PRODUCTION',
            started_by=_rb.current_user().id
        )

        _rb.db.session.add(row)
        _rb.db.session.commit()

        payload={
            'qa_run_id':row.id,
            'run_type':run_type,
            'callback_url':_rb.request.host_url.rstrip('/')+'/api/qa/callback',
            'callback_token':_rb.QA_CALLBACK_TOKEN
        }

        result,error=_rb.qa_n8n_call(
            _rb.QA_N8N_RUN_WEBHOOK,
            payload,
            timeout=20
        )

        if error:
            row.status='FAILED_TO_START'
            row.error_text=error
            row.finished_at=_rb.datetime.utcnow()
            _rb.db.session.commit()

            _rb.flash('QA workflow failed to start: '+error,'danger')
            return _rb.redirect(_rb.url_for('admin_qa_control'))

        row.status='RUNNING'

        if isinstance(result,dict):
            row.external_execution_id=str(
                result.get('execution_id')
                or result.get('executionId')
                or result.get('id')
                or ''
            )

        _rb.db.session.commit()

        _rb.audit(
            'QA_RUN_START',
            'qa_run',
            row.id,
            'type=%s' % run_type
        )
        _rb.db.session.commit()

        _rb.flash('QA run started.','success')
        return _rb.redirect(_rb.url_for('admin_qa_control'))
    return admin_qa_control_run


def install_0682(_rb):
    @_rb.app.post('/admin/qa-control/retry-failed')
    @_rb.require_perm('users.view')
    def admin_qa_retry_failed():
        run_id=_rb.request.form.get('run_id',type=int)

        row=_rb.QARun.query.get_or_404(run_id)

        failed=_rb.QATestResult.query.filter_by(
            run_id=row.id,
            status='FAIL'
        ).all()

        keys=[x.test_key for x in failed]

        if not keys:
            _rb.flash('No failed tests to retry.','info')
            return _rb.redirect(_rb.url_for('admin_qa_control'))

        payload={
            'qa_run_id':row.id,
            'tests':keys,
            'callback_url':_rb.request.host_url.rstrip('/')+'/api/qa/callback',
            'callback_token':_rb.QA_CALLBACK_TOKEN
        }

        result,error=_rb.qa_n8n_call(
            _rb.QA_N8N_RETRY_WEBHOOK or _rb.QA_N8N_RUN_WEBHOOK,
            payload,
            timeout=20
        )

        if error:
            _rb.flash('Retry failed to start: '+error,'danger')
        else:
            _rb.flash('Failed tests retry started.','success')

        return _rb.redirect(_rb.url_for('admin_qa_control'))
    return admin_qa_retry_failed


def install_0683(_rb):
    @_rb.app.post('/admin/qa-control/workflow/<action>')
    @_rb.require_perm('users.view')
    def admin_qa_workflow_control(action):
        action=(action or '').lower()

        urls={
            'enable':_rb.QA_N8N_ENABLE_WEBHOOK,
            'disable':_rb.QA_N8N_DISABLE_WEBHOOK
        }

        if action not in urls:
            _rb.abort(404)

        result,error=_rb.qa_n8n_call(
            urls[action],
            {
                'requested_by':_rb.current_user().id,
                'action':action
            }
        )

        if error:
            _rb.flash('Automation control failed: '+error,'danger')
        else:
            _rb.audit(
                'QA_AUTOMATION_'+action.upper(),
                'qa_control',
                0,
                action
            )
            _rb.db.session.commit()
            _rb.flash('QA automation '+action+' request sent.','success')

        return _rb.redirect(_rb.url_for('admin_qa_control'))
    return admin_qa_workflow_control


def install_0684(_rb):
    @_rb.app.post('/api/qa/callback')
    def api_qa_callback():
        expected=_rb.QA_CALLBACK_TOKEN

        supplied=(
            _rb.request.headers.get('X-RadBridge-QA-Token')
            or _rb.request.args.get('token')
            or ''
        )

        if expected and supplied != expected:
            return _rb.jsonify({
                'ok':False,
                'error':'QA_CALLBACK_UNAUTHORIZED'
            }),401

        data=_rb.request.get_json(silent=True) or {}

        run_id=data.get('qa_run_id')

        try:
            run_id=int(run_id)
        except Exception:
            return _rb.jsonify({
                'ok':False,
                'error':'INVALID_QA_RUN_ID'
            }),400

        row=_rb.QARun.query.get(run_id)

        if not row:
            return _rb.jsonify({
                'ok':False,
                'error':'QA_RUN_NOT_FOUND'
            }),404

        tests=data.get('tests') or []

        for item in tests:
            if not isinstance(item,dict):
                continue

            key=str(item.get('test') or item.get('test_key') or '').strip()

            if not key:
                continue

            tr=_rb.QATestResult.query.filter_by(
                run_id=row.id,
                test_key=key
            ).first()

            if not tr:
                tr=_rb.QATestResult(
                    run_id=row.id,
                    test_key=key
                )
                _rb.db.session.add(tr)

            tr.category=str(item.get('category') or '')
            tr.title=str(item.get('title') or key)
            tr.status=str(item.get('status') or 'UNKNOWN').upper()
            tr.severity=str(item.get('severity') or 'NORMAL').upper()
            tr.expected=str(item.get('expected') or '')
            tr.actual=str(item.get('actual') or '')
            tr.error_text=str(item.get('error') or '')
            tr.order_id=item.get('order_id') or None
            tr.details_json=_rb.json.dumps(
                item.get('details') or {},
                ensure_ascii=False,
                default=str
            )
            tr.finished_at=_rb.datetime.utcnow()

        _rb.db.session.flush()

        all_rows=_rb.QATestResult.query.filter_by(
            run_id=row.id
        ).all()

        row.total_tests=len(all_rows)
        row.passed_tests=sum(
            1 for x in all_rows if x.status=='PASS'
        )
        row.failed_tests=sum(
            1 for x in all_rows if x.status=='FAIL'
        )
        row.critical_tests=sum(
            1 for x in all_rows
            if x.status=='FAIL' and x.severity=='CRITICAL'
        )
        row.warning_tests=sum(
            1 for x in all_rows
            if x.status in ('WARN','WARNING')
        )

        callback_status=str(
            data.get('status')
            or ''
        ).upper()

        if callback_status in ('COMPLETE','COMPLETED','FINISHED'):
            row.status='COMPLETED'
            row.finished_at=_rb.datetime.utcnow()
        elif callback_status:
            row.status=callback_status
        else:
            row.status='RUNNING'

        row.summary_json=_rb.json.dumps(
            data.get('summary') or {},
            ensure_ascii=False,
            default=str
        )

        _rb.db.session.commit()

        return _rb.jsonify({
            'ok':True,
            'run':_rb.qa_run_summary(row)
        })
    return api_qa_callback


def install_0739(_rb):
    @_rb.app.route('/admin/label-templates',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_label_templates():
        if _rb.request.method=='POST':
            row=_rb.LabelTemplate(name=(_rb.request.form.get('name') or 'Default Label').strip(),
              branch_id=_rb.request.form.get('branch_id',type=int),
              width_mm=_rb.request.form.get('width_mm',type=int) or 50,
              height_mm=_rb.request.form.get('height_mm',type=int) or 30,
              layout_json=(_rb.request.form.get('layout_json') or '{}').strip(),
              active=_rb.request.form.get('active')=='1',
              is_default=_rb.request.form.get('is_default')=='1')
            _rb.db.session.add(row);_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('admin_label_templates'))
        return _rb.render_template('admin_label_templates.html',
          rows=_rb.LabelTemplate.query.order_by(_rb.LabelTemplate.id.desc()).all(),
          branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all())
    return admin_label_templates


def install_0759(_rb):
    @_rb.app.route('/admin/ocr-settings',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_ocr_settings():
        row=_rb.OCRProviderSetting.query.order_by(_rb.OCRProviderSetting.id).first()
        if _rb.request.method=='POST':
            config=_rb._ocr_config_from_input(_rb.request.form)
            local=_rb.validate_ocr_local(config,_rb.os.environ)

            # Never allow an API key or token value to be persisted in a field that
            # is specifically intended to contain an environment-variable name.
            secret_check=local['fields'].get('secret_env_name',{})
            if secret_check.get('code')=='SECRET_ENV_NAME_INVALID':
                _rb.flash(secret_check.get('message') or 'Invalid secret environment variable name.','danger')
                return _rb.render_template('admin_ocr_settings.html',row=row,
                  draft=config,initial_validation=local,saved_validation=_rb._ocr_saved_validation(row),
                  supported_providers=_rb.SUPPORTED_PROVIDERS),400

            if config['enabled'] and not local.get('ok'):
                bad=[x.get('message') for x in local.get('fields',{}).values() if x.get('status')=='invalid']
                _rb.flash('OCR settings were not saved: '+'; '.join([x for x in bad if x][:3]),'danger')
                return _rb.render_template('admin_ocr_settings.html',row=row,
                  draft=config,initial_validation=local,saved_validation=_rb._ocr_saved_validation(row),
                  supported_providers=_rb.SUPPORTED_PROVIDERS),400

            if not row:
                row=_rb.OCRProviderSetting(provider_key=config['provider_key']);_rb.db.session.add(row)
            row.enabled=config['enabled']
            row.provider_key=config['provider_key']
            row.base_url=config['base_url']
            row.model_name=config['model_name']
            row.timeout_seconds=config['timeout_seconds']
            row.secret_env_name=config['secret_env_name']
            row.updated_by=_rb.current_user().id
            row.validation_status='NOT_CHECKED'
            row.validation_details='{}'
            row.validation_config_hash=''
            row.validation_latency_ms=None
            row.validated_by=None
            row.validated_at=None
            _rb.audit('OCR_SETTINGS_SAVE','ocr_provider_setting',row.id or '',
              f"provider={row.provider_key} enabled={row.enabled} base_host={_rb.urlparse(row.base_url).hostname or ''}")
            _rb.db.session.commit()

            if _rb.request.form.get('action')=='save_validate' and row.enabled:
                result=_rb.validate_ocr_remote(row,mode='connection',environ=_rb.os.environ)
                _rb._store_ocr_validation(row,result)
                _rb.audit('OCR_SETTINGS_VALIDATE','ocr_provider_setting',row.id,
                  f"provider={row.provider_key} status={result.get('overall')} error={result.get('error_code','')}")
                _rb.db.session.commit()
                _rb.flash(result.get('message') or result.get('overall'),
                  'success' if result.get('ok') else 'danger')
            else:
                _rb.flash('OCR settings saved. Validation is required before clinical use.','success')
            return _rb.redirect(_rb.url_for('admin_ocr_settings'))

        config=row if row else {
          'enabled':False,'provider_key':'GENERIC_OCR_REST','base_url':'http://radbridge-ocr:7400',
          'model_name':'','timeout_seconds':60,'secret_env_name':'RIS_OCR_API_KEY'}
        return _rb.render_template('admin_ocr_settings.html',row=row,draft=(config if not row else None),
          initial_validation=_rb.validate_ocr_local(config,_rb.os.environ),
          saved_validation=_rb._ocr_saved_validation(row),supported_providers=_rb.SUPPORTED_PROVIDERS)
    return admin_ocr_settings


def install_0760(_rb):
    @_rb.app.post('/admin/ocr-settings/validate')
    @_rb.require_perm('users.view')
    def admin_ocr_settings_validate():
        payload=_rb.request.get_json(silent=True) or _rb.request.form
        config=_rb._ocr_config_from_input(payload)
        mode='ocr' if str(payload.get('mode') or '').lower()=='ocr' else 'connection'
        result=_rb.validate_ocr_remote(config,mode=mode,environ=_rb.os.environ)
        row=_rb.OCRProviderSetting.query.order_by(_rb.OCRProviderSetting.id).first()
        persisted=_rb._store_ocr_validation(row,result)
        if persisted:
            _rb.audit('OCR_SETTINGS_TEST' if mode=='ocr' else 'OCR_SETTINGS_VALIDATE',
              'ocr_provider_setting',row.id,
              f"provider={config['provider_key']} status={result.get('overall')} error={result.get('error_code','')}")
            _rb.db.session.commit()
        result['saved_config_match']=persisted
        return _rb.jsonify(result)
    return admin_ocr_settings_validate


def install_0762(_rb):
    @_rb.app.route('/admin/printer-profiles',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_printer_profiles():
        if _rb.request.method=='POST':
            row=_rb.PrinterProfile(
                name=(_rb.request.form.get('name') or 'Printer Profile').strip(),
                branch_id=_rb.request.form.get('branch_id',type=int),
                user_id=_rb.request.form.get('user_id',type=int),
                workstation_code=(_rb.request.form.get('workstation_code') or '').strip(),
                document_type=(_rb.request.form.get('document_type') or 'A4').upper(),
                printer_name=(_rb.request.form.get('printer_name') or '').strip(),
                paper_size=(_rb.request.form.get('paper_size') or 'A4').upper(),
                copies=max(1,_rb.request.form.get('copies',type=int) or 1),
                auto_open_print_dialog=_rb.request.form.get('auto_open_print_dialog')=='1',
                active=_rb.request.form.get('active')=='1'
            )
            _rb.db.session.add(row);_rb.db.session.commit()
            _rb.audit('PRINTER_PROFILE_CREATE','printer_profile',row.id,row.name)
            return _rb.redirect(_rb.url_for('admin_printer_profiles'))
        return _rb.render_template('admin_printer_profiles.html',
            rows=_rb.PrinterProfile.query.order_by(_rb.PrinterProfile.id.desc()).all(),
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            users=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all())
    return admin_printer_profiles


def install_0763(_rb):
    @_rb.app.post('/admin/printer-profiles/<int:profile_id>/delete')
    @_rb.require_perm('users.view')
    def admin_printer_profile_delete(profile_id):
        row=_rb.PrinterProfile.query.get_or_404(profile_id)
        row.active=False;_rb.db.session.commit()
        _rb.audit('PRINTER_PROFILE_DISABLE','printer_profile',row.id,row.name)
        return _rb.redirect(_rb.url_for('admin_printer_profiles'))
    return admin_printer_profile_delete


def install_0804(_rb):
    @_rb.app.get('/admin/data-management')
    @_rb.require_perm('backup.view')
    def admin_data_management():
        patient_count=_rb.Patient.query.count()
        order_count=_rb.Order.query.count()
        return _rb.render_template('admin_data_management.html',storage_rows=_rb.admin_storage_paths(),
            patient_count=patient_count,order_count=order_count,
            backup_dir=_rb.admin_backup_dir(create=False))
    return admin_data_management


def install_0806(_rb):
    @_rb.app.post('/admin/data-management/create-manifest-backup')
    @_rb.require_perm('backup.create')
    def admin_create_manifest_backup():
        # Safe application-level backup manifest. Database dump remains external to avoid embedding DB passwords in web requests.
        stamp=_rb.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        path=_rb.os.path.join(_rb.admin_backup_dir(),f'ris-backup-manifest-{stamp}.json')
        payload={
            'created_at':_rb.datetime.utcnow().isoformat()+'Z',
            'version':_rb.APP_VERSION,
            'patients':_rb.Patient.query.count(),'orders':_rb.Order.query.count(),
            'storage':_rb.admin_storage_paths()
        }
        raw=_rb.json.dumps(payload,ensure_ascii=False,indent=2).encode()
        payload['sha256']=_rb.hashlib.sha256(raw).hexdigest()
        with open(path,'w',encoding='utf-8') as f:_rb.json.dump(payload,f,ensure_ascii=False,indent=2)
        _rb.audit('BACKUP_MANIFEST_CREATE','backup','',_rb.os.path.basename(path))
        _rb.flash(f'Backup manifest created: {_rb.os.path.basename(path)}','success')
        return _rb.redirect(_rb.url_for('admin_data_management'))
    return admin_create_manifest_backup


def install_0809(_rb):
    @_rb.app.post('/admin/data-management/reset-module')
    @_rb.require_perm('data.reset')
    def admin_reset_module():
        # Intentionally allow-list only non-clinical operational queues in v5.27.3.
        module=(_rb.request.form.get('module') or '').upper()
        allowed={'NOTIFICATIONS':'Notification'}
        if module not in allowed:
            _rb.abort(400,'This module is not approved for direct reset.')
        model=_rb.namespace().get(allowed[module])
        if model is None:_rb.abort(400,'Module model is unavailable.')
        count=model.query.count()
        expected=_rb.destructive_confirmation_token('RESET '+module,count)
        if (_rb.request.form.get('confirmation') or '').strip()!=expected:
            _rb.flash(f'Confirmation mismatch. Type exactly: {expected}','danger')
            return _rb.redirect(_rb.url_for('admin_data_management'))
        model.query.delete(synchronize_session=False);_rb.db.session.commit()
        _rb.audit('MODULE_RESET',module,'',f'rows={count}')
        _rb.flash(f'{module} reset complete. {count} row(s) removed.','success')
        return _rb.redirect(_rb.url_for('admin_data_management'))
    return admin_reset_module


def install_0829(_rb):
    @_rb.app.route('/admin/storage-dr',methods=['GET','POST'])
    @_rb.require_perm('storage.targets.view')
    def storage_dr_manager():
        """Storage and DR topology manager; credentials stay outside the RIS DB."""
        _rb.storage_defaults()
        if _rb.request.method=='POST':
            if not _rb.has_perm('storage.targets.manage'):_rb.abort(403)
            action=(_rb.request.form.get('action') or 'ADD_STORAGE').upper()
            if action=='ADD_STORAGE':
                code=(_rb.request.form.get('code') or '').strip().upper()
                if not code or _rb.StorageLocation.query.filter_by(code=code).first():
                    _rb.flash('Storage code is required and must be unique.','danger');return _rb.redirect(_rb.url_for('storage_dr_manager'))
                row=_rb.StorageLocation(code=code,label=(_rb.request.form.get('label') or code).strip(),
                  path=(_rb.request.form.get('path') or '').strip(),storage_type=(_rb.request.form.get('storage_type') or 'PACS').upper(),
                  protocol=(_rb.request.form.get('protocol') or 'LOCAL').upper(),role=(_rb.request.form.get('role') or 'PRIMARY').upper(),
                  branch_id=_rb.request.form.get('branch_id',type=int),company_code=(_rb.request.form.get('company_code') or '').strip().upper(),
                  vendor=(_rb.request.form.get('vendor') or '').strip(),endpoint=(_rb.request.form.get('endpoint') or '').strip(),
                  mount_source=(_rb.request.form.get('mount_source') or '').strip(),filesystem=(_rb.request.form.get('filesystem') or '').strip(),
                  priority=_rb.request.form.get('priority',type=int) or 100,read_only=_rb.request.form.get('read_only')=='1',
                  notes=(_rb.request.form.get('notes') or '').strip())
                _rb.db.session.add(row);_rb.db.session.flush();_rb.refresh_storage_health(row);_rb.audit('STORAGE_TARGET_ADD','storage_location',row.id,code)
            elif action=='ADD_NODE':
                if not _rb.has_perm('dr.manage'):_rb.abort(403)
                code=(_rb.request.form.get('node_code') or '').strip().upper()
                if not code or _rb.ReplicationNode.query.filter_by(code=code).first():
                    _rb.flash('Replication node code is required and must be unique.','danger');return _rb.redirect(_rb.url_for('storage_dr_manager'))
                row=_rb.ReplicationNode(code=code,name=(_rb.request.form.get('node_name') or code).strip(),
                  node_role=(_rb.request.form.get('node_role') or 'DR').upper(),branch_id=_rb.request.form.get('node_branch_id',type=int),
                  company_code=(_rb.request.form.get('node_company_code') or '').strip().upper(),host=(_rb.request.form.get('host') or '').strip(),
                  site=(_rb.request.form.get('site') or '').strip(),notes=(_rb.request.form.get('node_notes') or '').strip())
                _rb.db.session.add(row);_rb.db.session.flush();_rb.audit('DR_NODE_ADD','replication_node',row.id,code)
            elif action=='ADD_POLICY':
                if not _rb.has_perm('dr.manage'):_rb.abort(403)
                code=(_rb.request.form.get('policy_code') or '').strip().upper()
                src=_rb.request.form.get('source_node_id',type=int);dst=_rb.request.form.get('target_node_id',type=int)
                if not code or not src or not dst or src==dst:
                    _rb.flash('Policy code and distinct source/target nodes are required.','danger');return _rb.redirect(_rb.url_for('storage_dr_manager'))
                row=_rb.ReplicationPolicy(code=code,name=(_rb.request.form.get('policy_name') or code).strip(),source_node_id=src,target_node_id=dst,
                  data_scope=(_rb.request.form.get('data_scope') or 'PACS').upper(),transport=(_rb.request.form.get('transport') or 'RSYNC').upper(),
                  mode=(_rb.request.form.get('mode') or 'ASYNC').upper(),source_storage_id=_rb.request.form.get('source_storage_id',type=int),
                  target_storage_id=_rb.request.form.get('target_storage_id',type=int),rpo_minutes=max(0,_rb.request.form.get('rpo_minutes',type=int) or 15),
                  rto_minutes=max(0,_rb.request.form.get('rto_minutes',type=int) or 60),schedule=(_rb.request.form.get('schedule') or '').strip())
                _rb.db.session.add(row);_rb.db.session.flush();_rb.db.session.add(_rb.ReplicationState(policy_id=row.id,status='UNKNOWN'))
                _rb.audit('DR_POLICY_ADD','replication_policy',row.id,code)
            _rb.db.session.commit();_rb.flash('Storage / DR configuration saved.','success');return _rb.redirect(_rb.url_for('storage_dr_manager'))
        for row in _rb.StorageLocation.query.filter_by(active=True).all(): _rb.refresh_storage_health(row)
        _rb.db.session.commit()
        return _rb.render_template('storage_dr.html',storages=_rb.StorageLocation.query.order_by(_rb.StorageLocation.code).all(),
          nodes=_rb.ReplicationNode.query.order_by(_rb.ReplicationNode.code).all(),policies=_rb.ReplicationPolicy.query.order_by(_rb.ReplicationPolicy.code).all(),
          states={x.policy_id:x for x in _rb.ReplicationState.query.order_by(_rb.ReplicationState.id.desc()).all()},
          failovers=_rb.FailoverEvent.query.order_by(_rb.FailoverEvent.id.desc()).limit(100).all(),branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all())
    return storage_dr_manager


def install_0830(_rb):
    @_rb.app.post('/admin/storage-dr/storage/<int:storage_id>/health')
    @_rb.require_perm('storage.targets.manage')
    def storage_target_health(storage_id):
        row=_rb.StorageLocation.query.get_or_404(storage_id);_rb.refresh_storage_health(row);_rb.audit('STORAGE_HEALTH_CHECK','storage_location',row.id,row.health_status);_rb.db.session.commit()
        return _rb.redirect(_rb.url_for('storage_dr_manager'))
    return storage_target_health


def install_0831(_rb):
    @_rb.app.post('/admin/storage-dr/policy/<int:policy_id>/state')
    @_rb.require_perm('dr.manage')
    def replication_state_update(policy_id):
        policy=_rb.ReplicationPolicy.query.get_or_404(policy_id)
        state=_rb.ReplicationState.query.filter_by(policy_id=policy.id).order_by(_rb.ReplicationState.id.desc()).first() or _rb.ReplicationState(policy_id=policy.id)
        state.status=(_rb.request.form.get('status') or 'UNKNOWN').upper();state.lag_seconds=max(0,_rb.request.form.get('lag_seconds',type=int) or 0)
        state.pending_items=max(0,_rb.request.form.get('pending_items',type=int) or 0);state.pending_bytes=max(0,_rb.request.form.get('pending_bytes',type=int) or 0)
        state.last_error=(_rb.request.form.get('last_error') or '').strip();state.checkpoint=(_rb.request.form.get('checkpoint') or '').strip();state.last_check_at=_rb.datetime.utcnow()
        if state.status=='HEALTHY':state.last_success_at=_rb.datetime.utcnow()
        _rb.db.session.add(state);_rb.audit('DR_STATE_UPDATE','replication_policy',policy.id,state.status);_rb.db.session.commit();return _rb.redirect(_rb.url_for('storage_dr_manager'))
    return replication_state_update


def install_0832(_rb):
    @_rb.app.post('/admin/storage-dr/policy/<int:policy_id>/failover')
    @_rb.require_perm('dr.failover')
    def dr_failover_request(policy_id):
        policy=_rb.ReplicationPolicy.query.get_or_404(policy_id);action=(_rb.request.form.get('action') or 'PLAN').upper()
        if action not in ('PLAN','TEST','PROMOTE','FAILBACK'):_rb.abort(400)
        # Safety: RadBridge records and audits the request; infrastructure orchestration must execute promotion externally.
        row=_rb.FailoverEvent(policy_id=policy.id,action=action,status='PLANNED',requested_by=_rb.current_user().id,notes=(_rb.request.form.get('notes') or '').strip())
        _rb.db.session.add(row);_rb.db.session.flush();_rb.audit('DR_FAILOVER_REQUEST','failover_event',row.id,f'{policy.code}:{action}');_rb.db.session.commit()
        _rb.flash('Failover request recorded. Infrastructure promotion is intentionally not executed automatically by the web app.','warning')
        return _rb.redirect(_rb.url_for('storage_dr_manager'))
    return dr_failover_request


def install_0833(_rb):
    @_rb.app.route('/admin/storage-cloud',methods=['GET','POST'])
    @_rb.require_perm('storage.cloud.view')
    def storage_cloud_manager():
        _rb.storage_defaults()
        if _rb.request.method=='POST':
            if not _rb.has_perm('storage.cloud.manage'):_rb.abort(403)
            row=_rb.CloudBackupConfig(
              name=(_rb.request.form.get('name') or 'Daily Cloud Backup').strip(),
              provider=(_rb.request.form.get('provider') or 'RCLONE').upper(),
              rclone_remote=(_rb.request.form.get('rclone_remote') or '').strip(),
              remote_root=(_rb.request.form.get('remote_root') or '').strip(),
              include_reports=_rb.request.form.get('include_reports')=='1',
              include_attachments=_rb.request.form.get('include_attachments')=='1',
              include_database=_rb.request.form.get('include_database')=='1',
              include_pacs=_rb.request.form.get('include_pacs')=='1',
              schedule_hour=max(0,min(23,_rb.request.form.get('schedule_hour',type=int) or 2)),active=True)
            _rb.db.session.add(row);_rb.db.session.commit();_rb.flash('Cloud backup profile saved. Credentials remain outside the RIS database.','success')
            return _rb.redirect(_rb.url_for('storage_cloud_manager'))
        return _rb.render_template('storage_cloud.html',
          locations=_rb.StorageLocation.query.order_by(_rb.StorageLocation.id).all(),
          configs=_rb.CloudBackupConfig.query.order_by(_rb.CloudBackupConfig.id.desc()).all(),
          runs=_rb.BackupRun.query.order_by(_rb.BackupRun.id.desc()).limit(100).all())
    return storage_cloud_manager


def install_0948(_rb):
    @_rb.app.route("/admin/ivr")
    @_rb.login_required
    def admin_ivr():
        uid = _rb.session.get("uid")
        user = _rb.db.session.get(_rb.User, uid) if uid else None

        if not user:
            return _rb.redirect(_rb.url_for("login"))

        extension_count = _rb.TelephonyExtension.query.filter_by(
            active=True
        ).count()

        return _rb.render_template(
            "admin_ivr.html",
            extension_count=extension_count
        )
    return admin_ivr
