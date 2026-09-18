from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
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


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    email = Column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    role = Column(
        String(50),
        nullable=False,
        default="user",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    conversations = relationship(
        "Conversation",
        back_populates="user",
        passive_deletes=True,
    )


# ============================================================
# CONVERSATION
# ============================================================

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(
        String(36),
        primary_key=True,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
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

    user = relationship(
        "User",
        back_populates="conversations",
    )

    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


# ============================================================
# CHAT MESSAGE
# ============================================================

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

    agent_data = Column(
        Text,
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


# ============================================================
# CHAT ATTACHMENT
# ============================================================

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