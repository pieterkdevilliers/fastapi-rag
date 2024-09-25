from typing import Optional
from sqlmodel import SQLModel, Field


class SourceFileModel(SQLModel, table=True):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """
    __tablename__ = "sourcefile"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_path: str


