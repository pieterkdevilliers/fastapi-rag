from pydantic import BaseModel
from typing import Optional


class SourceFile(BaseModel):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """
    __tablename__ = "source_files"

    id: Optional[int] = None
    file_name: str
    file_path: str


