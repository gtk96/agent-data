"""
Workflow state management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowState(BaseModel):
    """Workflow execution state."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="State ID")
    workflow_id: str = Field(..., description="Workflow ID")
    current_step: int = Field(0, description="Current step index")
    data: Dict[str, Any] = Field(default_factory=dict, description="Workflow data")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Execution history")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    def update(self, key: str, value: Any) -> None:
        """Update state data."""
        self.data[key] = value
        self.updated_at = datetime.now()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state data."""
        return self.data.get(key, default)

    def add_history(self, step_name: str, result: Dict[str, Any]) -> None:
        """Add entry to execution history."""
        self.history.append(
            {
                "step": step_name,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.updated_at = datetime.now()

    def next_step(self) -> bool:
        """Advance to next step."""
        self.current_step += 1
        self.updated_at = datetime.now()
        return True
