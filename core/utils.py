from sqlmodel import select, Session
from core.models import Product
from accounts.models import StripeSubscription

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

def update_product_in_db(product_id: str, update_data: Product, session: Session):
    """
    Update Product in DB
    """
    product_in_db = session.exec(select(Product).where(Product.product_id == product_id)).first()

    if not product_in_db:
        return {"error": "Product not found"}

    updated_product_dict = update_data.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in updated_product_dict.items():
        setattr(product_in_db, key, value)
    session.add(product_in_db)
    session.commit()
    session.refresh(product_in_db)

    return product_in_db


def create_stripe_subscription_in_db(subscription: StripeSubscription, session: Session):
    """
    Create Stripe Subscription in DB
    """
    session.add(subscription)
    session.commit()
    session.refresh(subscription)

    return subscription
