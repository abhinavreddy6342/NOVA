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


@router.get("/conversations/{conversation_id}")
def get_conversation_detail(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Return one conversation with all messages and attachments.
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