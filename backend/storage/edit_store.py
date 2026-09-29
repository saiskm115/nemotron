import uuid
from typing import List, Optional, Any
from ..models.session import EditCommand

class EditHistoryManager:
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.undo_stack: List[EditCommand] = []
        self.redo_stack: List[EditCommand] = []

    def record_edit(self, edit_type: str, before_state: Any, after_state: Any) -> EditCommand:
        cmd = EditCommand(
            id=str(uuid.uuid4()),
            type=edit_type,
            before=before_state,
            after=after_state
        )
        self.undo_stack.append(cmd)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear() # Clear redo when new edit occurs
        return cmd

    def undo(self) -> Optional[EditCommand]:
        if not self.undo_stack:
            return None
        cmd = self.undo_stack.pop()
        self.redo_stack.append(cmd)
        return cmd

    def redo(self) -> Optional[EditCommand]:
        if not self.redo_stack:
            return None
        cmd = self.redo_stack.pop()
        self.undo_stack.append(cmd)
        return cmd
