import os
import stripe
from datetime import datetime, timezone
from sqlmodel import select, Session
from core.utils import create_product_in_db, update_product_in_db, create_stripe_subscription_in_db, update_stripe_subscription_in_db
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


def process_stripe_subscription_checkout_session_completed_event(event: dict, session: Session):
    """
    Process Stripe Subscription Checkout Session Completed Event
    """
    session_data = event.get('data', {}).get('object', {})
    stripe_customer_id = session_data.get('customer', '')
    stripe_subscription_id = session_data.get('subscription', '')
    account_unique_id = session_data.get('metadata', {}).get('account_unique_id', '')

    subscription = StripeSubscription(
        account_unique_id=account_unique_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_customer_id=stripe_customer_id
    )
    new_subscription = create_stripe_subscription_in_db(subscription, session)
    return new_subscription


def process_retrieved_stripe_subscription_data(subscription: dict, session: Session):
    """
    Process Retrieved Stripe Subscription Data
    """
    subscription_id = subscription['id']
    status = subscription['status']
    type = subscription['items']['data'][0]['price']['recurring']['interval']
    current_period_end = subscription['current_period_end']
    current_period_end = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    trial_start = datetime.fromtimestamp(subscription['trial_start'], tz=timezone.utc) if subscription['trial_start'] else None
    trial_end = datetime.fromtimestamp(subscription['trial_end'], tz=timezone.utc) if subscription['trial_end'] else None


    retrieved_subscription = StripeSubscription(
        stripe_subscription_id=subscription_id,
        status=status,
        current_period_end=current_period_end,
        trial_start=trial_start,
        trial_end=trial_end,
        type=type
    )
    # Update the subscription in the database
    updated_subscription = update_stripe_subscription_in_db(subscription_id, retrieved_subscription, session)

    return updated_subscription


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


def get_stripe_subscription_from_subscription_id(subscription_id: str):
    """
    Get Stripe Subscription from Subscription ID
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        if not subscription:
            return {"error": "Subscription not found"}
        return subscription
    except stripe.error.StripeError as e:
        return {"error": str(e)}


