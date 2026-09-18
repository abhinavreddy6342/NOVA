import json
import time
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import ChatAttachment
from app.services.chat_history import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)
from app.services.audit.service import (
    audit_service,
    create_request_id,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE_ROOT = (
    BACKEND_ROOT / "workspace"
).resolve()


router = APIRouter(
    prefix="/api/history",
    tags=["Chat History"],
)


def _duration_ms(start_time: float) -> float:
    return round(
        (time.perf_counter() - start_time) * 1000.0,
        2,
    )


def _safe_audit(
    *,
    status: str,
    category: str,
    action: str,
    service: str,
    message: str = "",
    duration_ms: float | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    metadata: dict | None = None,
):
    """
    Audit must never break the primary History API operation.
    """
    try:
        fields = {
            "category": category,
            "action": action,
            "service": service,
            "message": message,
            "duration_ms": duration_ms,
            "resource": resource,
            "resource_id": resource_id,
            "request_id": request_id,
            "metadata": metadata or {},
        }

        if status == "success":
            return audit_service.success(**fields)

        if status == "failed":
            return audit_service.failure(**fields)

    except Exception as exc:
        print(
            f"History audit recording failed: {exc}"
        )

    return None


@router.get("/conversations")
def get_conversations(
    db: Session = Depends(get_db),
):
    """
    Return all conversations ordered by latest activity.
    """
    conversations = list_conversations(db)

    return {
        "count": len(conversations),
        "conversations": [
            {
                "id": conversation.id,
                "title": conversation.title,
                "preview": conversation.preview,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
            }
            for conversation in conversations
        ],
    }


@router.post("/conversations")
def new_conversation(
    db: Session = Depends(get_db),
):
    """
    Create a new empty conversation.
    """
    started = time.perf_counter()
    request_id = create_request_id()

    try:
        conversation = create_conversation(db)

        _safe_audit(
            status="success",
            category="history",
            action="conversation_create",
            service="chat_history",
            message="Conversation created",
            duration_ms=_duration_ms(started),
            resource="conversation",
            resource_id=conversation.id,
            request_id=request_id,
            metadata={
                "title": conversation.title,
            },
        )

        return {
            "id": conversation.id,
            "title": conversation.title,
            "preview": conversation.preview,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        }

    except Exception as exc:
        _safe_audit(
            status="failed",
            category="history",
            action="conversation_create",
            service="chat_history",
            message="Conversation creation failed",
            duration_ms=_duration_ms(started),
            resource="conversation",
            request_id=request_id,
            metadata={
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise


def _verify_workspace_artifact(
    file_path: str,
) -> tuple[bool, int | None]:
    """
    Safely validate that a workspace-relative file path is inside
    the NOVA workspace and currently exists on disk.
    """
    if not file_path or not str(file_path).strip():
        return False, None

    clean_path = (
        str(file_path)
        .strip()
        .replace("\\", "/")
        .lstrip("/")
    )

    try:
        raw_p = Path(clean_path)

        if raw_p.is_absolute():
            resolved = raw_p.resolve()
        else:
            resolved = (
                WORKSPACE_ROOT / raw_p
            ).resolve()

        resolved.relative_to(WORKSPACE_ROOT)

        if resolved.exists() and resolved.is_file():
            return True, resolved.stat().st_size

    except Exception:
        pass

    return False, None


@router.get("/conversations/{conversation_id}")
def get_conversation_detail(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Return one conversation with all messages,
    attachments, and persisted agent metadata.
    """
    conversation = get_conversation(
        db,
        conversation_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    message_items = []

    for message in conversation.messages:
        attachments = (
            db.query(ChatAttachment)
            .filter(
                ChatAttachment.message_id == message.id
            )
            .all()
        )

        agent_data = None

        if (
            hasattr(message, "agent_data")
            and message.agent_data
        ):
            try:
                agent_data = json.loads(
                    message.agent_data
                )

                if isinstance(agent_data, dict):
                    artifacts = agent_data.get(
                        "artifacts",
                        [],
                    )

                    valid_artifacts = []

                    for artifact in artifacts:
                        if (
                            isinstance(artifact, dict)
                            and "file_path" in artifact
                        ):
                            clean_path = (
                                str(
                                    artifact["file_path"]
                                )
                                .replace("\\", "/")
                                .strip()
                                .lstrip("/")
                            )

                            if (
                                clean_path.startswith(
                                    "input/"
                                )
                                or clean_path.startswith(
                                    "workspace/input/"
                                )
                                or "input/" in clean_path
                            ):
                                continue

                            available, disk_size = (
                                _verify_workspace_artifact(
                                    artifact[
                                        "file_path"
                                    ]
                                )
                            )

                            artifact[
                                "available"
                            ] = available

                            if (
                                available
                                and disk_size is not None
                                and not artifact.get(
                                    "size_bytes"
                                )
                            ):
                                artifact[
                                    "size_bytes"
                                ] = disk_size

                            valid_artifacts.append(
                                artifact
                            )

                    agent_data[
                        "artifacts"
                    ] = valid_artifacts

            except Exception as exc:
                print(
                    f"Error parsing message agent_data: {exc}"
                )
                agent_data = None

        message_items.append(
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "model": message.model,
                "created_at": message.created_at,
                "attachments": [
                    {
                        "id": attachment.id,
                        "file_id": attachment.file_id,
                        "filename": attachment.filename,
                        "content_type": attachment.content_type,
                        "created_at": attachment.created_at,
                    }
                    for attachment in attachments
                ],
                "agent": agent_data,
            }
        )

    return {
        "id": conversation.id,
        "title": conversation.title,
        "preview": conversation.preview,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": message_items,
    }


@router.delete("/conversations/{conversation_id}")
def remove_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a conversation and its associated history.
    """
    started = time.perf_counter()
    request_id = create_request_id()

    try:
        deleted = delete_conversation(
            db,
            conversation_id,
        )

        if not deleted:
            _safe_audit(
                status="failed",
                category="history",
                action="conversation_delete",
                service="chat_history",
                message="Conversation deletion failed: conversation not found",
                duration_ms=_duration_ms(started),
                resource="conversation",
                resource_id=conversation_id,
                request_id=request_id,
                metadata={
                    "reason": "not_found",
                },
            )

            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        _safe_audit(
            status="success",
            category="history",
            action="conversation_delete",
            service="chat_history",
            message="Conversation deleted",
            duration_ms=_duration_ms(started),
            resource="conversation",
            resource_id=conversation_id,
            request_id=request_id,
        )

        return {
            "status": "deleted",
            "conversation_id": conversation_id,
        }

    except HTTPException:
        raise

    except Exception as exc:
        _safe_audit(
            status="failed",
            category="history",
            action="conversation_delete",
            service="chat_history",
            message="Conversation deletion failed",
            duration_ms=_duration_ms(started),
            resource="conversation",
            resource_id=conversation_id,
            request_id=request_id,
            metadata={
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise