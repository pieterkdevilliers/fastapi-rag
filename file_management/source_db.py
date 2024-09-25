from typing import Optional
from sqlmodel import SQLModel, Field, create_engine

# DB_FILE = "sqlite:///./source_db.db"
DB_FILE = "source_db.db"
engine = create_engine(f'sqlite:///{DB_FILE}', echo=True)


class SourceFileModel(SQLModel, table=True):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """
    __tablename__ = "sourcefile"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_path: str


def create_tables():
    """
    Create Tables
    """
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    # Creates DB Tables
    create_tables()
