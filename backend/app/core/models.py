from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(
        String(36),
        primary_key=True,
    )

    title = Column(
        String(200),
        nullable=False,
        default="New conversation",
    )

    preview = Column(
        String(300),
        nullable=False,
        default="",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(
        String(36),
        primary_key=True,
    )

    conversation_id = Column(
        String(36),
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    role = Column(
        String(20),
        nullable=False,
    )

    content = Column(
        Text,
        nullable=False,
    )

    model = Column(
        String(120),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )


class ChatAttachment(Base):
    __tablename__ = "chat_attachments"

    id = Column(
        String(36),
        primary_key=True,
    )

    message_id = Column(
        String(36),
        ForeignKey(
            "chat_messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    file_id = Column(
        String(100),
        nullable=False,
    )

    filename = Column(
        String(500),
        nullable=False,
    )

    content_type = Column(
        String(150),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )