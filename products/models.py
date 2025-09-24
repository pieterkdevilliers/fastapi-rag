from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, List
from sqlmodel import Field, SQLModel, Relationship, Column
from sqlalchemy import JSON
import uuid
# Conditional import for type checking
if TYPE_CHECKING:
    from accounts.models import Account

class UserProductBase(SQLModel):
    """
    User Product Model Base
    """
    account_unique_id: str = Field(foreign_key="account.account_unique_id")


class UserProduct(UserProductBase, table=True):
    """
    User Product Model
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    account: "Account" = Relationship(back_populates="products")
    product_title: str = Field(default=None, nullable=False)
    product_description: str = Field(default=None, nullable=False)
    product_sale_url: str = Field(default=None, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    who_is_this_for: str = Field(default=None, nullable=False)