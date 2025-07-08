import os
import mailerlite as MailerLite

client = MailerLite.Client({
  'api_key': os.getenv("MAILERLITE_API_KEY")
})


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



