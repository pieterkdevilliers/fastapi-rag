from typing import Optional
from sqlmodel import SQLModel, Field


class ScoreCardBase(SQLModel):
    """
    ScoreCard Model Base
    """
    id: int = Field(primary_key=True)  # make this the PK
    account_unique_id: str = Field(foreign_key="account.account_unique_id")


class ScoreCardResult(ScoreCardBase, table=True):
    """
    Score Card Result Model
    """
    status: str = Field(nullable=False)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    key: str = Field(nullable=False)
    report_url: str = Field(nullable=False)
    result_id: str = Field(nullable=False)


class ScoreAppAccountBase(SQLModel):
    """
    ScoreApp Account Base Model
    """
    scoreapp_id: str = Field(nullable=False)  # Renamed to avoid conflict
    account_unique_id: str = Field(foreign_key="account.account_unique_id")


class ScoreAppAccount(ScoreAppAccountBase, table=True):
    """
    ScoreApp Account Model
    """
    __tablename__ = "scoreapp_account"  # Explicit table name
    
    id: Optional[int] = Field(default=None, primary_key=True)
