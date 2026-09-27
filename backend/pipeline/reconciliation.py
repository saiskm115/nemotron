from typing import List, Optional
from ..models.turn import Turn
from .alignment import parse_language_segments

class TurnReconciler:
    """
    Reconciles incoming streaming ASR results (interim or final) with existing session turns.
    Preserves user edits if the turn has already been modified by the user (source='user_edit').
    """

    def reconcile_turn(
        self,
        existing_turns: List[Turn],
        incoming_turn: Turn
    ) -> List[Turn]:
        updated_turns = list(existing_turns)
        
        # 1. Search for matching interim turn by overlapping timestamp window
        matched_idx: Optional[int] = None
        for idx, t in enumerate(updated_turns):
            if t.status in ("interim", "edited"):
                # Check timestamp overlap
                overlap = max(0.0, min(t.end, incoming_turn.end) - max(t.start, incoming_turn.start))
                if overlap > 0.1 or (abs(t.start - incoming_turn.start) < 0.5):
                    matched_idx = idx
                    break

        if matched_idx is not None:
            existing = updated_turns[matched_idx]
            # If user already edited this turn, do not overwrite the user's text!
            if existing.source == "user_edit":
                # Update background model metadata only
                existing.original_model_text = incoming_turn.text
                existing.original_model_speaker_id = incoming_turn.speaker_id
                existing.original_start = incoming_turn.start
                existing.original_end = incoming_turn.end
                if incoming_turn.status == "final":
                    existing.status = "edited"
            else:
                # Update interim turn with incoming (potentially final) data
                lang_segs, _ = parse_language_segments(incoming_turn.text)
                existing.text = incoming_turn.text
                existing.speaker_id = incoming_turn.speaker_id
                existing.start = incoming_turn.start
                existing.end = incoming_turn.end
                existing.status = incoming_turn.status
                existing.overlap = incoming_turn.overlap
                existing.overlap_speakers = incoming_turn.overlap_speakers
                existing.language_segments = lang_segs
                existing.original_model_text = incoming_turn.text
                existing.original_model_speaker_id = incoming_turn.speaker_id
                existing.original_start = incoming_turn.start
                existing.original_end = incoming_turn.end
        else:
            # Append new turn
            updated_turns.append(incoming_turn)

        return updated_turns
