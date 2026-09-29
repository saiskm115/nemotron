import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# The annotation kinds a reviewer can tag a region with. ``speaker_label`` is the
# one that changes diarisation: attaching it to a region asserts which voice is
# talking there, which is how a human corrects a model that split one person into
# four or merged two into one.
AnnotationLabel = Literal[
    "note",
    "important",
    "question",
    "action_item",
    "review",
    "backchannel",
    "speaker_label",
    "error",
]

MIN_ANNOTATION_SEC = 0.05


class Annotation(BaseModel):
    id: str = Field(default_factory=lambda: f"ann_{uuid.uuid4().hex[:10]}")
    start: float
    end: float
    # Short tag shown on the timeline block, e.g. "wrong speaker" or "follow up".
    text: str = ""
    label: AnnotationLabel = "note"
    # Which voice this annotation is about. None means "this region", not a
    # particular speaker.
    speaker_id: Optional[str] = None
    # Which turn the annotator had selected, when there was one.
    turn_id: Optional[str] = None
    source: Literal["manual", "model"] = "manual"
    author: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def normalised(self, duration: Optional[float] = None) -> "Annotation":
        """Clamps to a valid, non-degenerate range, left edge first."""
        start = max(0.0, round(float(self.start), 3))
        end = round(float(self.end), 3)
        if end < start:
            start, end = end, start
        if end - start < MIN_ANNOTATION_SEC:
            end = round(start + MIN_ANNOTATION_SEC, 3)
        if duration and duration > 0:
            start = min(start, round(duration, 3))
            end = min(end, round(duration, 3))
            if end - start < MIN_ANNOTATION_SEC:
                end = min(round(duration, 3), round(start + MIN_ANNOTATION_SEC, 3))
                if end <= start:
                    start = max(0.0, round(end - MIN_ANNOTATION_SEC, 3))
        self.start = start
        self.end = end
        return self


class AnnotationCreate(BaseModel):
    start: float
    end: float
    text: str = ""
    label: AnnotationLabel = "note"
    speaker_id: Optional[str] = None
    turn_id: Optional[str] = None
    author: Optional[str] = None


class AnnotationUpdate(BaseModel):
    start: Optional[float] = None
    end: Optional[float] = None
    text: Optional[str] = None
    label: Optional[AnnotationLabel] = None
    speaker_id: Optional[str] = None
    turn_id: Optional[str] = None
    author: Optional[str] = None
