from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
)

DATABASE_PATH = BASE_DIR / "nova.db"

DATABASE_URL = (
    f"sqlite:///{DATABASE_PATH.as_posix()}"
)


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """
    Initialize NOVA database tables and perform safe,
    idempotent migrations.

    Existing data is never intentionally deleted or reset.
    """

    # Register all NOVA SQLAlchemy models before create_all().
    from app.core import models  # noqa: F401

    # Create tables that do not already exist.
    Base.metadata.create_all(
        bind=engine
    )

    with engine.begin() as conn:

        # ----------------------------------------------------
        # CHAT_MESSAGES MIGRATION
        # ----------------------------------------------------

        try:
            result = conn.execute(
                text(
                    "PRAGMA table_info(chat_messages)"
                )
            ).fetchall()

            columns = [
                row[1]
                for row in result
            ]

            if (
                columns
                and "agent_data" not in columns
            ):
                conn.execute(
                    text(
                        """
                        ALTER TABLE chat_messages
                        ADD COLUMN agent_data TEXT
                        """
                    )
                )

                print(
                    "NOVA migration: "
                    "chat_messages.agent_data added."
                )

        except Exception as exc:
            print(
                "NOVA migration notice "
                "(chat_messages): "
                f"{exc}"
            )

        # ----------------------------------------------------
        # CONVERSATIONS USER OWNERSHIP MIGRATION
        # ----------------------------------------------------

        try:
            result = conn.execute(
                text(
                    "PRAGMA table_info(conversations)"
                )
            ).fetchall()

            columns = [
                row[1]
                for row in result
            ]

            if (
                columns
                and "user_id" not in columns
            ):
                conn.execute(
                    text(
                        """
                        ALTER TABLE conversations
                        ADD COLUMN user_id INTEGER
                        """
                    )
                )

                print(
                    "NOVA migration: "
                    "conversations.user_id added."
                )

        except Exception as exc:
            print(
                "NOVA migration notice "
                "(conversations.user_id): "
                f"{exc}"
            )

        # ----------------------------------------------------
        # CONVERSATIONS USER INDEX
        # ----------------------------------------------------

        try:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS
                    ix_conversations_user_id
                    ON conversations(user_id)
                    """
                )
            )

        except Exception as exc:
            print(
                "NOVA migration notice "
                "(conversation user index): "
                f"{exc}"
            )


# ============================================================
# DATABASE SESSION
# ============================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()