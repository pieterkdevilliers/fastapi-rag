from typing import Optional
from sqlmodel import SQLModel, Field

class SourceFile(SQLModel, table=True):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_path: str