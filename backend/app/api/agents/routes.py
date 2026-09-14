from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.execution.executor import AgentExecutor
from app.agents.planner.planner import agent_planner
from app.agents.response.synthesizer import (
    agent_response_synthesizer,
)
from app.core.database import get_db
from app.services.chat_history import (
    add_message,
    create_conversation,
    get_conversation,
)


router = APIRouter(
    prefix="/api/agents",
    tags=["Agents"],
)


class AgentRunRequest(BaseModel):
    objective: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None
    auto_confirm: bool = False


class AgentRunResponse(BaseModel):
    conversation_id: Optional[str] = None
    plan: Dict[str, Any]
    execution: Dict[str, Any]
    response: str


def serialize_execution(
    execution: Any,
) -> Dict[str, Any]:
    """
    Convert the existing ExecutionResult object
    into JSON-safe response data.
    """

    if hasattr(
        execution,
        "to_dict",
    ):
        return execution.to_dict()

    result: Dict[str, Any] = {}

    for attribute in (
        "completed_steps",
        "failed_steps",
        "blocked_steps",
    ):
        if hasattr(
            execution,
            attribute,
        ):
            result[attribute] = getattr(
                execution,
                attribute,
            )

    if hasattr(
        execution,
        "plan",
    ):
        plan = execution.plan

        if hasattr(
            plan,
            "status",
        ):
            result["status"] = (
                plan.status.value
                if hasattr(
                    plan.status,
                    "value",
                )
                else str(plan.status)
            )

    return result


def build_synthesis_context(
    execution: Any,
) -> Dict[str, Any]:
    """
    Extract successful step results from the executed plan
    for final response synthesis.
    """

    context: Dict[str, Any] = {}

    if not hasattr(
        execution,
        "plan",
    ):
        return context

    plan = execution.plan

    for step in plan.steps:
        if (
            step.status.value == "completed"
            and step.result is not None
        ):
            context[step.id] = step.result

    return context


def build_conversation_title(
    objective: str,
) -> str:
    """
    Create a clean Recent Chats title from the user's objective.
    """

    cleaned = " ".join(
        objective.strip().split()
    )

    if not cleaned:
        return "NOVA Agent Chat"

    if len(cleaned) <= 70:
        return cleaned

    return (
        cleaned[:67].rstrip()
        + "..."
    )


@router.post(
    "/run",
    response_model=AgentRunResponse,
)
def run_agent(
    request: AgentRunRequest,
    db: Session = Depends(get_db),
) -> AgentRunResponse:

    objective = request.objective.strip()

    if not objective:
        raise HTTPException(
            status_code=400,
            detail="Objective cannot be empty.",
        )

    try:
        # ---------------------------------------------------------------
        # CONVERSATION
        # ---------------------------------------------------------------

        supplied_conversation_id = None

        if request.context:
            supplied_conversation_id = (
                request.context.get(
                    "conversation_id"
                )
            )

        conversation = None

        if supplied_conversation_id:
            conversation = get_conversation(
                db,
                str(
                    supplied_conversation_id
                ),
            )

        # ---------------------------------------------------------------
        # PLAN
        # ---------------------------------------------------------------

        plan = agent_planner.create_plan(
            objective=objective,
        )

        # ---------------------------------------------------------------
        # EXECUTE
        # ---------------------------------------------------------------

        executor = AgentExecutor(
            auto_confirm=request.auto_confirm,
        )

        execution = executor.execute(
            plan=plan,
            context=request.context or {},
        )

        # ---------------------------------------------------------------
        # SYNTHESIZE FINAL RESPONSE
        # ---------------------------------------------------------------

        synthesis_context = (
            build_synthesis_context(
                execution
            )
        )

        if synthesis_context:
            response = (
                agent_response_synthesizer.synthesize(
                    objective=objective,
                    execution_context=synthesis_context,
                )
            )
        else:
            response = (
                "NOVA could not produce a final answer "
                "because the agent execution did not "
                "produce any completed results."
            )

        # ---------------------------------------------------------------
        # CREATE CONVERSATION WHEN NEEDED
        # ---------------------------------------------------------------

        if conversation is None:
            conversation = create_conversation(
                db,
                title=build_conversation_title(
                    objective
                ),
            )

        # ---------------------------------------------------------------
        # SAVE USER MESSAGE
        # ---------------------------------------------------------------

        add_message(
            db=db,
            conversation=conversation,
            role="user",
            content=objective,
            model=None,
        )

        # ---------------------------------------------------------------
        # SAVE ASSISTANT RESPONSE
        # ---------------------------------------------------------------

        add_message(
            db=db,
            conversation=conversation,
            role="assistant",
            content=response,
            model="NOVA Agent",
        )

        # ---------------------------------------------------------------
        # RETURN
        # ---------------------------------------------------------------

        return AgentRunResponse(
            conversation_id=conversation.id,
            plan=plan.model_dump(
                mode="json"
            ),
            execution=serialize_execution(
                execution
            ),
            response=response,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {exc}",
        ) from exc