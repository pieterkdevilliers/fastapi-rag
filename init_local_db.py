# create_manual_local_db.py
from sqlmodel import SQLModel, Field, create_engine
from sqlalchemy import Column, JSON
from datetime import datetime, timezone
from typing import Optional, List

# -------------------------------
# Define all tables manually
# -------------------------------

# Account table
class Account(SQLModel, table=True):
    __tablename__ = "account"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_unique_id: str = Field(unique=True, nullable=False)
    account_organisation: str = Field(nullable=False)
    relevance_score: float = Field(default=0.7, nullable=True)
    k_value: int = Field(default=4, nullable=True)
    chunk_size: int = Field(default=1000, nullable=True)
    chunk_overlap: int = Field(default=200, nullable=True)
    webhook_url: Optional[str] = Field(default=None, nullable=True)

# User table
class User(SQLModel, table=True):
    __tablename__ = "user"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_email: str
    user_password: str
    account_unique_id: str = Field(foreign_key="account.account_unique_id")
    receive_notifications: bool = Field(default=False, nullable=True)

# WidgetAPIKey table
class WidgetAPIKey(SQLModel, table=True):
    __tablename__ = "widgetapikey"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_unique_id: str = Field(foreign_key="account.account_unique_id", index=True)
    name: Optional[str] = Field(default=None)
    display_prefix: Optional[str] = Field(default=None, index=True)
    api_key_hash: str = Field(unique=True, index=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    allowed_origins: List[str] = Field(default_factory=list, sa_column=Column(JSON))

# StripeSubscription table
class StripeSubscription(SQLModel, table=True):
    __tablename__ = "stripesubscription"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_unique_id: Optional[str] = Field(foreign_key="account.account_unique_id", nullable=True)
    stripe_subscription_id: str = Field(unique=True, index=True)
    stripe_customer_id: str = Field(unique=True, index=True)
    status: str = Field(default="active")
    current_period_end: Optional[datetime] = None
    type: Optional[str] = Field(default=None, index=True)
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    subscription_start: Optional[datetime] = None
    stripe_account_url: Optional[str] = Field(default=None, index=True)
    related_product_title: Optional[str] = None

# AccountPrompts table
DEFAULT_MAIN_PROMPT = """You are an expert analyst for a business..."""  # truncated for brevity

class AccountPrompts(SQLModel, table=True):
    __tablename__ = "accountprompts"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_unique_id: str = Field(foreign_key="account.account_unique_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prompt_key: str = Field(default="Main Prompt", nullable=False)
    prompt_text: str = Field(default=DEFAULT_MAIN_PROMPT, nullable=False)

# SourceFile table
class SourceFile(SQLModel, table=True):
    __tablename__ = "sourcefile"
    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    file_path: str
    included_in_source_data: bool = Field(default=False)
    original_filename: Optional[str] = None
    processing_status: Optional[str] = Field(default="PENDING")
    processing_error: Optional[str] = None
    already_processed_to_source_data: bool = Field(default=False)
    account_unique_id: str = Field(foreign_key="account.account_unique_id")
    folder_id: Optional[int] = Field(foreign_key="folder.id")

# Folder table
class Folder(SQLModel, table=True):
    __tablename__ = "folder"
    id: Optional[int] = Field(default=None, primary_key=True)
    folder_name: str = Field(default="New Folder", nullable=False, unique=True)
    account_unique_id: str = Field(foreign_key="account.account_unique_id")

# Product table
class Product(SQLModel, table=True):
    __tablename__ = "product"
    id: Optional[int] = Field(default=None, primary_key=True)
    product_title: str
    product_id: str = Field(default="", index=True, unique=True)
    product_description: str = Field(default="")
    product_statement_descriptor: str = Field(default="")
    product_price: float = Field(default=0.0)
    product_plan_cycle: str = Field(default="")
    price_id: Optional[str] = Field(default=None, index=True, nullable=True, unique=True)

# PasswordResetToken table
class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "passwordresettoken"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    token: str = Field(unique=True, index=True, nullable=False)
    expires_at: Optional[datetime] = None

# -------------------------------
# Create engine and tables
# -------------------------------
engine = create_engine("sqlite:///./source_db.db", echo=True)

# Only create tables that don't exist
SQLModel.metadata.create_all(engine)
print("All tables created (existing tables were skipped).")
