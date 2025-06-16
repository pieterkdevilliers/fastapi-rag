import os
import stripe
from sqlmodel import select, Session
from core.utils import create_product_in_db, update_product_in_db
from core.models import Product

#Stripe Setup

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def process_stripe_product_created_event(event: dict, session: Session):
    """
    Process Stripe Product Created Event
    """
    
    product_data = event.get('data', {}).get('object', {})
    product_id = product_data.get('id', '')
    product_title = product_data.get('name', '')
    product_description = product_data.get('description', '')
    product_statement_descriptor = product_data.get('statement_descriptor', '')
    product_price = product_data.get('price', {}).get('unit_amount', 0) / 100.0  # Convert cents to dollars
    product_plan_cycle = product_data.get('recurring', {}).get('interval', '')
    price_id = product_data.get('default_price', '')

    product = Product(
        product_id=product_id,
        product_title=product_title,
        product_description=product_description,
        product_statement_descriptor=product_statement_descriptor,
        product_price=product_price,
        product_plan_cycle=product_plan_cycle,
        price_id=price_id
    )

    new_product = create_product_in_db(product, session)

    return new_product


def process_stripe_product_updated_event(event: dict, session: Session):
    """
    Process Stripe Product Updated Event
    """
    
    product_data = event.get('data', {}).get('object', {})
    product_id = product_data.get('id', '')
    product_title = product_data.get('name', '')
    product_description = product_data.get('description', '')
    product_statement_descriptor = product_data.get('statement_descriptor', '')
    product_price = product_data.get('price', {}).get('unit_amount', 0) / 100.0  # Convert cents to dollars
    product_plan_cycle = product_data.get('recurring', {}).get('interval', '')
    price_id = product_data.get('default_price', '')
    
    product = Product(
        product_id=product_id,
        product_title=product_title,
        product_description=product_description,
        product_statement_descriptor=product_statement_descriptor,
        product_price=product_price,
        product_plan_cycle=product_plan_cycle,
        price_id=price_id
    )

    updated_product = update_product_in_db(product_id, product, session)

    return updated_product


def get_stripe_price_object_from_price_id(price_id: str):
    """
    Get Price Object from Price ID
    """
    price_object = stripe.Price.retrieve(price_id)
    if not price_object:
        return {"error": "Price object not found"}
    return price_object
