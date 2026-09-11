from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.models import (
    ChatAttachment,
    ChatMessage,
    Conversation,
)


def create_conversation(
    db: Session,
    title: str = "New conversation",
) -> Conversation:
    conversation = Conversation(
        id=str(uuid4()),
        title=title,
        preview="",
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def get_conversation(
    db: Session,
    conversation_id: str,
):
    return (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id
        )
        .first()
    )


def list_conversations(
    db: Session,
):
    return (
        db.query(Conversation)
        .order_by(
            desc(Conversation.updated_at)
        )
        .all()
    )


def add_message(
    db: Session,
    conversation: Conversation,
    role: str,
    content: str,
    model: str | None = None,
):
    message = ChatMessage(
        id=str(uuid4()),
        conversation_id=conversation.id,
        role=role,
        content=content,
        model=model,
    )

    db.add(message)

    conversation.preview = (
        content[:180]
        if content
        else ""
    )

    db.commit()
    db.refresh(message)

    return message


def add_attachment(
    db: Session,
    message: ChatMessage,
    file_id: str,
    filename: str,
    content_type: str | None = None,
):
    attachment = ChatAttachment(
        id=str(uuid4()),
        message_id=message.id,
        file_id=file_id,
        filename=filename,
        content_type=content_type,
    )

    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment


def delete_conversation(
    db: Session,
    conversation_id: str,
) -> bool:
    conversation = get_conversation(
        db,
        conversation_id,
    )

    if not conversation:
        return False

    db.delete(conversation)
    db.commit()

    return True