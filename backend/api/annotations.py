from typing import List

from fastapi import APIRouter, HTTPException

from ..models.annotation import Annotation, AnnotationCreate, AnnotationUpdate
from ..storage.session_store import session_store

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


@router.get("/{session_id}", response_model=List[Annotation])
async def list_annotations(session_id: str):
    """Every manual label on a session's timeline, in chronological order."""
    if not session_store.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return session_store.list_annotations(session_id)


@router.post("/{session_id}", response_model=Annotation, status_code=201)
async def create_annotation(session_id: str, req: AnnotationCreate):
    """
    Records a label the reviewer drew on the timeline.

    The range is clamped to the recording, so a drag that runs off either end of
    the viewport still produces a valid annotation instead of a 400.
    """
    annotation = session_store.create_annotation(session_id, req)
    if not annotation:
        raise HTTPException(status_code=404, detail="Session not found")
    return annotation


@router.patch("/{session_id}/{annotation_id}", response_model=Annotation)
async def update_annotation(session_id: str, annotation_id: str, update: AnnotationUpdate):
    annotation = session_store.update_annotation(session_id, annotation_id, update)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation or session not found")
    return annotation


@router.post("/{session_id}/{annotation_id}/apply", status_code=200)
async def apply_annotation(session_id: str, annotation_id: str):
    """
    Re-labels the turns an annotation covers with the speaker it names.

    This is how a reviewer corrects the diarisation: draw a region, say who is
    speaking in it, and every turn inside that region moves to that speaker. The
    change joins the undo history like any other edit.
    """
    changed = session_store.apply_annotation_to_turns(session_id, annotation_id)
    if changed == 0:
        raise HTTPException(
            status_code=400,
            detail="Nothing to apply: pick an annotation that names a speaker and covers at least one turn",
        )
    return {"turns_updated": changed}


@router.delete("/{session_id}/{annotation_id}", status_code=204)
async def delete_annotation(session_id: str, annotation_id: str):
    if not session_store.delete_annotation(session_id, annotation_id):
        raise HTTPException(status_code=404, detail="Annotation or session not found")
    return None
