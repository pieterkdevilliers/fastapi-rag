from sqlmodel import SQLModel, Field

class ProductBase(SQLModel):
    id: int
    product_title: str

class Product(ProductBase, table=True):
    """
    Product Model
    """
    product_id: str = Field(default="", primary_key=True)
    product_description: str = Field(default="")
    product_statement_descriptor: str = Field(default="")
    product_price: float = Field(default=0.0)
    product_plan_cycle: str = Field(default="")


