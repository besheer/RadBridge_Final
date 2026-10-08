"""Read-only readiness projection and non-overridable reception barrier."""
import json

def receiving(order):
    return str(getattr(order,'pacs_status','') or '').strip().upper()=='RECEIVING'

class BlockedReceptionView:
    def __init__(self,row):self._row=row
    status='BLOCKED'
    score=0
    incomplete_images=True
    def __getattr__(self,name):
        if self._row is None:return None
        return getattr(self._row,name)
    @property
    def details_json(self):
        try:details=json.loads(getattr(self._row,'details_json','') or '{}')
        except (TypeError,ValueError):details={}
        if not isinstance(details,dict):details={}
        blockers=details.get('blockers',[])
        if not isinstance(blockers,list):blockers=[]
        details['blockers']=sorted(set(str(item) for item in blockers)|{'PACS_RECEIVING'})
        return json.dumps(details)

def view(order,row):
    return BlockedReceptionView(row) if receiving(order) else row
