"""Orthanc evidence transport with the existing bounded request timeout."""
from urllib.parse import quote


class OrthancDeliveryEvidence:
    def __init__(self, base_url, get, auth):self.base_url,self.get,self.auth=base_url,get,auth

    def _json(self, study_id, suffix=''):
        url=self.base_url+'/studies/'+quote(study_id,safe='')+suffix
        response=self.get(url,auth=self.auth(),timeout=8)
        response.raise_for_status()
        return response.json()

    def study(self, study_id):return self._json(study_id)
    def instance_count(self, study_id):
        return int(self._json(study_id,'/statistics').get('CountInstances') or 0)
