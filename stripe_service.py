import os
import stripe
from datetime import datetime, timezone
from sqlmodel import select, Session
from core.utils import create_product_in_db, update_product_in_db, create_stripe_subscription_in_db
from core.models import Product
from accounts.models import StripeSubscription

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


def get_stripe_customer_from_customer_id(customer_id: str):
    """
    Get Stripe Customer from Customer ID
    """
    try:
        customer = stripe.Customer.retrieve(customer_id)
        if not customer:
            return {"error": "Customer not found"}
        return customer
    except stripe.error.StripeError as e:
        return {"error": str(e)}


def process_stripe_subscription_created_event(event: dict, session: Session):
    """
    Process Stripe Subscription Created Event
    """
    
    subscription_data = event.get('data', {}).get('object', {})
    stripe_subscription_id = subscription_data.get('subscription', '')
    stripe_customer_id = subscription_data.get('customer', '')
    status = subscription_data.get('status', 'active')
    trial_start = subscription_data.get('trial_start', None)
    trial_end = subscription_data.get('trial_end', None)
    subscription_start = subscription_data.get('current_period_start', None)
    stripe_account_url = subscription_data.get('url', None)

    account_unique_id = get_stripe_customer_from_customer_id(stripe_customer_id).get('metadata', {}).get('account_unique_id', '')

    subscription = StripeSubscription(
        account_unique_id=account_unique_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id,
        status=status,
        trial_start=datetime.fromtimestamp(trial_start, tz=timezone.utc) if trial_start else None,
        trial_end=datetime.fromtimestamp(trial_end, tz=timezone.utc) if trial_end else None,
        subscription_start=datetime.fromtimestamp(subscription_start, tz=timezone.utc) if subscription_start else None,
        stripe_account_url=stripe_account_url
    )

    new_subscription = create_stripe_subscription_in_db(subscription, session)

    return new_subscription
