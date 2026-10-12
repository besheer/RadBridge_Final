"""Local artifact evidence restricted to the configured report root."""
from pathlib import Path


class ReportDeliveryFiles:
    def __init__(self, root, validate_patient):self.root,self.validate_patient=root,validate_patient

    def matches(self, order, report):
        root=Path(self.root).resolve()
        for raw in (report.pdf_path,report.docx_path,report.source_path):
            if not raw:continue
            try:
                path=Path(raw).resolve();path.relative_to(root)
                if not path.is_file() or path.stat().st_size==0 or path.suffix.lower() not in ('.pdf','.docx'):continue
                result=self.validate_patient(order,str(path),path.suffix)
                if result.get('result')=='MATCH':return True
            except Exception:
                continue
        return False
