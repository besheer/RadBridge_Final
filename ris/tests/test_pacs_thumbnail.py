from types import SimpleNamespace
import pytest
from pacs_thumbnail import study_preview, ThumbnailUnavailable


def preview(data=b'\x89PNG\r\n\x1a\nsmall-real-png',mime='image/png'):
    return SimpleNamespace(content=data,headers={'Content-Type':mime},raise_for_status=lambda:None)


def test_small_real_preview_is_returned_without_svg_placeholder():
    image=preview()
    data,mime=study_preview({'Instances':['image']},lambda _:None,lambda _:image)
    assert data==image.content and len(data)<128 and mime=='image/png'


def test_retry_another_instance_in_same_study_after_preview_failure():
    calls=[]
    def get(instance):
        calls.append(instance)
        if instance=='bad':raise RuntimeError('Unsupported transfer syntax')
        return preview()
    assert study_preview({'Series':['series']},lambda _: {'Instances':['bad','good']},get)[1]=='image/png'
    assert calls==['bad','good']


def test_skip_report_series_and_try_next_image_series():
    calls=[]
    def series(key):
        return {'MainDicomTags':{'Modality':'SR' if key=='report' else 'CT'},'Instances':[key]}
    study_preview({'Series':['report','image']},series,lambda key:calls.append(key) or preview())
    assert calls==['image']


@pytest.mark.parametrize('image',[preview(b'<svg/>','image/svg+xml'),preview(b'not-pixels'),preview(b'{"error":true}','application/json')])
def test_reject_non_pixel_or_mislabelled_response(image):
    with pytest.raises(ThumbnailUnavailable):
        study_preview({'Instances':['bad']},lambda _:None,lambda _:image)


def test_preview_requests_are_bounded_and_duplicate_instances_ignored():
    calls=[]
    def get(key):calls.append(key);raise RuntimeError('No pixels')
    with pytest.raises(ThumbnailUnavailable):
        study_preview({'Instances':['same','same','a','b'],'Series':['one','two']},lambda _: {'Instances':['c','d']},get)
    assert calls==['same','a','b','c']


def test_real_jpeg_retains_response_bytes():
    image=preview(b'\xff\xd8\xffreal-jpeg','image/jpeg; charset=binary')
    assert study_preview({'Instances':['image']},lambda _:None,lambda _:image)==(image.content,'image/jpeg')
