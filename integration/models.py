from typing import Optional
from sqlmodel import SQLModel, Field


class ScoreCardBase(SQLModel):
    """
    ScoreCard Model Base
    """
    id: str = Field(nullable=False)
    account_unique_id: str = Field(foreign_key="account.account_unique_id")


class ScoreCardResult(ScoreCardBase, table=True):
    """
    Score Card Result Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(nullable=False)
    first_name: str = Field(nullable=True)
    last_name: str = Field(nullable=True)
    email: str = Field(nullable=True)
    key: str = Field(nullable=False)
    report_url: str = Field(nullable=False)
