import pytest
from backend.models.turn import Turn
from backend.pipeline.reconciliation import TurnReconciler

def test_interim_to_final_reconciliation():
    reconciler = TurnReconciler()
    existing_turns = [
        Turn(
            id="turn_live_1",
            speaker_id="speaker_0",
            start=0.2,
            end=1.5,
            text="నేను meeting కి...",
            status="interim",
            source="model"
        )
    ]

    final_turn = Turn(
        id="turn_final_incoming",
        speaker_id="speaker_0",
        start=0.2,
        end=3.1,
        text="నేను meeting కి 10 minutes late అవుతాను.",
        status="final",
        source="model"
    )

    reconciled = reconciler.reconcile_turn(existing_turns, final_turn)

    assert len(reconciled) == 1
    assert reconciled[0].id == "turn_live_1"
    assert reconciled[0].status == "final"
    assert reconciled[0].text == "నేను meeting కి 10 minutes late అవుతాను."
    assert reconciled[0].end == 3.1

def test_preserve_user_edits_during_reconciliation():
    reconciler = TurnReconciler()
    # Turn was edited by user before final result arrived
    existing_turns = [
        Turn(
            id="turn_live_1",
            speaker_id="speaker_0",
            start=0.2,
            end=1.5,
            text="నేను manual edit చేశాను.",
            status="edited",
            source="user_edit"
        )
    ]

    final_incoming = Turn(
        id="turn_final_incoming",
        speaker_id="speaker_0",
        start=0.2,
        end=3.1,
        text="నేను meeting కి 10 minutes late అవుతాను.",
        status="final",
        source="model"
    )

    reconciled = reconciler.reconcile_turn(existing_turns, final_incoming)

    assert len(reconciled) == 1
    # User's edit must NOT be overwritten!
    assert reconciled[0].text == "నేను manual edit చేశాను."
    assert reconciled[0].source == "user_edit"
    # But model original output must be stored in background
    assert reconciled[0].original_model_text == "నేను meeting కి 10 minutes late అవుతాను."
