from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class SourceFile(SQLModel, table=True):
    """
    DB Table for Source Files - Not the generated / chunked documents
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_path: str

    # Lazy import Account inside the class definition or function where needed
    def get_account(self):
        from accounts.models import Account
        return self.account
    
    account_unique_id: str = Field(default=None, foreign_key="account.account_unique_id")
    account: "Account" = Relationship(back_populates="source_files")


