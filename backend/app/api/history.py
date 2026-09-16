import json
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

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = (
    BACKEND_ROOT / "workspace"
).resolve()


router = APIRouter(
    prefix="/api/history",
    tags=["Chat History"],
)


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
    conversation = create_conversation(db)

    return {
        "id": conversation.id,
        "title": conversation.title,
        "preview": conversation.preview,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


def _verify_workspace_artifact(file_path: str) -> tuple[bool, int | None]:
    """
    Safely validate that a workspace-relative file path is inside
    the NOVA workspace and currently exists on disk.
    """
    if not file_path or not str(file_path).strip():
        return False, None

    clean_path = str(file_path).strip().replace("\\", "/").lstrip("/")

    try:
        raw_p = Path(clean_path)
        if raw_p.is_absolute():
            resolved = raw_p.resolve()
        else:
            resolved = (WORKSPACE_ROOT / raw_p).resolve()

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
    Return one conversation with all messages, attachments, and persisted agent metadata.
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
        if hasattr(message, "agent_data") and message.agent_data:
            try:
                agent_data = json.loads(message.agent_data)
                if isinstance(agent_data, dict):
                    artifacts = agent_data.get("artifacts", [])
                    valid_artifacts = []
                    for artifact in artifacts:
                        if isinstance(artifact, dict) and "file_path" in artifact:
                            clean_path = str(artifact["file_path"]).replace("\\", "/").strip().lstrip("/")
                            if clean_path.startswith("input/") or clean_path.startswith("workspace/input/") or "input/" in clean_path:
                                continue
                            available, disk_size = _verify_workspace_artifact(artifact["file_path"])
                            artifact["available"] = available
                            if available and disk_size is not None and not artifact.get("size_bytes"):
                                artifact["size_bytes"] = disk_size
                            valid_artifacts.append(artifact)
                    agent_data["artifacts"] = valid_artifacts
            except Exception as exc:
                print(f"Error parsing message agent_data: {exc}")
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
    deleted = delete_conversation(
        db,
        conversation_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return {
        "status": "deleted",
        "conversation_id": conversation_id,
    }