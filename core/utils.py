from sqlmodel import select, Session
from core.models import Product

def create_product_in_db(product: Product, session: Session):
    """
    Save New Product to DB
    """
    existing_product = session.exec(
        select(Product).where(Product.product_id == product.product_id)
    ).first()
    if existing_product:
        return {"error": "Product with this ID already exists"}
    
    session.add(product)
    session.commit()
    session.refresh(product)
    
    return product

def update_product_in_db(product_id: str, product: Product, session: Session):
    """
    Update Product in DB
    """
    product = session.exec(select(Product).where(Product.product_id == product_id)).first()
    
    if not product:
        return {"error": "Product not found"}
    
    updated_product_dict = product.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in updated_product_dict.items():
        setattr(product, key, value)
    session.add(product)
    session.commit()
    session.refresh(product)
    
    return product

