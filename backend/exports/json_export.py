import json
from ..models.session import Session

def export_json(session: Session) -> str:
    """Exports canonical JSON session dump according to Section 34."""
    data = session.model_dump()
    return json.dumps(data, indent=2, ensure_ascii=False)
