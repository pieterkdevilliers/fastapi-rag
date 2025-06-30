import httpx
import json
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from sqlmodel import Session
from main import WidgetEmailPayload
from chat_messages.utils import get_chat_messages_by_session_id
from accounts.utils import get_account_webhook_url

# A model for a single chat message in the webhook
class WebhookChatMessage(BaseModel):
    timestamp: datetime
    sender_type: str
    message_text: str

# The main payload for your webhook
class WebhookPayload(BaseModel):
    contact_info: WidgetEmailPayload # Re-use the existing model for contact details
    transcript: Optional[List[WebhookChatMessage]] = None
    account_unique_id: str


def send_chat_messages_webhook_notification(account_unique_id: str, chat_session_id: int, payload: WidgetEmailPayload, webhook_url: str, session: Session):
    """
    Start webhook notification process
    """
    construct_chat_messages_webhook(account_unique_id=account_unique_id,
                                    chat_session_id=chat_session_id,
                                    payload=payload,
                                    webhook_url=webhook_url,
                                    session=session)


async def construct_chat_messages_webhook(account_unique_id: str, chat_session_id: int, payload: WidgetEmailPayload, webhook_url: str, session: Session):
    """
    Fetches the session messages and builds json for webhook
    """
    chat_messages = get_chat_messages_by_session_id(
        chat_session_id=chat_session_id,
        session=session
    )

    webhook_transcript = [
        WebhookChatMessage(
            timestamp=msg.timestamp,
            sender_type=msg.sender_type,
            message_text=msg.message_text
        ) for msg in chat_messages
    ] if chat_messages else None

    webhook_payload = WebhookPayload(
        contact_info=payload,
        transcript=webhook_transcript,
        account_unique_id=account_unique_id
    )

    

    await send_webhook_notification(webhook_url, webhook_payload)

    return {"message": "Notification sent", "account_unique_id": account_unique_id}


async def send_webhook_notification(webhook_url: str, payload: WebhookPayload):
    """
    Sends a structured payload to a specified webhook URL.
    """
    if not webhook_url:
        return

    print(f"Sending webhook notification to {webhook_url}")
    
    # Use httpx for async HTTP requests
    async with httpx.AsyncClient() as client:
        try:
            # .dict() is deprecated, use .model_dump() with mode='json'
            # to ensure types like datetime are properly serialized.
            payload_data = payload.model_dump(mode="json")

            response = await client.post(
                webhook_url,
                json=payload_data,
                headers={"Content-Type": "application/json"},
                timeout=10.0, # Set a reasonable timeout
            )
            
            # Raise an exception for 4xx or 5xx status codes
            response.raise_for_status() 
            print(f"Webhook sent successfully to {webhook_url}. Status: {response.status_code}")

        except httpx.RequestError as e:
            # Catches connection errors, timeouts, etc.
            print(f"ERROR: Could not send webhook to {webhook_url}. Error: {e}")
        except Exception as e:
            # Catch other potential errors
            print(f"ERROR: An unexpected error occurred during webhook sending. Error: {e}")