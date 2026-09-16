from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATABASE_PATH = BASE_DIR / "nova.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


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


def init_db():
    """
    Initialize database tables and perform safe, idempotent migrations.
    Guarantees existing data is never reset or deleted.
    """
    from sqlalchemy import text

    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("PRAGMA table_info(chat_messages)")
            ).fetchall()
            columns = [row[1] for row in result]
            if columns and "agent_data" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE chat_messages ADD COLUMN agent_data TEXT;"
                    )
                )
                conn.commit()
        except Exception as exc:
            print(f"Idempotent migration notice: {exc}")


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()