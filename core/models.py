from sqlmodel import SQLModel, Field
from typing import Optional

class ProductBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_title: str

class Product(ProductBase, table=True):
    """
    Product Model
    """
    __tablename__ = "product"
    
    product_id: str = Field(default="", index=True, unique=True)
    product_description: str = Field(default="")
    product_statement_descriptor: str = Field(default="")
    product_price: float = Field(default=0.0)
    product_plan_cycle: str = Field(default="")
    price_id: Optional[str] = Field(default=None, index=True, nullable=True, unique=True)


