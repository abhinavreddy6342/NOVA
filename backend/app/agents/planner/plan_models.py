from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanStepStatus(str, Enum):
    """
    Execution state of an individual agent step.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(str, Enum):
    """
    Overall state of an agent plan.
    """

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStep(BaseModel):
    """
    A single executable step inside an NOVA plan.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the step.",
    )

    title: str = Field(
        ...,
        description="Human-readable step title.",
    )

    description: str = Field(
        ...,
        description="What NOVA should accomplish.",
    )

    tool: Optional[str] = Field(
        default=None,
        description="Tool required to execute this step.",
    )

    dependencies: List[str] = Field(
        default_factory=list,
        description="IDs of prerequisite steps.",
    )

    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inputs required by the step.",
    )

    expected_output: Optional[str] = Field(
        default=None,
        description="Expected result of the step.",
    )

    status: PlanStepStatus = (
        PlanStepStatus.PENDING
    )

    result: Any = Field(
        default=None,
        description="Actual execution result.",
    )

    error: Optional[str] = Field(
        default=None,
        description="Error produced during execution.",
    )


class AgentPlan(BaseModel):
    """
    Complete execution plan created by NOVA.
    """

    id: str = Field(
        ...,
        description="Unique plan identifier.",
    )

    objective: str = Field(
        ...,
        description="The user's overall objective.",
    )

    status: PlanStatus = (
        PlanStatus.CREATED
    )

    steps: List[PlanStep] = Field(
        default_factory=list,
        description="Ordered execution steps.",
    )

    tools_required: List[str] = Field(
        default_factory=list,
        description="Tools required by this plan.",
    )

    expected_outputs: List[str] = Field(
        default_factory=list,
        description="Final outputs expected from the plan.",
    )

    verification_required: bool = Field(
        default=True,
        description=(
            "Whether the completed plan "
            "must be verified."
        ),
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata.",
    )