from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.execution.executor import AgentExecutor
from app.agents.planner.planner import agent_planner
from app.agents.response.synthesizer import (
    agent_response_synthesizer,
)
from app.core.database import get_db
from app.services.chat_files import (
    load_chat_file,
)
from app.services.chat_history import (
    add_attachment,
    add_message,
    create_conversation,
    get_conversation,
)


router = APIRouter(
    prefix="/api/agents",
    tags=["Agents"],
)


# ---------------------------------------------------------------------------
# NOVA WORKSPACE
# ---------------------------------------------------------------------------

# routes.py is located at:
# backend/app/api/agents/routes.py
#
# parents[0] -> agents
# parents[1] -> api
# parents[2] -> app
# parents[3] -> backend

APP_ROOT = Path(__file__).resolve().parents[2]

BACKEND_ROOT = (
    APP_ROOT.parent
).resolve()

WORKSPACE_ROOT = (
    APP_ROOT
    / "workspace"
).resolve()

WORKSPACE_INPUT_DIR = (
    WORKSPACE_ROOT
    / "input"
).resolve()

CHAT_UPLOADS_DIR = (
    APP_ROOT
    / "knowledge"
    / "chat_uploads"
).resolve()

ALLOWED_SPREADSHEET_EXTENSIONS = {
    ".csv",
    ".xlsx",
}


# ---------------------------------------------------------------------------
# REQUEST / RESPONSE MODELS
# ---------------------------------------------------------------------------

class AgentRunRequest(BaseModel):
    objective: str = Field(..., min_length=1)

    context: Optional[Dict[str, Any]] = None

    auto_confirm: bool = False


class AgentRunResponse(BaseModel):
    conversation_id: Optional[str] = None

    plan: Dict[str, Any]

    execution: Dict[str, Any]

    response: str


# ---------------------------------------------------------------------------
# ATTACHMENT HELPERS
# ---------------------------------------------------------------------------

def _get_context_attachments(
    context: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract attachment references from the agent context.
    """

    if not context:
        return []

    attachments = context.get(
        "attachments",
        [],
    )

    if not isinstance(
        attachments,
        list,
    ):
        return []

    normalized: List[Dict[str, Any]] = []

    for attachment in attachments:
        if not isinstance(
            attachment,
            dict,
        ):
            continue

        file_id = str(
            attachment.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            continue

        normalized.append(
            {
                "file_id": file_id,
                "filename": str(
                    attachment.get(
                        "filename",
                        "",
                    )
                ).strip(),
                "content_type": str(
                    attachment.get(
                        "content_type",
                        "",
                    )
                ).strip(),
            }
        )

    return normalized


def _resolve_chat_upload_path(
    file_id: str,
) -> Path:
    """
    Resolve a previously uploaded chat file inside
    NOVA's controlled chat-upload directory.
    """

    metadata = load_chat_file(
        file_id
    )

    stored_name = str(
        metadata.get(
            "stored_name",
            "",
        )
    ).strip()

    if not stored_name:
        raise ValueError(
            "Uploaded file metadata does not contain a stored filename."
        )

    source_path = (
        CHAT_UPLOADS_DIR
        / Path(stored_name).name
    ).resolve()

    try:
        source_path.relative_to(
            CHAT_UPLOADS_DIR
        )
    except ValueError as exc:
        raise PermissionError(
            "Access denied: uploaded file is outside "
            "NOVA's controlled attachment directory."
        ) from exc

    if not source_path.exists():
        raise FileNotFoundError(
            f"Uploaded file not found: {file_id}"
        )

    if not source_path.is_file():
        raise ValueError(
            "Uploaded attachment is not a file."
        )

    return source_path


def _stage_spreadsheet_attachment(
    attachment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Copy an uploaded spreadsheet into NOVA's controlled
    workspace/input directory.

    The planner and spreadsheet tools operate only on the
    controlled NOVA workspace, so uploaded attachments are
    staged there before agent execution.
    """

    file_id = attachment.get(
        "file_id",
        "",
    )

    if not file_id:
        raise ValueError(
            "Spreadsheet attachment is missing file_id."
        )

    source_path = _resolve_chat_upload_path(
        str(file_id)
    )

    extension = source_path.suffix.lower()

    if extension not in ALLOWED_SPREADSHEET_EXTENSIONS:
        raise ValueError(
            "Agent spreadsheet analysis supports only "
            "CSV and XLSX attachments."
        )

    original_filename = (
        attachment.get(
            "filename"
        )
        or source_path.name
    )

    original_filename = Path(
        str(original_filename)
    ).name

    if not original_filename:
        original_filename = source_path.name

    safe_filename = (
        f"{file_id}_{original_filename}"
    )

    destination_path = (
        WORKSPACE_INPUT_DIR
        / safe_filename
    ).resolve()

    try:
        destination_path.relative_to(
            WORKSPACE_INPUT_DIR
        )
    except ValueError as exc:
        raise PermissionError(
            "Access denied: staged spreadsheet must remain "
            "inside NOVA's workspace input directory."
        ) from exc

    WORKSPACE_INPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source_path,
        destination_path,
    )

    if not destination_path.exists():
        raise RuntimeError(
            "Uploaded spreadsheet could not be staged "
            "into the NOVA workspace."
        )

    return {
        "file_id": str(file_id),
        "original_filename": original_filename,
        "workspace_file_path": str(
            destination_path.relative_to(
                WORKSPACE_ROOT
            )
        ).replace(
            "\\",
            "/",
        ),
        "workspace_absolute_path": str(
            destination_path
        ),
        "extension": extension,
    }


def _prepare_agent_context(
    context: Optional[Dict[str, Any]],
    objective: str,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Prepare context for agent execution.

    Uploaded spreadsheet attachments are staged into
    NOVA's controlled workspace and their workspace paths
    are exposed to the planner through the objective.
    """

    prepared_context: Dict[str, Any] = dict(
        context or {}
    )

    attachments = _get_context_attachments(
        context
    )

    if not attachments:
        return (
            prepared_context,
            [],
        )

    staged_attachments: List[Dict[str, Any]] = []

    for attachment in attachments:
        staged = _stage_spreadsheet_attachment(
            attachment
        )

        staged_attachments.append(
            staged
        )

    prepared_context[
        "attachments"
    ] = staged_attachments

    spreadsheet_paths = [
        item["workspace_file_path"]
        for item in staged_attachments
    ]

    prepared_context[
        "spreadsheet_files"
    ] = spreadsheet_paths

    if spreadsheet_paths:
        attachment_instruction = (
            "\n\nUploaded spreadsheet attachment(s) are available "
            "inside the NOVA workspace at:\n"
            + "\n".join(
                f"- {path}"
                for path in spreadsheet_paths
            )
            + "\nUse these local paths when the user's request "
            "requires spreadsheet analysis."
        )

        prepared_context[
            "agent_objective"
        ] = (
            objective
            + attachment_instruction
        )

    return (
        prepared_context,
        staged_attachments,
    )


def _cleanup_staged_files(
    staged_attachments: List[Dict[str, Any]],
) -> None:
    """
    Remove temporary spreadsheet copies created for the
    agent execution.
    """

    for attachment in staged_attachments:
        path_value = attachment.get(
            "workspace_absolute_path"
        )

        if not path_value:
            continue

        path = Path(
            str(path_value)
        ).resolve()

        try:
            path.relative_to(
                WORKSPACE_INPUT_DIR
            )
        except ValueError:
            continue

        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            continue


# ---------------------------------------------------------------------------
# EXECUTION SERIALIZATION
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# CONVERSATION HELPERS
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# AGENT RUN
# ---------------------------------------------------------------------------

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

    staged_attachments: List[
        Dict[str, Any]
    ] = []

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
        # PREPARE ATTACHMENTS
        # ---------------------------------------------------------------

        prepared_context, staged_attachments = (
            _prepare_agent_context(
                context=request.context,
                objective=objective,
            )
        )

        planner_objective = str(
            prepared_context.get(
                "agent_objective",
                objective,
            )
        ).strip()

        # ---------------------------------------------------------------
        # PLAN
        # ---------------------------------------------------------------

        plan = agent_planner.create_plan(
            objective=planner_objective,
        )

        # ---------------------------------------------------------------
        # EXECUTE
        # ---------------------------------------------------------------

        executor = AgentExecutor(
            auto_confirm=request.auto_confirm,
        )

        execution = executor.execute(
            plan=plan,
            context=prepared_context,
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

        saved_user_message = add_message(
            db=db,
            conversation=conversation,
            role="user",
            content=objective,
            model=None,
        )

        # ---------------------------------------------------------------
        # SAVE ATTACHMENT REFERENCES
        # ---------------------------------------------------------------

        for attachment in _get_context_attachments(
            request.context
        ):
            try:
                file_data = load_chat_file(
                    attachment["file_id"]
                )
            except Exception:
                continue

            add_attachment(
                db=db,
                message=saved_user_message,
                file_id=file_data.get(
                    "file_id",
                    attachment["file_id"],
                ),
                filename=file_data.get(
                    "filename",
                    attachment.get(
                        "filename",
                        "Unknown file",
                    ),
                ),
                content_type=file_data.get(
                    "content_type",
                    attachment.get(
                        "content_type",
                        "",
                    ),
                ),
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

    finally:
        _cleanup_staged_files(
            staged_attachments
        )