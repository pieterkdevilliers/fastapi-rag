import httpx
import json
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from sqlmodel import Session
from chat_messages.utils import get_chat_messages_by_session_id
from core.models import ContactPayload, WebhookData, WebhookChatMessage


async def send_chat_messages_webhook_notification(account_unique_id: str, chat_session_id: int, payload: ContactPayload, webhook_url: str, session: Session):
    """
    Start webhook notification process
    """
    print('send_chat_messages_webhook_notification')
    await construct_chat_messages_webhook(account_unique_id=account_unique_id,
                                    chat_session_id=chat_session_id,
                                    payload=payload,
                                    webhook_url=webhook_url,
                                    session=session)


async def construct_chat_messages_webhook(account_unique_id: str, chat_session_id: int, payload: ContactPayload, webhook_url: str, session: Session):
    """
    Fetches the session messages and builds json for webhook
    """
    print('construct_chat_messages_webhook')
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

    webhook_payload = WebhookData(
        contact_info=payload,
        transcript=webhook_transcript,
        account_unique_id=account_unique_id
    )

    print('webhook_transcript: ', webhook_transcript)
    print('webhook_payload: ', webhook_payload)

    await send_webhook_notification(webhook_url, webhook_payload)

    return {"message": "Notification sent", "account_unique_id": account_unique_id}


async def send_webhook_notification(webhook_url: str, payload: WebhookData):
    """
    Sends a structured payload to a specified webhook URL.
    """
    print('send_webhook_notification')
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