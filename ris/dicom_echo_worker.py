import json,sys,time,logging
from pynetdicom import AE
from pynetdicom.sop_class import Verification
logging.getLogger('pynetdicom').setLevel(logging.CRITICAL)

def run(host,port,called,calling):
    started=time.monotonic();association=None;ae=AE(ae_title=calling)
    ae.add_requested_context(Verification)
    ae.acse_timeout=3;ae.dimse_timeout=3;ae.network_timeout=3
    try:
        association=ae.associate(host,int(port),ae_title=called)
        if not association.is_established:
            return {'result':'UNREACHABLE','message':'DICOM association unavailable or rejected.','elapsed_ms':round((time.monotonic()-started)*1000)}
        status=association.send_c_echo()
        success=bool(status is not None and getattr(status,'Status',None)==0)
        return {'result':'SUCCESS' if success else 'FAILED','message':'C-ECHO succeeded.' if success else 'C-ECHO did not return success.','elapsed_ms':round((time.monotonic()-started)*1000)}
    finally:
        if association:
            if association.is_established:association.release()
            elif not association.is_released:association.abort()
        ae.shutdown()

if __name__=='__main__':
    try:print(json.dumps(run(*sys.argv[1:5])))
    except Exception:print(json.dumps({'result':'FAILED','message':'DICOM connection failed.','elapsed_ms':0}))
