import os
import mailerlite as MailerLite
from sqlmodel import Session
from accounts.utils import get_account_by_account_unique_id
from accounts.models import User


ACCOUNT_OWNERS_GROUP_ID = int(os.getenv("MAILERLITE_ACCOUNT_OWNERS_GROUP_ID"))
ACCOUNT_USERS_GROUP_ID = int(os.getenv("MAILERLITE_ACCOUNT_USERS_GROUP_ID"))
LEADS_NO_SUBSCRIPTION_GROUP_ID = int(os.getenv("MAILERLITE_LEADS_NO_SUBSCRIPTION_GROUP_ID"))
LEADS_NO_ACCOUNT_GROUP_ID = int(os.getenv("MAILERLITE_LEADS_NO_ACCOUNT_GROUP_ID"))
CUSTOMERS_CANCELLED_GROUP_ID = int(os.getenv("MAILERLITE_CUSTOMERS_CANCELLED_GROUP_ID"))
CUSTOMERS_ACTIVE_GROUP_ID = int(os.getenv("MAILERLITE_CUSTOMERS_ACTIVE_GROUP_ID"))

client = MailerLite.Client({
  'api_key': os.getenv("MAILERLITE_API_KEY")
})

############################################
# API Functions
############################################


############################################
# Subscriber Management
############################################

def add_subscriber(email: str, fields: dict = None):
    """
    Add a subscriber to MailerLite.

    :param email: The email address of the subscriber.
    :param fields: Additional fields for the subscriber (optional).
    :return: Response from MailerLite API.
    """

    response = client.subscribers.create(email, fields=fields)

    return response


def update_subscriber(email: str, fields: dict = None):
    """
    Update a subscriber in MailerLite.

    :param email: The email address of the subscriber.
    :param fields: Additional fields for the subscriber (optional).
    :return: Response from MailerLite API.
    """

    response = client.subscribers.update(email, fields=fields)

    return response


def get_subscriber(email: str):
    """
    Get a subscriber from MailerLite.

    :param email: The email address of the subscriber.
    :return: Response from MailerLite API.
    """

    response = client.subscribers.get(email)

    return response


def delete_subscriber(email: str):
    """
    Delete a subscriber from MailerLite.

    :param subscriber_id: The ID of the subscriber.
    :return: Response from MailerLite API.
    """

    subscriber = get_subscriber(email)
    if not subscriber:
        raise ValueError(f"Subscriber with email {email} not found.")
    if 'data' not in subscriber or 'id' not in subscriber['data']:
        raise ValueError(f"Unexpected response format for subscriber with email {email}.")
    
    subscriber_id = int(subscriber['data']['id'])
    
    print(f"DEBUG: Subscriber ID for email {email} is {subscriber_id}")
    
    if not subscriber_id:
        raise ValueError(f"Subscriber with email {email} not found.")

    response = client.subscribers.delete(subscriber_id)

    return response



def forget_subscriber(email: str):
    """
    Forget a subscriber in MailerLite.

    :param email: The email address of the subscriber.
    :return: Response from MailerLite API.
    """
    subscriber = get_subscriber(email)
    if not subscriber:
        raise ValueError(f"Subscriber with email {email} not found.")
    if 'data' not in subscriber or 'id' not in subscriber['data']:
        raise ValueError(f"Unexpected response format for subscriber with email {email}.")
    
    subscriber_id = int(subscriber['data']['id'])
    
    print(f"DEBUG: Subscriber ID for email {email} is {subscriber_id}")
    if not subscriber_id:
        raise ValueError(f"Subscriber with email {email} not found.")
    response = client.subscribers.forget(subscriber_id)

    return response


############################################
# Group Assignment Management
############################################

def assign_subscriber_to_group(email: str, group_id: int):
    """
    Add a subscriber to a group in MailerLite.

    :param email: The email address of the subscriber.
    :param group_id: The ID of the group to add the subscriber to.
    :return: Response from MailerLite API.
    """
    subscriber = get_subscriber(email)
    if not subscriber:
        raise ValueError(f"Subscriber with email {email} not found.")
    if 'data' not in subscriber or 'id' not in subscriber['data']:
        raise ValueError(f"Unexpected response format for subscriber with email {email}.")

    subscriber_id = int(subscriber['data']['id'])

    response = client.subscribers.assign_subscriber_to_group(subscriber_id, group_id)

    return response


def unassign_subscriber_from_group(email: str, group_id: int):
    """
    Remove a subscriber from a group in MailerLite.

    :param email: The email address of the subscriber.
    :param group_id: The ID of the group to remove the subscriber from.
    :return: Response from MailerLite API.
    """
    subscriber = get_subscriber(email)
    if not subscriber:
        raise ValueError(f"Subscriber with email {email} not found.")
    if 'data' not in subscriber or 'id' not in subscriber['data']:
        raise ValueError(f"Unexpected response format for subscriber with email {email}.")

    subscriber_id = int(subscriber['data']['id'])

    response = client.subscribers.unassign_subscriber_from_group(subscriber_id, group_id)

    return response


############################################
# Integration Utilities
############################################

def sync_to_mailerlite(email: str, account_unique_id: str, user_type: str, session: Session):
    """
    Sync a User to Mailerlite as a Subscriber
    Allows for First User as Account Owner
    """
    company = get_account_by_account_unique_id(account_unique_id, session).account_organisation
    fields = {
        "company": company,
        "account_unique_id": account_unique_id,}
    
    subscriber = add_subscriber(email=email, fields=fields)
    if not subscriber:
        raise ValueError(f"Failed to add subscriber with email {email} to MailerLite.")

    # Check if the user is the first user in the account
    if user_type == 'first_user':
        # Add the user to the account owners group
        assign_subscriber_to_group(email=email, group_id=ACCOUNT_OWNERS_GROUP_ID)
        assign_subscriber_to_group(email=email, group_id=LEADS_NO_SUBSCRIPTION_GROUP_ID)
        unassign_subscriber_from_group(email=email, group_id=LEADS_NO_ACCOUNT_GROUP_ID)
    else:
        # Add the user to the account users group
        assign_subscriber_to_group(email=email, group_id=ACCOUNT_USERS_GROUP_ID)


def delete_subscriber_from_mailerlite(user_id: int, account_unique_id: str, session: Session):
    """
    Delete a User from Mailerlite
    """
    user_email = session.get(User, user_id).user_email
    if not user_email:
        raise ValueError(f"User with ID {user_id} does not have an email address.")
    try:
        delete_subscriber(email=user_email)
    except ValueError as e:
        print(f"DEBUG: Error deleting subscriber {user_email} from MailerLite: {e}")
        return {"error": str(e)}
    return {"response": "success", "user_id": user_id}

