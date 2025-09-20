from typing import Generator, Iterator

from sqlmodel import SQLModel, create_engine, Session
from .config import Settings

settings = Settings()
engine = create_engine(settings.DATABASE_URL, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """SQLModel Session."""
    with Session() as session:
        yield session
