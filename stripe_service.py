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


def process_stripe_subscription_invoice_paid_event(event: dict, session: Session):
    """
    Process Stripe Invoice Paid Event
    """
    invoice_data = event.get('data', {}).get('object', {})
    stripe_subscription_id = invoice_data.get('subscription', '')
    stripe_customer_id = invoice_data.get('customer', '')
    type = invoice_data.get('lines', {}).get('data', [{}])[0].get('price', {}).get('recurring', {}).get('interval', '')
    current_period_end = invoice_data.get('lines', {}).get('data', [{}])[0].get('period', {}).get('end', 0)
    current_period_end = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    subscription_start = invoice_data.get('lines', {}).get('data', [{}])[0].get('period', {}).get('start', 0)
    subscription_start = datetime.fromtimestamp(subscription_start, tz=timezone.utc)
    status = 'active'  # Assuming the status is active when the invoice is paid

    db_subscription = session.exec(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == stripe_subscription_id
        )
    ).first()

    if db_subscription:
        subscription = StripeSubscription(
        stripe_subscription_id=stripe_subscription_id,
        type=type,
        current_period_end=current_period_end,
        )

        updated_subscription = update_stripe_subscription_in_db(
            stripe_subscription_id, subscription, session
        )

        return updated_subscription
    else:

        subscription = StripeSubscription(
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            type=type,
            current_period_end=current_period_end,
            subscription_start=subscription_start,
            status=status
        )

        new_subscription = create_stripe_subscription_in_db(subscription, session)

        return new_subscription


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


def process_stripe_subscription_updated_event(event:dict, session: Session):
    """
    Update existing subscriptions stripe to database
    """
    subscription_data = event.get('data', {}).get('object', {})
    subscription_id = subscription_data.get('id', '')
    customer_id = subscription_data.get('customer', '')
    status = subscription_data.get('status', '')
    current_period_end = datetime.fromtimestamp(subscription_data.get('current_period_end', ''), tz=timezone.utc)
    trial_start = datetime.fromtimestamp(subscription_data.get('trial_start'), tz=timezone.utc) if subscription_data.get('trial_start') else None
    trial_end = datetime.fromtimestamp(subscription_data.get('trial_end'), tz=timezone.utc) if subscription_data.get('trial_end') else None

    stripe_subscription = StripeSubscription(
        stripe_subscription_id=subscription_id,
        stripe_customer_id=customer_id,
        status=status,
        current_period_end=current_period_end,
        trial_start=trial_start,
        trial_end=trial_end
    )

    updated_subscription = update_stripe_subscription_in_db(subscription_id, stripe_subscription, session)

    return updated_subscription


def process_stripe_subscription_deleted_event(event: dict, session: Session):
    """
    Update deleted subscriptions from Stripe to DB
    """
    subscription_data = event.get('data', {}).get('object', {})
    subscription_id = subscription_data.get('id', '')
    status = subscription_data.get('status', '')
    current_period_end = datetime.fromtimestamp(subscription_data.get('cancelled_at', ''), tz=timezone.utc)

    stripe_subscription = StripeSubscription(
        stripe_subscription_id=subscription_id,
        status=status,
        current_period_end=current_period_end,
    )

    deleted_subscription = update_stripe_subscription_in_db(subscription_id, stripe_subscription, session)

    return deleted_subscription


def add_account_unique_id_to_subscription(event: dict, session: Session):
    """
    Add account_unique_id to new subscription in db
    """
    subscription_data = event.get('data', {}).get('object', {})
    subscription_id = subscription_data.get('subscription', '')
    account_unique_id = subscription_data.get('metadata', {}).get('account_unique_id', '')

    stripe_subscription = StripeSubscription(
        account_unique_id = account_unique_id,
    )

    updated_subscription = update_stripe_subscription_in_db(subscription_id, stripe_subscription, session)

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


