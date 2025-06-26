from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class SourceFile(SQLModel, table=True):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_path: str
    included_in_source_data: bool = Field(default=False, nullable=True)
    original_filename: Optional[str] = Field(default=None) # To store the name of the file the user uploaded (e.g., "report.docx")
    processing_status: Optional[str] = Field(default="PENDING") # PENDING, PROCESSING, COMPLETED, FAILED
    processing_error: Optional[str] = Field(default=None) # To store error messages from Lambda
    already_processed_to_source_data: bool = Field(default=False, nullable=True)
    account_unique_id: str = Field(default=None, foreign_key="account.account_unique_id")
    account: "Account" = Relationship(back_populates="source_files")
    folder_id: Optional[int] = Field(default=None, foreign_key="folder.id")
    folder: "Folder" = Relationship(back_populates="source_files")


class Folder(SQLModel, table=True):
    """
    DB Table for Folders
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    folder_name: str = Field(nullable=False, unique=True, default='New Folder')
    account_unique_id: str = Field(default=None, foreign_key="account.account_unique_id")
    account: "Account" = Relationship(back_populates="folders")
    source_files: List["SourceFile"] = Relationship(back_populates="folder")

from accounts.models import Account

