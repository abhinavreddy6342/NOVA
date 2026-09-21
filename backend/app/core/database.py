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
        # LEGACY USERS AUTH SCHEMA MIGRATION
        # ----------------------------------------------------

        # Earlier NOVA builds stored users with UUID primary keys
        # and without the name/role fields required by the current
        # cookie-session authentication model. Migrate the records
        # in-place and retain their conversation ownership.
        try:
            user_columns = conn.execute(
                text(
                    "PRAGMA table_info(users)"
                )
            ).fetchall()

            user_column_names = {
                row[1]
                for row in user_columns
            }

            legacy_user_ids = (
                user_columns
                and (
                    "name" not in user_column_names
                    or "role" not in user_column_names
                    or str(user_columns[0][2]).upper()
                    != "INTEGER"
                )
            )

            if legacy_user_ids:
                legacy_users = conn.execute(
                    text(
                        """
                        SELECT
                            id,
                            email,
                            password_hash,
                            is_active,
                            created_at
                        FROM users
                        ORDER BY created_at, id
                        """
                    )
                ).mappings().all()

                conn.execute(
                    text(
                        """
                        CREATE TABLE users_nova_migration (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            email VARCHAR(320) NOT NULL UNIQUE,
                            password_hash VARCHAR(255) NOT NULL,
                            name VARCHAR(200) NOT NULL,
                            role VARCHAR(50) NOT NULL DEFAULT 'user',
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            created_at DATETIME NOT NULL
                        )
                        """
                    )
                )

                for new_id, legacy_user in enumerate(
                    legacy_users,
                    start=1,
                ):
                    email = str(
                        legacy_user["email"]
                    )

                    conn.execute(
                        text(
                            """
                            INSERT INTO users_nova_migration (
                                id,
                                email,
                                password_hash,
                                name,
                                role,
                                is_active,
                                created_at
                            ) VALUES (
                                :id,
                                :email,
                                :password_hash,
                                :name,
                                'user',
                                :is_active,
                                :created_at
                            )
                            """
                        ),
                        {
                            "id": new_id,
                            "email": email,
                            "password_hash": legacy_user[
                                "password_hash"
                            ],
                            "name": email.split("@", 1)[0],
                            "is_active": legacy_user[
                                "is_active"
                            ],
                            "created_at": legacy_user[
                                "created_at"
                            ],
                        },
                    )

                    conn.execute(
                        text(
                            """
                            UPDATE conversations
                            SET user_id = :new_id
                            WHERE user_id = :legacy_id
                            """
                        ),
                        {
                            "new_id": new_id,
                            "legacy_id": legacy_user["id"],
                        },
                    )

                conn.execute(
                    text("DROP TABLE users")
                )

                conn.execute(
                    text(
                        """
                        ALTER TABLE users_nova_migration
                        RENAME TO users
                        """
                    )
                )

                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS ix_users_email
                        ON users(email)
                        """
                    )
                )

                print(
                    "NOVA migration: legacy users schema upgraded."
                )

        except Exception as exc:
            print(
                "NOVA migration notice (users): "
                f"{exc}"
            )

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
