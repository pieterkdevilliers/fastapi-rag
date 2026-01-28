import io
import os
import uuid
from dotenv import load_dotenv
load_dotenv()
from io import BytesIO
import json
import tempfile
import stripe
import secrets
from bs4 import BeautifulSoup
from typing import Any, Union, Annotated, List, Optional, Dict
from datetime import datetime, timezone
from secrets import token_hex
import shutil
import boto3
import convert_to_pdf
from sqlmodel import SQLModel
from mailerlite_services import sync_to_mailerlite, delete_subscriber_from_mailerlite, update_active_customer_groups, update_subscriber, update_cancelled_customer_groups, add_subscriber, assign_subscriber_to_group, get_subscriber
from aws_ses_service import EmailService, get_email_service
from datetime import timedelta
from fastapi import FastAPI, UploadFile, Depends, File, Body, HTTPException, status, Request, Security, responses, APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import select, Session, Field
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from pydantic import BaseModel, EmailStr, Field
from file_management.models import SourceFile, Folder
from file_management.utils import save_file_to_db, update_file_in_db, delete_file_from_db, \
    fetch_html_content, extract_text_from_html, prepare_for_s3_upload, create_new_folder_in_db, \
    update_folder_in_db, delete_folder_from_db, delete_file_from_s3, get_docs_count_for_user_account, load_documents_from_s3, \
    create_pending_file_in_db, get_processed_docs_count_for_user_account
import file_management.utils as file_utils
from accounts.models import Account, User, WidgetAPIKey, StripeSubscription, AccountPrompts, WidgetConfig
from accounts.utils import create_new_account_in_db, update_account_in_db, delete_account_from_db, \
    create_new_user_in_db, update_user_in_db, delete_user_from_db, get_notification_users, get_user_by_email, \
    create_password_reset_token, get_reset_token, update_user_password, delete_reset_token, get_account_by_account_unique_id, \
    check_active_subscription_status, get_account_webhook_url, create_account_prompt, get_account_prompts, get_most_recent_prompt, \
    get_account_prompt_by_id, get_opt_in_webhook_url

import accounts.utils as account_utils
from db import engine
import query_data.query_source_data as query_source_data
from authentication import oauth2_scheme, Token, authenticate_user, get_password_hash, create_access_token, \
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES, get_widget_api_key_user, get_api_key_hash, get_api_key, get_internal_api_key
from dependencies import get_session
from chat_messages.models import ChatSession, ChatMessage
from chat_messages.utils import create_or_identify_chat_session, create_chat_message, get_session_id_by_visitor_uuid, \
    get_chat_messages_by_session_id, get_chat_session_count, get_questions_answered_count, create_email_message, \
    get_email_message_count, update_session_with_contact_details
import chat_messages.utils as chat_utils
from stripe_service import process_stripe_product_created_event, process_stripe_product_updated_event, get_stripe_price_object_from_price_id, \
    process_stripe_subscription_checkout_session_completed_event, get_stripe_subscription_from_subscription_id, \
    process_retrieved_stripe_subscription_data, process_stripe_subscription_invoice_paid_event, add_account_unique_id_to_subscription, \
    process_stripe_subscription_updated_event, process_stripe_subscription_deleted_event, process_in_app_subscription_cancellation, \
    get_stripe_customer_from_customer_id
from core.models import Product, PasswordResetToken, ContactPayload, OptInPayload
from core.utils import create_stripe_subscription_in_db, get_db_subscription_by_subscription_id, update_stripe_subscription_in_db
from pinecone_db_utils import check_pinecone_namespace_status, clear_pinecone_namespace_for_replace, delete_chunks_from_pinecone
from webhook_utils import send_chat_messages_webhook_notification, send_opt_in_webhook_notification
import integration.utils as int_utils
from integration.models import ScoreAppAccount, ScoreCardResult
import products.utils as prod_utils
import query_data.utils as query_utils
from query_data.query_data_schema import Query
from wordcloud import WordCloud
import aws_s3_services as s3_services


# Initialize the S3 client
s3 = boto3.client('s3')

#Stripe Setup
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# The name of your S3 bucket
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
lambda_client = boto3.client("lambda", region_name="us-east-1")

# Front-end Env Settings
FE_BASE_URL = os.getenv('FE_BASE_URL', 'http://localhost:3000')  # Default to localhost if not set

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

############################################
#  Authentication
############################################

@app.get("/api/v1/root")
async def read_root(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Root Route
    """
    return {"token": token}
    

@app.post("/api/v1/token")
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                 session: Session = Depends(get_session)) -> Token:
    """
    Login for Access Token
    """
    user = authenticate_user(form_data.username.lower(), form_data.password, session=session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['user_email']}, expires_delta=access_token_expires
    )

    account_unique_id = user.get('account_unique_id')
    organisation = get_account_by_account_unique_id(account_unique_id, session).account_organisation
    docs_count = get_docs_count_for_user_account(account_unique_id, session)
    processed_docs_count = get_processed_docs_count_for_user_account(account_unique_id, session)
    active_subscription = check_active_subscription_status(account_unique_id, session)
    is_account_owner = user.get('is_account_owner')

    account_prompts = get_account_prompts(account_unique_id, session)
    if not account_prompts:
        # Create a default prompt if none exist
        default_prompt = create_account_prompt(
            account_unique_id=account_unique_id,
            prompt_key="Main Prompt",
            prompt_text=None,
            session=session
        )
        account_prompts = [default_prompt]

    return Token(account_unique_id=account_unique_id, account_organisation=organisation, docs_count=docs_count, active_subscription=active_subscription, processed_docs_count=processed_docs_count, access_token=access_token, is_account_owner=is_account_owner, token_type="bearer")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr 


@app.post("/api/v1/forgot-password", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request_data: ForgotPasswordRequest,
    session: Session = Depends(get_session),
    email_service: EmailService = Depends(get_email_service)
    ):
    """
    Serves the Password Reset Step 1"""
    user = get_user_by_email(email=request_data.email, session=session)
    
    # IMPORTANT: To prevent user enumeration, always return a success message.
    if user:
        # 1. Generate a secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1) # Token valid for 1 hour

        # 2. Store the token in the database
        create_password_reset_token(user_id=user.id, token=token, expires_at=expires_at, session=session)

        # 3. Send the email
        reset_link = f"{FE_BASE_URL}/reset-password?token={token}"

        try:
            # This is now much cleaner and more descriptive!
            email_service.send_password_reset_email(
                to_email=user.user_email,
                reset_link=reset_link
            )
        except Exception as e:
            print(f"ERROR: Could not send password reset email to {user.user_email}. Error: {e}")
            return {"message": "If an account with that email exists, a password reset link has been sent."}

    return {"message": "If an account with that email exists, a password reset link has been sent."}


class TokenValidateRequest(BaseModel):
    token: str

@app.post("/api/v1/validate-token", status_code=status.HTTP_200_OK)
async def validate_reset_token(
    request_data: TokenValidateRequest,
    session: Session = Depends(get_session),
    ):
    """
    Serves the Password Reset Step 2"""
    token_record = get_reset_token(token=request_data.token, session=session)
    if not token_record or token_record.is_expired():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is invalid or has expired.",
        )
    return {"message": "Token is valid."}


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@app.post("/api/v1/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: ResetPasswordRequest,
    session: Session = Depends(get_session),
    ):
    token_record = get_reset_token(token=request.token, session=session)

    # 1. Re-validate the token
    if not token_record or token_record.is_expired():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is invalid or has expired.",
        )

    # 2. Get the user and update their password
    user_id = token_record.user_id
    update_user_password(user_id=user_id, password=request.new_password, session=session)

    # 3. Invalidate the token by deleting it
    delete_reset_token(token_record=token_record, session=session)

    return {"message": "Password has been successfully reset."}


############################################
#  State Management
############################################


@app.get("/api/v1/get-docs-count/{account_unique_id}")
async def get_docs_count(account_unique_id: str,
                          current_user: Annotated[User, Depends(get_current_active_user)],
                          session: Session = Depends(get_session)) -> dict[str, Any]:
    
    docs_count = get_docs_count_for_user_account(account_unique_id, session)

    return {"docs_count": docs_count}

############################################
#  API Key Management
############################################

class APIKeyCreateRequest(BaseModel):
    name: str
    allowed_origins: List[str]
    button_text: str
    widget_title: str
    welcome_message: str
    opt_in_required: bool

@app.post("/api/v1/create-api-key/{account_unique_id}")
async def create_api_key(
                        account_unique_id: str,
                        api_key_create_request: APIKeyCreateRequest,
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Create API Key
    """
    # Your logic to create an API key
    api_key = token_hex(32)  # Generate a secure random API key
    display_prefix = api_key[:8]  # Use the first 8 characters as the display prefix
    api_key_hash = get_api_key_hash(api_key)  # Generate a secure random API key hash
    new_api_key = WidgetAPIKey(account_unique_id=account_unique_id,
                               name=api_key_create_request.name,
                               allowed_origins=api_key_create_request.allowed_origins,
                               api_key_hash=api_key_hash,
                               display_prefix=display_prefix)
    session.add(new_api_key)
    session.commit()

    new_widget_config = WidgetConfig(
        widget_id=new_api_key.id,
        account_unique_id=account_unique_id,
        button_text=api_key_create_request.button_text,
        widget_title=api_key_create_request.widget_title,
        welcome_message=api_key_create_request.welcome_message,
        opt_in_required=api_key_create_request.opt_in_required)
    
    session.add(new_widget_config)
    session.commit()
    
    return {"api_key": api_key, "account_unique_id": account_unique_id, "allowed_origins": api_key_create_request.allowed_origins}


class WidgetAPIKeyWithConfig(SQLModel):
    """Response model for API key with its configuration"""
    id: int
    name: Optional[str]
    display_prefix: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool
    allowed_origins: List[str]
    widget_config: Optional[WidgetConfig] = None

@app.get("/api/v1/list-api-keys/{account_unique_id}")
async def list_api_keys(account_unique_id: str,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)) -> dict[str, List[WidgetAPIKeyWithConfig]]:
    """
    List API Keys with their configurations
    """
    # Get API keys
    api_keys_stmt = select(WidgetAPIKey).where(WidgetAPIKey.account_unique_id == account_unique_id)
    api_keys = session.exec(api_keys_stmt).all()
    
    # Get configs for these API keys
    api_key_ids = [key.id for key in api_keys]
    configs_stmt = select(WidgetConfig).where(WidgetConfig.widget_id.in_(api_key_ids))
    configs = session.exec(configs_stmt).all()
    
    # Create a mapping of widget_id to config
    config_map = {config.widget_id: config for config in configs}
    
    # Combine the data
    result = []
    for api_key in api_keys:
        widget_config = config_map.get(api_key.id)
        combined = WidgetAPIKeyWithConfig(
            id=api_key.id,
            name=api_key.name,
            display_prefix=api_key.display_prefix,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            is_active=api_key.is_active,
            allowed_origins=api_key.allowed_origins,
            widget_config=widget_config
        )
        result.append(combined)
    
    return {"api_keys": result}


@app.delete("/api/v1/delete-api-key/{account_unique_id}/{api_key_id}")
async def delete_api_key(account_unique_id: str,
                          api_key_id: str,
                          current_user: Annotated[User, Depends(get_current_active_user)],
                          session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Delete API Key
    """
    statement = select(WidgetAPIKey).where(WidgetAPIKey.id == api_key_id, WidgetAPIKey.account_unique_id == account_unique_id)
    result = session.exec(statement)
    api_key = result.first()
    if not api_key:
        return {"error": "API Key not found"}
    
    config_statement = select(WidgetConfig).where(WidgetConfig.widget_id == api_key_id)
    config_result = session.exec(config_statement)
    widget_config = config_result.first()

    if not widget_config:
        pass

    else:
        session.delete(widget_config)
        session.commit()

    session.delete(api_key)
    session.commit()

    return {"message": "API Key deleted successfully"}


class APIKeyUpdateRequest(BaseModel):
    name: str = None
    allowed_origins: List[str] = None
    theme_colour: str = None
    button_text: str = None
    widget_title: str = None
    welcome_message: str = None
    opt_in_required: bool = False


@app.put("/api/v1/update-api-key/{account_unique_id}/{api_key_id}")
async def update_api_key(account_unique_id: str,
                         current_user: Annotated[User, Depends(get_current_active_user)],
                         api_key_id: str,
                         api_key_update_request: APIKeyUpdateRequest,
                         session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Update API Key
    """
    statement = select(WidgetAPIKey).where(WidgetAPIKey.id == api_key_id)
    result = session.exec(statement)
    api_key = result.first()
    
    if not api_key:
        return {"error": "API Key not found"}
    
    if api_key_update_request.name is not None:
        api_key.name = api_key_update_request.name
    if api_key_update_request.allowed_origins is not None:
        api_key.allowed_origins = api_key_update_request.allowed_origins

    session.add(api_key)
    session.commit()

    config_statement = select(WidgetConfig).where(WidgetConfig.widget_id == api_key_id)
    config_result = session.exec(config_statement)
    widget_config = config_result.first()

    if not widget_config:
        pass

    else:
        widget_config.button_text = api_key_update_request.button_text
        widget_config.theme_colour = api_key_update_request.theme_colour
        widget_config.widget_title = api_key_update_request.widget_title
        widget_config.welcome_message = api_key_update_request.welcome_message
        widget_config.opt_in_required = api_key_update_request.opt_in_required

        session.add(widget_config)
        session.commit()
    
    return {"message": "API Key updated successfully", "api_key": api_key, "widget_config": widget_config}


############################################
# Integration Routes
############################################


@app.post("/api/v1/create-score-app-account/{account_unique_id}/{scoreapp_id}")
async def create_score_app_account(
                        account_unique_id: str,
                        scoreapp_id: str,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Create ScoreApp Account
    """

    new_score_app_account = ScoreAppAccount(account_unique_id=account_unique_id,
                               scoreapp_id=scoreapp_id)
    session.add(new_score_app_account)
    session.commit()
    
    return {"scoreapp_id": scoreapp_id, "account_unique_id": account_unique_id}


@app.get("/api/v1/score-app-account/{account_unique_id}")
async def get_score_app_account(account_unique_id: str,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Get Account Score App Account
    """
    account = await int_utils.get_score_app_account(account_unique_id, session)
    if not account:
        account = {}
    widget_key = os.getenv("SCOREAPP_WEBHOOK_SECRET_KEY")
    return {"account": account, "widget_key": widget_key}


class ScoreAppUpdate(BaseModel):
    scoreapp_id: str

@app.put("/api/v1/score-app-account/{account_id}")
async def update_score_app_account(
    account_id: int,
    update_data: ScoreAppUpdate,  # Accept as JSON body
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> dict[str, Any]:
    """
    Edit Account Score App Subdomain
    """
    updated_account = await int_utils.update_scoreapp_account_in_db(
        account_id, 
        update_data.scoreapp_id,  # Access from the model
        session
    )
    if not updated_account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {"updated_account": updated_account}


@app.delete("/api/v1/score-app-account/{scoreapp_id}")
async def delete_score_app_account(scoreapp_id: str,
                          current_user: Annotated[User, Depends(get_current_active_user)],
                          session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Delete ScoreApp Account Key
    """
    response = await int_utils.delete_scoreapp_account_from_db(scoreapp_id, session)

    return response


@app.post("/api/v1/score-card-result")
async def add_score_card_result(request: Request, session: Session = Depends(get_session)):
    """
    Validate and create a scorecard result in the db
    """
    signature = request.headers.get("Scoreapp-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature header")

    body_bytes = await request.body()
    
    # Validate signature
    validation_status = int_utils.validate_webhook_signature(signature, body_bytes)

    if validation_status:
        # Parse JSON from the stored bytes
        try:
            webhook_data = json.loads(body_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
        print("Full Request Body:", webhook_data)
        
        # Extract event name from the root level
        event_name = webhook_data.get("event_name")
        
        # Extract the nested data object
        nested_data = webhook_data.get("data", {})
        
        # Get report URL from the nested data (not from root)
        report_url = nested_data.get("report", "")
        if report_url:
            account_unique_id = await int_utils.get_account_unique_id(report_url, session)
            print(f"Account ID: {account_unique_id}")

        if event_name == "QUIZ_STARTED":
            print("Processing: Quiz Started")
            score_card_result = await int_utils.create_score_card_result(nested_data, account_unique_id, session)
            print("score_card_result: ", score_card_result)
            
        elif event_name == "QUIZ_FINISHED":
            print("Processing: Quiz Finished")
            # Access nested data correctly
            result_id = nested_data.get("result_id")
            score_card_result = await int_utils.create_or_update_score_card_result(result_id, nested_data, account_unique_id, session)
            extracted_text = await int_utils.trigger_extraction(score_card_result.id, lambda_client)
            print("score_card_result: ", score_card_result)
            
        elif event_name == "LEAD_DETAILS_UPDATED":
            print("Processing: Lead Details Updated")
            # Add your lead updated logic here
            
        elif event_name == "LEAD_SIGNED_UP":
            print("Processing: Lead Signed Up")
            # Add your lead signup logic here

    return {"status": "ok"}


@app.post("/api/v1/internal/scorecardresult/callback")
async def scorecardresult_callback(
    request: Request, session: Session = Depends(get_session)
):
    # Verify internal key
    api_key = request.headers.get("X-Internal-API-Key")
    if api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = await request.json()
    id = payload.get("scorecard_id")

    result = session.get(ScoreCardResult, id)
    if not result:
        raise HTTPException(status_code=404, detail="ScorecardResult not found")

    if payload["status"] == "COMPLETED":
        result.extracted_report_text = payload.get("extracted_report_text")
    else:
        result.extracted_report_text = f"[ERROR] {payload.get('error_message')}"

    session.add(result)
    session.commit()
    return {"status": "updated", "scorecard_id": id}

############################################
# Main Routes
############################################


@app.get("/api/v1/query-data/{account_unique_id}")
async def query_data(query: str, account_unique_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Query Data
    """
    if not query:
        return {"error": "No query provided"}

    response = query_source_data.query_source_data(query, account_unique_id, session)
    return response


class WidgetQueryPayload(BaseModel):
    query: str
    chat_session_id: int
    visitor_uuid: str
    email: Optional[str] = None



# Queries received from the web widget
@app.post("/api/v1/widget/query")
async def process_widget_query(
    payload: WidgetQueryPayload,
    auth_info: dict = Security(get_widget_api_key_user),
    session: Session = Depends(get_session)
):
    account_unique_id = auth_info["account_unique_id"]
    query = payload.query.strip() if payload.query else None
    visitor_email = payload.email if payload.email else None
    print('******Payload: ', payload)

    if not query:
        return {"error": "No query provided"}

    # Identify the chat session
    try:
        chat_session = create_or_identify_chat_session(
            account_unique_id,
            payload.visitor_uuid,
            session
        )
    except Exception as e:
        print(f"Error creating/identifying chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to identify chat session")

    # Pull chat history for context
    chat_history = session.exec(
        select(ChatMessage)
        .where(ChatMessage.chat_session_id == chat_session.id)
        .order_by(ChatMessage.timestamp)
    ).all()

    # Add the new user query to chat history
    chat_history.append(
        {"sender_type": "user", "message_text": query, "sources": []}
    )

    # Now feed `chat_history` into your query_source_data function
    active_subscription = check_active_subscription_status(account_unique_id, session)
    if active_subscription:
        response = query_source_data.query_source_data(
            query, visitor_email, account_unique_id, session, chat_history=chat_history
        )
    else:
        # Handle unsubscribed users
        recipients = get_notification_users(account_unique_id, session)
        if not recipients:
            raise HTTPException(status_code=404, detail="No notification users found for this account")

        email_service = get_email_service()
        try:
            for recipient in recipients:
                email_service.send_unsubscribed_widget_email(
                    recipient['user_email'],
                    'www.expertecho.ai/login?redirect=/accounts'
                )
        except Exception as e:
            print(f"ERROR sending email: {e}") 
            raise HTTPException(status_code=500, detail=str(e))

        response = {
            "response": {
                "response_text": "Unable to process your query at this time, please contact us via email."
            }
        }

    return response


# Queries received from the in-app test widget
@app.post("/api/v1/internal/widget/query")
async def process_internal_widget_query(
    payload: WidgetQueryPayload,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
):
    account_unique_id = current_user["account_unique_id"]
    query = payload.query.strip() if payload.query else None
    visitor_email = current_user["user_email"]
    print('******Payload: ', payload)


    if not query:
        return {"error": "No query provided"}

    # Identify the chat session
    try:
        chat_session = create_or_identify_chat_session(
            account_unique_id,
            payload.visitor_uuid,
            session
        )
    except Exception as e:
        print(f"Error creating/identifying chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to identify chat session")

    # Pull chat history for context
    chat_history = session.exec(
        select(ChatMessage)
        .where(ChatMessage.chat_session_id == chat_session.id)
        .order_by(ChatMessage.timestamp)
    ).all()

    # Add the new user query to chat history
    chat_history.append(
        {"sender_type": "user", "message_text": query, "sources": []}
    )

    # Now feed `chat_history` into your query_source_data function
    response = query_source_data.query_source_data(
            query, visitor_email, account_unique_id, session, chat_history=chat_history
        )

    return response


############################################################################
# ExpertEcho Agents Endpoints
############################################################################

# REINSTATE API AUTH BEFORE DEPLOYING AS LIVE #
# REMOVE UNIQUE_ACCOUNT_ID FROM ENDPOINT AND DIRECT SET #
# DISABLE DEFAULT ACTIVE_SUBSCRIPTION #


@app.post("/api/v1/widget/query-agent")
async def process_widget_query_agent(
    payload: WidgetQueryPayload,
    auth_info: dict = Security(get_widget_api_key_user),
    session: Session = Depends(get_session)
):
    account_unique_id = auth_info["account_unique_id"]
    account = get_account_by_account_unique_id(account_unique_id, session)
    query = payload.query.strip() if payload.query else None

    if not query:
        return {"error": "No query provided"}

    # Identify the chat session
    try:
        chat_session = create_or_identify_chat_session(
            account_unique_id,
            payload.visitor_uuid,
            session
        )
        print("Chat Session: ", chat_session)
    except Exception as e:
        print(f"Error creating/identifying chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to identify chat session")

    # Pull chat history for context
    chat_history = get_chat_messages_by_session_id(chat_session.id, session)
    chat_history_dicts = [
        {
            "sender": msg.sender_type,       # matches repo B
            "message": msg.message_text,     # matches repo B
        }
        for msg in chat_history
    ]

    chat_history_dicts.append({
        "sender": "user",
        "message": query,
    })
    
    scoreapp_report_text = query_utils.get_scoreapp_report(account_unique_id, payload.email, session)
    print('scoreapp_report_text: ', scoreapp_report_text)

    user_products = prod_utils.get_active_user_products_for_account(account_unique_id, session)
    print('user_products: ', user_products)
    if user_products:
        user_products_prompt = prod_utils.format_user_products_for_prompt(user_products)
    else:
        user_products_prompt = ""
    print('user_products_prompt: ', user_products_prompt)
    prompt_text = get_most_recent_prompt(account_unique_id, session).prompt_text

    agent_payload = Query(
        query=query,
        prompt=prompt_text,
        visitor_email=payload.email or "",
        visitor_uuid=payload.visitor_uuid,
        account_unique_id=account_unique_id,
        chat_history=chat_history_dicts,
        relevance_score=account.relevance_score,
        k_value=account.k_value,
        sources_returned=account.sources_returned,
        temperature=account.temperature,
        chat_session_id=str(chat_session.id),
        scoreapp_report_text=scoreapp_report_text,
        user_products_prompt=user_products_prompt,
    )

    # Now feed `chat_history` into your query_source_data function
    active_subscription = check_active_subscription_status(account_unique_id, session)
    if active_subscription:

        # Variables to accumulate the full response for DB storage
        full_response_text = ""
        sources = []
        
        async def generate():
            nonlocal full_response_text, sources
            
            try:
                async for chunk in query_utils.call_repo_b_stream(agent_payload):
                    chunk_type = chunk.get("type")
                    
                    if chunk_type == "sources":
                        # Store sources but don't necessarily send to client
                        sources = chunk.get("content", [])
                        # Optionally send to client
                        yield f"data: {json.dumps(chunk)}\n\n"
                        
                    elif chunk_type == "chunk":
                        # Accumulate for DB storage
                        content = chunk.get("content", "")
                        full_response_text += content
                        # Stream to client
                        yield f"data: {json.dumps(chunk)}\n\n"
                        
                    elif chunk_type == "done":
                        
                        # Send done signal to client
                        yield f"data: {json.dumps(chunk)}\n\n"
                        
                    elif chunk_type == "error":
                        # Send error to client
                        yield f"data: {json.dumps(chunk)}\n\n"
                        
            except Exception as e:
                error_chunk = {
                    "type": "error",
                    "content": f"Stream processing error: {str(e)}"
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"

            if len(chat_history) <= 1:
                sentiment = await query_utils.get_initial_query_sentiment(query_payload=agent_payload)
                await chat_utils.update_session_with_initial_query_sentiment(
                    account_unique_id=account_unique_id,
                    visitor_uuid=payload.visitor_uuid,
                    session=session,
                    sentiment=sentiment['sentiment'],
                    explanation=sentiment['explanation']
                )
                print(f"Initial sentiment for query '{query}': {sentiment}")

            if len(chat_history) > 1:
                print("Not analyzing sentiment for non-initial queries.")
                sentiment = await query_utils.update_conversation_sentiment(query_payload=agent_payload)
                await chat_utils.update_session_with_conversation_sentiment(
                    account_unique_id=account_unique_id,
                    visitor_uuid=payload.visitor_uuid,
                    session=session,
                    sentiment=sentiment['sentiment'],
                    explanation=sentiment['explanation']
                )
                print(f"Updated sentiment for query '{query}': {sentiment}")

        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        # Handle unsubscribed users
        recipients = get_notification_users(account_unique_id, session)
        if not recipients:
            raise HTTPException(status_code=404, detail="No notification users found for this account")

        email_service = get_email_service()
        try:
            for recipient in recipients:
                email_service.send_unsubscribed_widget_email(
                    recipient['user_email'],
                    'www.expertecho.ai/login?redirect=/accounts'
                )
        except Exception as e:
            print(f"ERROR sending email: {e}") 
            raise HTTPException(status_code=500, detail=str(e))

        response = {
            "response": {
                "response_text": "Unable to process your query at this time, please contact us via email."
            }
        }

    return response


# Queries received from the in-app test widget

# Modified endpoint to support streaming
@app.post("/api/v1/internal/widget/agent-query")
async def process_internal_widget_query_agent(
    payload: WidgetQueryPayload,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
):
    account_unique_id = current_user["account_unique_id"]
    account = get_account_by_account_unique_id(account_unique_id, session)
    query = payload.query.strip() if payload.query else None
    visitor_email = current_user["user_email"]
    
    if not query:
        return {"error": "No query provided"}

    # Identify the chat session
    try:
        chat_session = create_or_identify_chat_session(
            account_unique_id,
            payload.visitor_uuid,
            session
        )
        try:
            chat_utils.create_chat_message(
                session=session,
                chat_session_id=chat_session.id,
                sender_type="user",
                message_text=payload.query,
                sources=[]
            )
        except Exception as db_error:
            print(f"Error saving to DB: {db_error}")
    except Exception as e:
        print(f"Error creating/identifying chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to identify chat session")

    # Pull chat history for context
    chat_history = get_chat_messages_by_session_id(chat_session.id, session)
    chat_history_dicts = [
        {
            "sender": msg.sender_type,
            "message": msg.message_text,
        }
        for msg in chat_history
    ]

    chat_history_dicts.append({
        "sender": "user",
        "message": query,
    })
    
    scoreapp_report_text = query_utils.get_scoreapp_report(
        account_unique_id, payload.email, session
    )
    
    user_products = prod_utils.get_active_user_products_for_account(
        account_unique_id, session
    )
    user_products_prompt = ""
    if user_products:
        user_products_prompt = prod_utils.format_user_products_for_prompt(user_products)
    
    prompt_text = get_most_recent_prompt(account_unique_id, session).prompt_text

    agent_payload = Query(
        query=query,
        prompt=prompt_text,
        visitor_email=payload.email or "",
        visitor_uuid=payload.visitor_uuid,
        account_unique_id=account_unique_id,
        chat_history=chat_history_dicts,
        relevance_score=account.relevance_score,
        k_value=account.k_value,
        sources_returned=account.sources_returned,
        temperature=account.temperature,
        chat_session_id=str(chat_session.id),
        scoreapp_report_text=scoreapp_report_text,
        user_products_prompt=user_products_prompt,
    )
    
    # Variables to accumulate the full response for DB storage
    full_response_text = ""
    sources = []
    
    async def generate():
        nonlocal full_response_text, sources
        
        try:
            async for chunk in query_utils.call_repo_b_stream(agent_payload):
                chunk_type = chunk.get("type")
                
                if chunk_type == "sources":
                    # Store sources but don't necessarily send to client
                    sources = chunk.get("content", [])
                    # Optionally send to client
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
                elif chunk_type == "chunk":
                    # Accumulate for DB storage
                    content = chunk.get("content", "")
                    full_response_text += content
                    # Stream to client
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
                elif chunk_type == "done":
                    # Save to database now that we have the full response
                    try:
                        chat_utils.create_chat_message(
                            session=session,
                            chat_session_id=chat_session.id,
                            sender_type="bot",
                            message_text=full_response_text,
                            sources=sources
                        )
                    except Exception as db_error:
                        print(f"Error saving to DB: {db_error}")
                    
                    # Send done signal to client
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
                elif chunk_type == "error":
                    # Send error to client
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
        except Exception as e:
            error_chunk = {
                "type": "error",
                "content": f"Stream processing error: {str(e)}"
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

        if len(chat_history) <= 1:
            sentiment = await query_utils.get_initial_query_sentiment(query_payload=agent_payload)
            await chat_utils.update_session_with_initial_query_sentiment(
                account_unique_id=account_unique_id,
                visitor_uuid=payload.visitor_uuid,
                session=session,
                sentiment=sentiment['sentiment'],
                explanation=sentiment['explanation']
            )
            print(f"Initial sentiment for query '{query}': {sentiment}")

        if len(chat_history) > 1:
            print("Not analyzing sentiment for non-initial queries.")
            sentiment = await query_utils.update_conversation_sentiment(query_payload=agent_payload)
            await chat_utils.update_session_with_conversation_sentiment(
                account_unique_id=account_unique_id,
                visitor_uuid=payload.visitor_uuid,
                session=session,
                sentiment=sentiment['sentiment'],
                explanation=sentiment['explanation']
            )
            print(f"Updated sentiment for query '{query}': {sentiment}")
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# @app.post("/api/v1/internal/widget/agent-query")
# async def process_internal_widget_query_agent(
#     payload: WidgetQueryPayload,
#     current_user: Annotated[User, Depends(get_current_active_user)],
#     session: Session = Depends(get_session)
# ):
#     account_unique_id = current_user["account_unique_id"]
#     account = get_account_by_account_unique_id(account_unique_id, session)
#     query = payload.query.strip() if payload.query else None
#     visitor_email = current_user["user_email"]
#     print('******Payload: ', payload)


#     if not query:
#         return {"error": "No query provided"}

#     # Identify the chat session
#     try:
#         chat_session = create_or_identify_chat_session(
#             account_unique_id,
#             payload.visitor_uuid,
#             session
#         )
#     except Exception as e:
#         print(f"Error creating/identifying chat session: {e}")
#         raise HTTPException(status_code=500, detail="Failed to identify chat session")

#     # Pull chat history for context
#     chat_history = get_chat_messages_by_session_id(chat_session.id, session)
#     chat_history_dicts = [
#         {
#             "sender": msg.sender_type,       # matches repo B
#             "message": msg.message_text,     # matches repo B
#         }
#         for msg in chat_history
#     ]

#     chat_history_dicts.append({
#         "sender": "user",
#         "message": query,
#     })
    
#     scoreapp_report_text = query_utils.get_scoreapp_report(account_unique_id, payload.email, session)
#     print('scoreapp_report_text: ', scoreapp_report_text)

#     user_products = prod_utils.get_active_user_products_for_account(account_unique_id, session)
#     print('user_products: ', user_products)
#     if user_products:
#         user_products_prompt = prod_utils.format_user_products_for_prompt(user_products)
#     else:
#         user_products_prompt = ""
#     print('user_products_prompt: ', user_products_prompt)
#     prompt_text = get_most_recent_prompt(account_unique_id, session).prompt_text

#     agent_payload = Query(
#         query=query,
#         prompt=prompt_text,
#         visitor_email=payload.email or "",
#         visitor_uuid=payload.visitor_uuid,
#         account_unique_id=account_unique_id,
#         chat_history=chat_history_dicts,
#         relevance_score=account.relevance_score,
#         k_value=account.k_value,
#         sources_returned=account.sources_returned,
#         temperature=account.temperature,
#         chat_session_id=str(chat_session.id),
#         scoreapp_report_text=scoreapp_report_text,
#         user_products_prompt=user_products_prompt,
#     )
    
#     # Now feed `chat_history` into your query_source_data function
#     response = await query_utils.call_repo_b(agent_payload)

#     return response

############################################################################
############################################################################

@app.get("/api/v1/generate-chroma-db/{account_unique_id}")
async def generate_chroma_db_datastore(account_unique_id: str,
                                       current_user: Annotated[User, Depends(get_current_active_user)],
                                       replace: bool = False,
                                       session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Generate Pinecone DB
    """
    print(f"Received request to generate Pinecone DB for account {account_unique_id} with replace={replace}")
    account = get_account_by_account_unique_id(account_unique_id, session)
    try:
        documents_from_s3 = await load_documents_from_s3(account_unique_id=account_unique_id, replace=replace, session=session)

        if replace:
            try:
                print("Clearing Pinecone namespace before replacing")
                clear_pinecone_namespace_for_replace(account_unique_id=account_unique_id)
            except Exception as e:
                error_message = f"ERROR: Failed to clear Pinecone namespace: {e}"
                print(error_message)
                # return {"status": "error", "message": error_message}
        

        print(f"Loaded {len(documents_from_s3)} documents from S3 based on DB query.")
        for db_file in documents_from_s3:
            # Construct S3 key (path in S3) using account_unique_id and file name
            if db_file.original_filename.endswith('.xls') or db_file.original_filename.endswith('.xlsx'):
                s3_key = f"{account_unique_id}/{db_file.original_filename}"
            else:
                s3_key = f"{account_unique_id}/{db_file.file_name}"
            print(f"Attempting to trigger Lambda for file: {s3_key}")

            # The payload our Lambda expects
            lambda_payload = {
                "s3_bucket": BUCKET_NAME,
                "s3_key": s3_key,
                "s3_pdf_file_key": db_file.file_name,
                "account_unique_id": account_unique_id,
                "chuck_size": account.chunk_size,
                "chunk_overlap": account.chunk_overlap,
            }

            try:
                lambda_client.invoke(
                    # CHANGE THIS to your new function name
                    FunctionName="RAG-Document-Processor",
                    InvocationType="Event",
                    Payload=json.dumps(lambda_payload),
                )
                message = f"Successfully invoked Lambda for: {s3_key}. Check CloudWatch Logs for details."
                print(message)
                 # Mark file as processed in the database
                db_file.already_processed_to_source_data = True
                session.commit()

            except Exception as e:
                error_message = f"ERROR: Failed to invoke Lambda: {e}"
                print(error_message)
                return {"status": "error", "message": error_message}
            
        response = {"message": "Document processing passed to Lambda"}

    except Exception as e:
        print(f"Error generating Pinecone DB: {e}")
        return {"error": str(e)}
    
    return response


@app.get("/api/v1/clear-chroma-db/{account_unique_id}")
async def clear_chroma_db_datastore(account_unique_id: str, current_user: Annotated[User, Depends(get_current_active_user)]) -> dict[str, Any]:
    """
    Clear Pinecone DB
    """
    print(f"Received request to clear Pinecone DB for account {account_unique_id}")
    try:
        print("Clearing Pinecone namespace before replacing")
        clear_pinecone_namespace_for_replace(account_unique_id=account_unique_id)
    except Exception as e:
        error_message = f"ERROR: Failed to clear Pinecone namespace: {e}"
        print(error_message)
        return {"status": "error", "message": error_message}


@app.post("/api/v1/widget/opt-in")
async def widget_opt_in(
                        payload: OptInPayload, 
                        auth_info: dict = Security(get_widget_api_key_user),
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Contact Us
    """
    if not payload.name or not payload.email:
        raise HTTPException(status_code=400, detail="Name, email, and message are required fields")

    webhook_url = get_opt_in_webhook_url(account_unique_id=auth_info["account_unique_id"], session=session)

    chat_session_id = create_or_identify_chat_session(
        account_unique_id=auth_info["account_unique_id"],
        visitor_uuid=payload.visitorUuid,
        session=session,
        name=payload.name,
        email=payload.email,
    ).id

    payload.sessionId = chat_session_id

    if webhook_url:
        await send_opt_in_webhook_notification(
            payload=payload,
            opt_in_webhook_url=webhook_url,
        )
    
    
    return {"message": "Opt-in", "account_unique_id": auth_info["account_unique_id"], "chat_session_id": chat_session_id}    


@app.post("/api/v1/widget/contact-us")
async def widget_contact_us(
                        payload: ContactPayload, 
                        auth_info: dict = Security(get_widget_api_key_user),
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Contact Us
    """
    print(f"Received email for session {payload.sessionId} from visitor {payload.visitorUuid} for account {auth_info['account_unique_id']}")
    if not payload.name or not payload.email or not payload.message:
        raise HTTPException(status_code=400, detail="Name, email, and message are required fields")
    
    recipients = get_notification_users(auth_info["account_unique_id"], session)
    print('recipients: ', recipients)
    if not recipients:
        raise HTTPException(status_code=404, detail="No notification users found for this account")
    
    chat_session_id = get_session_id_by_visitor_uuid(
        account_unique_id=auth_info["account_unique_id"],
        visitor_uuid=payload.visitorUuid,
        session=session
    )
    if chat_session_id:
        updated_chat_session = update_session_with_contact_details(
            account_unique_id=auth_info["account_unique_id"],
            visitor_uuid=payload.visitorUuid,
            session=session,
            name=payload.name,
            email=payload.email
        )

    if not chat_session_id:
        print(f"No chat session found for visitor UUID {payload.visitorUuid} in account {auth_info['account_unique_id']}.")
        chat_session_id = create_or_identify_chat_session(
            account_unique_id=auth_info["account_unique_id"],
            visitor_uuid=payload.visitorUuid,
            session=session,
            name=payload.name,
            email=payload.email,
        ).id
    
    webhook_url = get_account_webhook_url(account_unique_id=auth_info["account_unique_id"], session=session)
    print("Webhook URL Found: ", webhook_url)

    if webhook_url:
        await send_chat_messages_webhook_notification(
            account_unique_id=auth_info["account_unique_id"],
            chat_session_id=chat_session_id,
            payload=payload,
            webhook_url=webhook_url,
            session=session
        )
    
    email_message = create_email_message(chat_session_id, payload.message, session)
    print('email_message: ', email_message)

    chat_messages = get_chat_messages_by_session_id(
        chat_session_id=chat_session_id,
        session=session
    )

    # 1. Format the initial contact message from the user payload
    contact_info_html = (
        f"<b>Name:</b> {payload.name}<br>"
        f"<b>Email:</b> {payload.email}<br>"
        f"<b>Message:</b><br>{payload.message}"
    )
    contact_info_text = (
        f"Name: {payload.name}\n"
        f"Email: {payload.email}\n"
        f"Message:\n{payload.message}"
    )

    # 2. Format the list of ChatMessage objects into a transcript
    transcript_html_lines = []
    transcript_text_lines = []

    if chat_messages:
        print(f"Found {len(chat_messages)} chat messages. Formatting transcript...")
        # Use a list comprehension to format each message object into a string
        for msg in chat_messages:
            # Format timestamp for readability, e.g., "2025-06-11 06:58"
            formatted_time = msg.timestamp.strftime('%Y-%m-%d %H:%M')
            sender = msg.sender_type.title() # "user" -> "User"

            # Create the HTML line with bolding and good spacing
            transcript_html_lines.append(
                f"[{formatted_time}] <b>{sender}:</b> {msg.message_text}"
            )
            # Create the plain text line
            transcript_text_lines.append(
                f"[{formatted_time}] {sender}: {msg.message_text}"
            )

    # 3. Combine the parts into final email bodies
    html_body = contact_info_html
    text_body = contact_info_text

    if transcript_html_lines:
        html_body += "<br><hr><h3>Chat Transcript</h3>" + "<br>".join(transcript_html_lines)
        text_body += "\n\n--- Chat Transcript ---\n" + "\n".join(transcript_text_lines)

    email_service = get_email_service()
    print(f"Sending contact us email to {len(recipients)} recipients for account {auth_info['account_unique_id']}")
    try:
        for recipient in recipients:
            # 4. Call the new, cleaner email service method
            email_service.send_email(
                to_email=recipient['user_email'],
                subject=f"Contact Us from {payload.name}",
                html_body=html_body,
                text_body=text_body
            )
    except Exception as e:
        # Log the actual exception for better debugging
        print(f"ERROR sending email: {e}") 
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"message": "Contact Us", "account_unique_id": auth_info["account_unique_id"]}


############################################
# Account Prompt Routes
############################################


@app.post("/api/v1/create-account-prompt/{account_unique_id}")
async def create_new_account_prompt(account_unique_id: str,
                                current_user: Annotated[User, Depends(get_current_active_user)],
                                session: Session = Depends(get_session),
                                prompt_key: str = Body(..., embed=True),
                                prompt_text: str = Body(..., embed=True)) -> dict[str, Any]:
    """
    Create Account Prompt
    """
    
    new_prompt = create_account_prompt(account_unique_id, prompt_key, prompt_text, session)
    
    return {"message": "Prompt created successfully", "prompt": new_prompt}


@app.get("/api/v1/list-account-prompts/{account_unique_id}")
async def list_account_prompts(account_unique_id: str,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    List Account Prompts
    """
    account_prompts = get_account_prompts(account_unique_id, session)
    return {"prompts": account_prompts}


@app.get("/api/v1/most-recent-prompt/{account_unique_id}")
async def most_recent_account_prompt(account_unique_id: str,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Most Recent Account Prompt
    """
    most_recent_prompt = get_most_recent_prompt(account_unique_id, session)
    return {"most_recent_prompt": most_recent_prompt}


@app.get("/api/v1/account-prompt/{account_unique_id}/{id}")
async def get_account_prompt(account_unique_id: str,
                        id: int,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Get Account Prompt by Key
    """
    prompt = get_account_prompt_by_id(account_unique_id, id, session)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"prompt": prompt}


@app.put("/api/v1/update-account-prompt/{account_unique_id}/{id}")
async def update_account_prompt(account_unique_id: str,
                                id: int,
                                current_user: Annotated[User, Depends(get_current_active_user)],
                                session: Session = Depends(get_session),
                                prompt_key: str = Body(None, embed=True),
                                prompt_text: str = Body(None, embed=True)) -> dict[str, Any]:
    """
    Update Account Prompt
    """
    prompt = get_account_prompt_by_id(account_unique_id, id, session)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    revised_prompt = create_account_prompt(account_unique_id, prompt_key, prompt_text, session)

    return {"message": "Prompt updated successfully", "prompt": revised_prompt}


############################################
# AWS SES Routes
############################################

class SESEmail(BaseModel):
    to_email: str
    subject: str
    message: str
    account_unique_id: str = None

@app.post("/api/v1/send-email")
async def send_ses_email(payload: SESEmail,
                         email_service: EmailService = Depends(get_email_service)):
    """
    Send an email via AWS SES.
    This endpoint sends a simple text/html email.
    """
    if payload.account_unique_id is None or not payload.account_unique_id.strip():
        raise HTTPException(status_code=400, detail="Account unique ID is required")
    
    try:
        html_body = payload.message
        # Automatically generate a text body by stripping HTML tags.
        soup = BeautifulSoup(html_body, "html.parser")
        text_body = soup.get_text(separator='\n', strip=True)

        # Call the updated email service method with both body arguments.
        email_service.send_email(
            to_email=payload.to_email,
            subject=payload.subject,
            text_body=text_body,  # Pass the plain text version
            html_body=html_body   # Pass the HTML version
        )

        return {"response": "Email sent successfully", "to_email": payload.to_email, "subject": payload.subject}
    
    except Exception as e:
        # It's good practice to log the error on the server for debugging.
        print(f"ERROR in send_ses_email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    

############################################
# File Management Routes
############################################

@app.post("/api/v1/files/{account_unique_id}/{folder_id}", status_code=202)
async def upload_files(
        account_unique_id: str,
        folder_id: int,
        current_user: Annotated[User, Depends(get_current_active_user)],
        files: list[UploadFile] = File(...),
        session: Session = Depends(get_session)
    ):
    """
    Amended file upload function, passing the filetype processing to a lambda function
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    processing_jobs = []
    for original_file in files:
        try:
            # 1. Create a "pending" record in the database FIRST.
            pending_db_file = create_pending_file_in_db(
                original_filename=original_file.filename,
                account_unique_id=account_unique_id,
                folder_id=folder_id,
                session=session
            )

            # 2. Generate the S3 key for the *original* file in the staging bucket.
            staging_s3_key = f"{account_unique_id}/raw/{token_hex(16)}-{original_file.filename}"

            # 3. Upload the raw file to the staging S3 bucket
            file_content = await original_file.read()
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=staging_s3_key,
                Body=file_content
            )

            # 3.1 If excel, save a permanent copy of the original file in s3
            if original_file.filename.lower().endswith(('.xls', '.xlsx')):
                # Save a permanent copy of the original file in S3
                permanent_s3_key = f"{account_unique_id}/{original_file.filename}"
                s3.put_object(
                    Bucket=BUCKET_NAME,
                    Key=permanent_s3_key,
                    Body=file_content
                )

            # 4. Prepare the payload for the Lambda function. Pass the DB record ID.
            lambda_payload = {
                "db_file_id": pending_db_file.id, # This is our job ID
                "staging_bucket": BUCKET_NAME,
                "staging_s3_key": staging_s3_key,
                "original_filename": original_file.filename,
                "account_unique_id": account_unique_id,
            }
            
            # Mark status as processing now that we are invoking lambda
            pending_db_file.processing_status = "PROCESSING"
            session.add(pending_db_file)
            session.commit()

            new_docs_count = get_docs_count_for_user_account(account_unique_id, session)

            # 5. Invoke the Lambda function asynchronously
            lambda_client.invoke(
                FunctionName="Rag-File-Upload-Processor",
                InvocationType='Event',
                Payload=json.dumps(lambda_payload)
            )
            
            processing_jobs.append({
                "db_file_id": pending_db_file.id, 
                "original_filename": original_file.filename, 
                "status": "PROCESSING"
            })

        except Exception as e:
            # You might want to delete the pending_db_file here or mark it as failed immediately
            print(f"Failed to trigger processing for {original_file.filename}: {e}")
            raise HTTPException(status_code=500, detail="Could not start file processing.")
            
    return {
        "response": "success",
        "message": f"{len(processing_jobs)} file(s) accepted for processing.",
        "uploaded_files": processing_jobs,
        "new_docs_count": new_docs_count
    }


# Pydantic model for the data Lambda will send back
class FileProcessingCallback(BaseModel):
    db_file_id: int
    status: str = Field(..., pattern="^(COMPLETED|FAILED)$")
    final_file_url: Optional[str] = None
    final_unique_filename: Optional[str] = None
    error_message: Optional[str] = None

@app.post("/api/v1/internal/files/callback", status_code=200, include_in_schema=False)
async def file_processing_callback(
        payload: FileProcessingCallback,
        session: Session = Depends(get_session),
        api_key: str = Depends(get_internal_api_key) # Secure the endpoint
    ):
    """
    Receives and processes the file update callback from lambda function processing file uploads
    """
    # Use session.get for efficient primary key lookup
    db_file = session.get(SourceFile, payload.db_file_id)

    if not db_file:
        print(f"ERROR: Callback received for non-existent db_file_id: {payload.db_file_id}")
        raise HTTPException(status_code=404, detail="File record not found for the given ID.")

    # Update the file record based on the Lambda's result
    db_file.processing_status = payload.status
    if payload.status == "COMPLETED":
        db_file.file_name = payload.final_unique_filename
        db_file.file_path = payload.final_file_url
    else: # FAILED
        db_file.processing_error = payload.error_message
        # Optional: update file_name to reflect the error
        db_file.file_name = f"failed - {db_file.original_filename}"

    session.add(db_file)
    session.commit()

    return {"message": "callback received and processed"}


@app.get("/api/v1/files/{account_unique_id}")
async def get_files(account_unique_id: str,
                    current_user: Annotated[User, Depends(get_current_active_user)],
                    session: Session = Depends(get_session)):
    """
    Get All Files
    """
    returned_files = []
    statement = select(SourceFile).filter(SourceFile.account_unique_id == account_unique_id)
    result = session.exec(statement)
    files = result.all()
    for file in files:
        returned_files.append(file)
    print(type(returned_files))

    if not returned_files:
        return {"error": "No files found",
                "files": returned_files}
    
    return {"files": returned_files}


@app.get("/api/v1/files/{account_unique_id}/{folder_id}")
async def get_files_in_folder(account_unique_id: str, folder_id: int,
                              current_user: Annotated[User, Depends(get_current_active_user)],
                              session: Session = Depends(get_session)):
    """
    Get All Files in a Folder
    """
    returned_files = []
    statement = select(SourceFile).filter(SourceFile.account_unique_id == account_unique_id, SourceFile.folder_id == folder_id)
    result = session.exec(statement)
    files = result.all()
    for file in files:
        returned_files.append(file)
    print(type(returned_files))

    if not returned_files:
        return {"error": "No files found",
                "files": returned_files}
    
    return {"files": returned_files}


@app.get("/api/v1/files/{account_unique_id}/{file_id}")
async def get_file(account_unique_id: str, file_id: int,
                   current_user: Annotated[User, Depends(get_current_active_user)],
                   session: Session = Depends(get_session)):
    """
    Get File By ID
    """
    statement = select(SourceFile).filter(SourceFile.account_unique_id == account_unique_id, SourceFile.id == file_id)
    result = session.exec(statement)
    file = result.first()
    
    if not file:
        return {"error": "File not found",
                "file_id": file_id}
    
    return {"response": "success",
            "file": file}


@app.put("/api/v1/files/{account_unique_id}/{file_id}", response_model=Union[SourceFile, dict])
async def update_file(file_id: int,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      updated_file: SourceFile = Body(...),
                      session: Session = Depends(get_session)):
    """
    Edit File
    """
    print('updated_file:', updated_file)
    file = session.get(SourceFile, file_id)
    print('file:', file)
    
    if not file:
        raise HTTPException(status_code=404, detail={"error": "File not found", "file_id": file_id})
    
    updated_file = update_file_in_db(file_id, updated_file, session)
    
    return updated_file


@app.delete("/api/v1/files/{account_unique_id}/{file_id}")
async def delete_file(account_unique_id: str, file_id: int,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Delete File
    """
    file = session.get(SourceFile, file_id)
    
    if not file:
        return {"error": "File not found",
                "file_id": file_id}
    
    s3_response = await delete_file_from_s3(account_unique_id, file, session)
    if s3_response == True:

        s3_object_key = f"{file.account_unique_id}/{file.file_name}"
        chroma_response =delete_chunks_from_pinecone(s3_object_key, account_unique_id)

        response = delete_file_from_db(account_unique_id, file_id, session)
        new_docs_count = get_docs_count_for_user_account(account_unique_id, session)
        return {'response': 'success',
                'file_id': response['file_id'],
                'new_docs_count': new_docs_count,
                'chroma_response': chroma_response['status']}
    else:
        raise HTTPException(status_code=404, detail={"error": "File could not be deleted", "file_id": file_id})
    

@app.api_route("/api/v1/files/view/{account_unique_id}/{file_identifier}",
                    response_class=StreamingResponse,
                    summary="View a specific document from S3",
                    tags=["Documents"],
                    methods=["GET", "HEAD"])
async def stream_file_from_s3(request: Request, account_unique_id: str, file_identifier: str,
                #    current_user: Annotated[User, Depends(get_current_active_user)],
                   session: Session = Depends(get_session)):
    """
    Get File By S3 key identifier
    """

        # Construct the S3 key
    s3_key = f"{account_unique_id}/{file_identifier}"
    print(f"Request method: {request.method} for S3 Key: {s3_key}")

    print(f"Attempting to fetch S3 object: Bucket='{BUCKET_NAME}', Key='{s3_key}'")

    try:
        if request.method == "HEAD":
            s3_metadata = s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
            content_type = s3_metadata.get('ContentType', 'application/pdf')
            content_length = s3_metadata.get('ContentLength', 0)

            if not content_type.lower().startswith('application/pdf'):
                content_type = 'application/pdf'

            response_headers = {
                "Content-Disposition": f"inline; filename=\"{file_identifier}\"",
                "Content-Type": content_type,
                "Content-Length": str(content_length) # Good to include for HEAD
            }
            return StreamingResponse(io.BytesIO(b''), media_type=content_type, headers=response_headers)

        # For GET request, proceed as before
        s3_object = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        file_content_bytes = s3_object['Body'].read()
        content_type = s3_object.get('ContentType', 'application/pdf')
        if not content_type.lower().startswith('application/pdf'):
            content_type = 'application/pdf'

        response_headers = {
            "Content-Disposition": f"inline; filename=\"{file_identifier}\"",
            "Content-Type": content_type
            # Content-Length will be added automatically by StreamingResponse for GET
        }
        return StreamingResponse(
            io.BytesIO(file_content_bytes),
            media_type=content_type,
            headers=response_headers
        )

    except s3.exceptions.NoSuchKey:
        print(f"S3 Error: NoSuchKey for Key='{s3_key}'")
        raise HTTPException(status_code=404, detail=f"File '{file_identifier}' not found.")
    except Exception as e: # Catch other Boto3 errors that might indicate permission issues etc.
        # Specifically for head_object, a 403 from S3 might come as ClientError
        if hasattr(e, 'response') and 'Error' in e.response and e.response['Error']['Code'] == '403':
            print(f"S3 Permission Error (403) for Key='{s3_key}': {e}")
            raise HTTPException(status_code=403, detail="Access denied to the file in storage.")
        print(f"S3 Error processing Key='{s3_key}': {e}")
        raise HTTPException(status_code=500, detail=f"Error accessing file: {str(e)}")


    # # Construct the S3 key
    # s3_key = f"{account_unique_id}/{file_identifier}"
    # print(f"Request method: {request.method} for S3 Key: {s3_key}")

    # print(f"Attempting to fetch S3 object: Bucket='{BUCKET_NAME}', Key='{s3_key}'")
    
    
class URLRequest(BaseModel):
    """
    URL Request
    """
    url: str
    
@app.post("/api/v1/get-text-from-url/{account_unique_id}/{folder_id}")
async def get_text_from_url(request: URLRequest, account_unique_id: str, folder_id: int,
                            current_user: Annotated[User, Depends(get_current_active_user)],
                            session: Session = Depends(get_session)):
    """
    Get Text from URL
    """
    url = request.url
    html_content = await fetch_html_content(url)
    extracted_text = await extract_text_from_html(html_content)

    # Call the updated prepare_for_s3_upload
    s3_upload_result = await prepare_for_s3_upload(
        extracted_text['text'],
        extracted_text['title'], # Pass the title for filename generation
        account_unique_id,
        folder_id,
        session
    )
    
    print(f"Received request to get text from URL: {request.url}, processed as PDF: {s3_upload_result.get('file_name_on_s3')}")
    return {"response": "success", "url": request.url, "s3_details": s3_upload_result}


@app.get("/api/v1/folders/{account_unique_id}")
async def get_folders(account_unique_id: str,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Get Folders
    """
    statement = select(Folder).filter(Folder.account_unique_id == account_unique_id)
    result = session.exec(statement)
    folders = []
    for item in result:
        folders.append(item)
    
    if not folders:
        return {"error": "No folders found"}
    
    if folders:
        processed_docs_count = get_processed_docs_count_for_user_account(account_unique_id, session)
        return {"response": "success",
                "folders": folders,
                "processed_docs_count": processed_docs_count}


@app.get("/api/v1/folders/{account_unique_id}/{folder_id}")
async def get_folder(account_unique_id: str,
                     folder_id: int,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Get Folders
    """
    statement = select(Folder).filter(Folder.account_unique_id == account_unique_id, Folder.id == folder_id)
    result = session.exec(statement)
    folder = result.first()
    
    if not folder:
        return {"error": "No folder found"}
    
    if folder:
        return {"response": "success",
                "folder": folder}


@app.post("/api/v1/folders/{account_unique_id}/{folder_name}")
async def create_folder(account_unique_id: str,
                        folder_name: str,
                          current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)):
    """
    Create Account
    """
    statement = select(Folder).filter(Folder.account_unique_id == account_unique_id, Folder.folder_name == folder_name)
    result = session.exec(statement)
    folder = result.first()
    
    if folder:
        return {"error": "Folder already exists",
                "folder_name": folder_name,
                "folder_id": folder.id,
                "account_unique_id": account_unique_id}
        
    folder = create_new_folder_in_db(account_unique_id, folder_name, session)
    
    return {"response": "success",
            "folder": folder,
            "folder_name": folder.folder_name,
            "account_unique_id": folder.account_unique_id}
    

@app.put("/api/v1/folders/{account_unique_id}/{folder_id}", response_model=Union[Folder, dict])
async def edit_folder(account_unique_id: str, folder_id: int, updated_folder: Folder,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Edit Folder
    """
    folder = session.get(Folder, folder_id)
    
    if not folder:
        return {"error": "Folder not found",
                "folder_id": folder_id}
    
    updated_folder = update_folder_in_db(folder_id, updated_folder, session)
    
    return updated_folder


@app.delete("/api/v1/folder/{folder_id}")
async def delete_folder(folder_id: int,
                         current_user: Annotated[User, Depends(get_current_active_user)],
                         session: Session = Depends(get_session)):
    """
    Delete Folder
    """
    response = delete_folder_from_db(folder_id, session)
    if response.get('error'):
        return {"error": response['error'],
                'folder_id': response['folder_id']}
    
    return {'response': 'success',
            'folder_id': response['folder_id']}


############################################
# Accounts Routes
############################################

@app.get("/api/v1/accounts")
async def get_accounts(current_user: Annotated[User, Depends(get_current_active_user)],
                       session: Session = Depends(get_session)):
    """
    Get All Accounts
    """
    returned_accounts = []
    account_unique_id = current_user['account_unique_id']
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    accounts = result.all()
    
    if not accounts:
        return {"error": "No accounts found",
                "accounts": returned_accounts}
        
    for account in accounts:
        returned_accounts.append(account)
    return {"response": "success",
            "accounts": returned_accounts}


@app.post("/api/v1/accounts/{account_organisation}")
async def create_account(account_organisation: str, session: Session = Depends(get_session)):
    """
    Create Account
    """
    account = create_new_account_in_db(account_organisation, session)

    default_prompt = create_account_prompt(
            account_unique_id=account.account_unique_id,
            prompt_key="Main Prompt",
            prompt_text=None,
            session=session
        )
    
    return {"response": "success",
            "account": account,
            "account_organisation": account.account_organisation,
            "account_unique_id": account.account_unique_id}


@app.put("/api/v1/accounts/{account_unique_id}", response_model=Union[Account, dict])
async def edit_account(account_unique_id: str, updated_account: Account, 
                       current_user: Annotated[User, Depends(get_current_active_user)],
                       session: Session = Depends(get_session)):
    """
    Edit Account
    """

    account = update_account_in_db(account_unique_id, updated_account, session)
    
    return account


@app.delete("/api/v1/accounts/{account_unique_id}")
async def delete_account(account_unique_id: str,
                         current_user: Annotated[User, Depends(get_current_active_user)],
                         session: Session = Depends(get_session)):
    """
    Delete Account
    """

    if not current_user.get('is_account_owner'):
        return {"message": "Action restricted to account owners only"}
    
    # WidgetConfig and WidgetAPIKey
    widget_api_keys = account_utils.get_widget_api_keys_for_account(account_unique_id, session)
    widget_configs = account_utils.get_widget_configs_for_account(account_unique_id, session)

    for widget_api_key in widget_api_keys:
        widget_api_key_delete_result = account_utils.delete_widget_api_key_from_db(widget_api_key.id, session)
        print('*****widget_api_key_delete_result: ', widget_api_key_delete_result)
    
    for widget_config in widget_configs:
        widget_config_delete_result = account_utils.delete_widget_config_from_db(widget_config.widget_id, session)
        print('*****widget_config_delete_result: ', widget_config_delete_result)

    # ScoreAppAccount and ScoreCardResult
    score_card_results = await int_utils.get_score_card_results_for_account(account_unique_id, session)
    scoreapp_account = await int_utils.get_score_app_account(account_unique_id, session)

    for score_card_result in score_card_results:
        score_card_result_delete_result = await int_utils.delete_score_card_result_from_db(score_card_result.result_id, session)
        print('*****score_card_result_delete_result: ', score_card_result_delete_result)
    
    if scoreapp_account:
        scoreapp_account_delete_result = await int_utils.delete_scoreapp_account_from_db(scoreapp_account.scoreapp_id, session)
        print('*****scoreapp_account_delete_result: ', scoreapp_account_delete_result)

    # ChatSession, ChatMessage and EmailMessage
    chat_sessions = chat_utils.get_chat_sessions_for_account(account_unique_id, session)
    for chat_session in chat_sessions:
        chat_messages = chat_utils.get_chat_messages_for_chat_session(chat_session.id, session)
        for chat_message in chat_messages:
            chat_message_delete_result = chat_utils.delete_chat_message_from_db(chat_message.message_id, session)
            print('*****chat_message_delete_result: ', chat_message_delete_result)
        email_messages = chat_utils.get_email_messages_for_chat_session(chat_session.id, session)
        for email_message in email_messages:
            email_message_delete_result = chat_utils.delete_email_message_from_db(email_message.message_id, session)
            print('*****email_message_delete_result: ', email_message_delete_result)
    
    for chat_session in chat_sessions:
        chat_session_delete_result = chat_utils.delete_chat_session_from_db(chat_session.id, session)
        print('*****chat_session_delete_result: ', chat_session_delete_result)
    
    # SourceFile From S3 and DB
    source_files = file_utils.get_files_for_account(account_unique_id, session)
    for source_file in source_files:
        delete_file_from_s3_result = await file_utils.delete_file_from_s3(account_unique_id, source_file, session)
        print('*****delete_file_from_s3_result: ', delete_file_from_s3_result)
        delete_file_from_db_result = await file_utils.delete_file_from_db(account_unique_id, source_file.id, session)
        print('*****delete_file_from_db_result: ', delete_file_from_db_result)
    
    # Folders
    folders = file_utils.get_folders_for_account(account_unique_id, session)
    for folder in folders:
        folder_delete_result = file_utils.delete_folder_from_db(folder.id, session)
        print('*****folder_delete_result: ', folder_delete_result)

    # Account Prompts
    prompts = account_utils.get_account_prompts(account_unique_id, session)
    for prompt in prompts:
        delete_prompt_result = account_utils.delete_prompt_from_db(prompt.id, session)
        print('*****delete_prompt_result: ', delete_prompt_result)

    # User Products
    user_products = prod_utils.get_user_products_for_account(account_unique_id, session)
    for user_product in user_products:
        delete_user_products_result = prod_utils.delete_user_product_from_db(account_unique_id, user_product.id, session)
        print('*****delete_user_products_result: ', delete_user_products_result)

    # Pinecone Data Store
    collection_status = check_pinecone_namespace_status(account_unique_id)
    print("collection_status: ", collection_status["status"])
    if not collection_status["status"] == 404:
        delete_vector_store_result = await clear_chroma_db_datastore(account_unique_id, current_user)
        print('*****delete_vector_store_result: ', delete_vector_store_result)
    
    # Users
    users = account_utils.get_users_for_account(account_unique_id, session)
    print("******USERS: ", users)
    for user in users:
        delete_user_result = account_utils.delete_user_from_db(account_unique_id, user.id, session)
        print('*****delete_user_result: ', delete_user_result)

    # Account
    delete_account_result = account_utils.delete_account_from_db(account_unique_id, session)
    print('*****delete_account_result: ', delete_account_result)

    return {'response': 'success',
            'delete_account_result': delete_account_result}


@app.get("/api/v1/accounts/{account_unique_id}")
async def get_account(account_unique_id: str,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Get Account By ID
    """
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    account = result.first()
    
    if not account:
        return {"error": "Account not found"}
    
    return {"response": "success",
            "account": account}


############################################
# Users Routes
############################################

@app.get("/api/v1/users")
async def get_users(current_user: Annotated[User, Depends(get_current_active_user)],
                    session: Session = Depends(get_session)):
    """
    Get all Users
    """
    returned_users = []
    account_unique_id = current_user['account_unique_id']
    statement = select(User).filter(User.account_unique_id == account_unique_id)
    result = session.exec(statement)
    users = result.all()
    
    if not users:
        return {"error": "No users found",
                "users": returned_users}
        
    for user in users:
        returned_users.append(user)
    
    return {"response": "success",
            "users": returned_users}


class UserCreatePayload(BaseModel):
    user_email: str
    user_password: str


@app.post("/api/v1/users/{account_unique_id}")
async def create_user(account_unique_id: str, 
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      payload: UserCreatePayload = Body(...),
                      session: Session = Depends(get_session)):
    """
    Create User
    """
    receive_notifications = False  # Default to False for subsequent users
    user_password = get_password_hash(payload.user_password)
    user = create_new_user_in_db(payload.user_email.lower(), user_password, account_unique_id, session, receive_notifications)
    user_type = 'additional_user'
    company = get_account_by_account_unique_id(account_unique_id, session).account_organisation
    sync_to_mailerlite(email=payload.user_email.lower(), company=company, account_unique_id=account_unique_id, user_type=user_type, session=session)

    return {"response": "success",
            "user": user,
            "user_email": user.user_email.lower(),
            "user_id": user.id}


@app.post("/api/v1/first-user/{account_unique_id}")
async def create_first_user(account_unique_id: str, 
                      payload: UserCreatePayload = Body(...),
                      session: Session = Depends(get_session)):
    """
    Create User
    """
    receive_notifications = True
    is_account_owner = True  # Default to True for first user
    user_password = get_password_hash(payload.user_password)
    user = create_new_user_in_db(payload.user_email.lower(), user_password, account_unique_id, session, receive_notifications, is_account_owner)
    user_type = 'first_user'
    company = get_account_by_account_unique_id(account_unique_id, session).account_organisation
    if not company:
        raise HTTPException(status_code=404, detail="Account not found")
    sync_to_mailerlite(email=payload.user_email.lower(), company=company, account_unique_id=account_unique_id, user_type=user_type, session=session)

    return {"response": "success",
            "user": user,
            "user_email": user.user_email.lower(),
            "user_id": user.id}


@app.put("/api/v1/users/{account_unique_id}/{user_id}", response_model=Union[User, dict])
async def edit_user(account_unique_id: str, user_id: int, updated_user: User,
                    current_user: Annotated[User, Depends(get_current_active_user)],
                    session: Session = Depends(get_session)):
    """
    Edit User
    """
    user = session.get(User, user_id)
    
    if not user:
        return {"error": "User not found",
                "user_id": user_id}
    
    user = update_user_in_db(account_unique_id, user_id, updated_user, session)
    
    return user


@app.delete("/api/v1/users/{account_unique_id}/{user_id}")
async def delete_user(account_unique_id: str, user_id: int,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Delete User
    """
    user_email = session.get(User, user_id).user_email
    delete_subscriber_from_mailerlite(user_email=user_email, account_unique_id=account_unique_id, session=session)

    response = delete_user_from_db(account_unique_id, user_id, session)
    
    return {"response": "success",
            "user_id": response['user_id']}


@app.get("/api/v1/users/{account_unique_id}/{user_id}")
async def get_user(account_unique_id: str, user_id: int,
                   current_user: Annotated[User, Depends(get_current_active_user)],
                   session: Session = Depends(get_session)):
    """
    Get User By ID
    """
    statement = select(User).filter(User.account_unique_id == account_unique_id, User.id == user_id)
    result = session.exec(statement)
    user = result.first()
    
    if not user:
        return {"error": "User not found",
                "user_id": user_id}
    
    return {"response": "success",
            "user": user}



############################################
# Chat Messages Routes
############################################

class ChatMessagePayload(BaseModel):
    chat_session_id: int
    visitor_uuid: str
    sender_type: str  # 'user' or 'bot'
    message_text: str
    sources: List[str]


@app.post("/api/v1/widget/messages")
async def process_widget_message(
                                    payload: ChatMessagePayload,
                                    auth_info: dict = Security(get_widget_api_key_user),
                                    session: Session = Depends(get_session)
                                    ):
    account_unique_id = auth_info["account_unique_id"]
    print(f"Received chat message from widget for account {account_unique_id}: {payload.message_text}")
    # Validate the chat message here
    if not payload.message_text or not payload.chat_session_id or not payload.visitor_uuid:
        raise HTTPException(status_code=400, detail="chat_session_id, visitor_uuid, and message_text are required fields")
    if payload.sender_type not in ['user', 'bot']:
        raise HTTPException(status_code=400, detail="sender_type must be 'user' or 'bot'")
    # Validate the chat session ID and visitor UUID
    if not isinstance(payload.chat_session_id, int) or not payload.visitor_uuid:
        raise HTTPException(status_code=400, detail="Invalid chat_session_id or visitor_uuid format")
    
    # Process the chat message
    print(f"Processing chat message: {payload.message_text} from {payload.sender_type}")
    try:
        chat_session = create_or_identify_chat_session(account_unique_id, payload.visitor_uuid, session)
    except Exception as e:
        print(f"Error creating or identifying chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create or identify chat session")

    try:
        chat_message = create_chat_message(chat_session.id, payload.message_text, payload.sender_type, payload.sources, session)
    except Exception as e:
        print(f"Error creating chat message: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat message")
    print(f"Chat message processed successfully: {chat_message.message_text} from {chat_message.sender_type}")


@app.post("/api/v1/internal/widget/messages")
async def process_internal_widget_message(
                                    payload: ChatMessagePayload,
                                    current_user: Annotated[User, Depends(get_current_active_user)],
                                    session: Session = Depends(get_session)
                                    ):
    account_unique_id = current_user["account_unique_id"]
    print(f"Received chat message from widget for account {account_unique_id}: {payload.message_text}")
    # Validate the chat message here
    if not payload.message_text or not payload.chat_session_id or not payload.visitor_uuid:
        raise HTTPException(status_code=400, detail="chat_session_id, visitor_uuid, and message_text are required fields")
    if payload.sender_type not in ['user', 'bot']:
        raise HTTPException(status_code=400, detail="sender_type must be 'user' or 'bot'")
    # Validate the chat session ID and visitor UUID
    if not isinstance(payload.chat_session_id, int) or not payload.visitor_uuid:
        raise HTTPException(status_code=400, detail="Invalid chat_session_id or visitor_uuid format")
    
    # Process the chat message
    print(f"Processing chat message: {payload.message_text} from {payload.sender_type}")
    try:
        chat_session = create_or_identify_chat_session(account_unique_id, payload.visitor_uuid, session)
    except Exception as e:
        print(f"Error creating or identifying chat session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create or identify chat session")

    try:
        chat_message = create_chat_message(chat_session.id, payload.message_text, payload.sender_type, payload.sources, session)
    except Exception as e:
        print(f"Error creating chat message: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat message")
    print(f"Chat message processed successfully: {chat_message.message_text} from {chat_message.sender_type}")


@app.get("/api/v1/chat-sessions/{account_unique_id}")
async def get_chat_sessions(account_unique_id: str,
                            current_user: Annotated[User, Depends(get_current_active_user)],
                            session: Session = Depends(get_session)):
    """
    Get All Chat Sessions for an Account
    """
    statement = (
        select(ChatSession)
        .filter(ChatSession.account_unique_id == account_unique_id)
        .order_by(ChatSession.start_time.desc())
    )
    result = session.exec(statement)
    chat_sessions = result.all()
    
    if not chat_sessions:
        return {"error": "No chat sessions found",
                "chat_sessions": []}
    
    return {"response": "success",
            "chat_sessions": chat_sessions}


@app.get("/api/v1/chat-sessions/{account_unique_id}/{session_id}")
async def get_chat_session(account_unique_id: str, session_id: int,
                           current_user: Annotated[User, Depends(get_current_active_user)],
                           session: Session = Depends(get_session)):
    """
    Get Chat Session By ID
    """
    statement = select(ChatSession).filter(ChatSession.account_unique_id == account_unique_id, ChatSession.id == session_id)
    result = session.exec(statement)
    chat_session = result.first()
    
    if not chat_session:
        return {"error": "Chat session not found",
                "session_id": session_id}
    
    return {"response": "success",
            "chat_session": chat_session}


@app.get("/api/v1/chat-messages/{account_unique_id}/{session_id}")
async def get_chat_messages(account_unique_id: str, session_id: int,
                            current_user: Annotated[User, Depends(get_current_active_user)],
                            session: Session = Depends(get_session)):
    """
    Get Chat Messages for a Session
    """
    
    chat_messages = get_chat_messages_by_session_id(session_id, session)
    
    if not chat_messages:
        return {"error": "No chat messages found for this session",
                "session_id": session_id}
    
    return {"response": "success",
            "chat_messages": chat_messages}


############################################
# Subscription Routes
############################################

class SubscriptionCreate(BaseModel):
    stripe_subscription_id: str
    stripe_customer_id: str
    status: str = Field(default="active", nullable=True)
    current_period_end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: str = Field(default="monthly", nullable=True)  # 'monthly' or 'yearly'
    trial_start: Optional[datetime] = Field(default=None, nullable=True)
    trial_end: Optional[datetime] = Field(default=None, nullable=True)
    subscription_start: Optional[datetime] = Field(default=None, nullable=True)
    stripe_account_url: Optional[str] = Field(default=None, nullable=True, index=True)


@app.post("/api/v1/stripe-subscriptions/{account_unique_id}")
async def create_stripe_subscription(account_unique_id: str,
                               subscription_data: SubscriptionCreate,
                               current_user: Annotated[User, Depends(get_current_active_user)],
                               session: Session = Depends(get_session)):
    """
    Create a New Subscription
    """
    try:
        subscription_dict = subscription_data.model_dump()
        subscription = create_stripe_subscription_in_db(account_unique_id, subscription_dict, session)
    except Exception as e:
        print(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to create subscription")

    return {"response": "success",
            "subscription": subscription}


@app.get("/api/v1/stripe-subscriptions/{account_unique_id}")
async def get_stripe_subscriptions(account_unique_id: str,
                                   current_user: Annotated[User, Depends(get_current_active_user)],
                                   session: Session = Depends(get_session)):
    """
    Get All Stripe Subscriptions for an Account
    """
    statement = select(StripeSubscription).filter(StripeSubscription.account_unique_id == account_unique_id)
    result = session.exec(statement)
    subscriptions = result.all()
    
    if not subscriptions:
        return {"error": "No subscriptions found",
                "subscriptions": []}
    
    active_subscription = check_active_subscription_status(account_unique_id, session)
    
    return {"response": "success",
            "subscriptions": subscriptions,
            "active_subscription": active_subscription}


@app.get("/api/v1/stripe-subscriptions-id/{account_unique_id}/{subscription_id}")
async def get_stripe_subscription_by_id(account_unique_id: str, subscription_id: int,
                                   current_user: Annotated[User, Depends(get_current_active_user)],
                                   session: Session = Depends(get_session)):
    """
    Get a Stripe Subscription by ID
    """
    statement = select(StripeSubscription).filter(StripeSubscription.account_unique_id == account_unique_id,
                                                  StripeSubscription.id == subscription_id)
    result = session.exec(statement)
    subscription = result.first()

    if not subscription:
        return {"error": "Subscription not found",
                "subscription_id": subscription_id}

    return {"response": "success",
            "subscription": subscription}


@app.get("/api/v1/stripe-subscriptions-ref/{account_unique_id}/{stripe_subscription_id}")
async def get_stripe_subscription_by_ref(account_unique_id: str, stripe_subscription_id: str,
                                   current_user: Annotated[User, Depends(get_current_active_user)],
                                   session: Session = Depends(get_session)):
    """
    Get a Stripe Subscription by Reference ID
    """
    statement = select(StripeSubscription).filter(StripeSubscription.account_unique_id == account_unique_id,
                                                  StripeSubscription.stripe_subscription_id == stripe_subscription_id)
    result = session.exec(statement)
    subscription = result.first()

    if not subscription:
        return {"error": "Subscription not found",
                "stripe_subscription_id": stripe_subscription_id}

    return {"response": "success",
            "subscription": subscription}


class SubscriptionUpdate(BaseModel):
    status: str = Field(default="active", nullable=True)
    current_period_end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: str = Field(default="monthly", nullable=True)  # 'monthly' or 'yearly'
    subscription_start: Optional[datetime] = Field(default=None, nullable=True)


# The updated endpoint
@app.put("/api/v1/stripe-subscriptions/{account_unique_id}/{subscription_id}", response_model=StripeSubscription)
async def update_stripe_subscription(account_unique_id: str, subscription_id: int,
                                      subscription_update_data: SubscriptionUpdate, # Renamed for clarity
                                      current_user: Annotated[User, Depends(get_current_active_user)],
                                      session: Session = Depends(get_session)):
    """
    Update a Stripe Subscription
    """
    # 1. Convert the Pydantic model to a dictionary of *only the submitted fields*
    update_dict = subscription_update_data.model_dump(exclude_unset=True)

    # 2. Call the utility function with the dictionary
    updated_subscription = update_stripe_subscription_in_db(
        subscription_id=subscription_id, 
        update_data=update_dict, # Pass the dictionary here
        session=session
    )
    
    if not updated_subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return updated_subscription


############################################
# Product Routes
############################################


@app.get("/api/v1/products")
async def get_products(current_user: Annotated[User, Depends(get_current_active_user)],
                       session: Session = Depends(get_session)):
    """
    Get All Products
    """
    statement = select(Product)
    result = session.exec(statement)
    products = result.all()
    
    if not products:
        return {"error": "No products found",
                "products": []}
    
    return {"response": "success",
            "products": products}

############################################
# Stripe Routes
############################################


@app.get("/api/v1/checkout/{price_id}/{account_unique_id}")
async def create_checkout_session(price_id: str, account_unique_id: str,):
    """
    Create Stripe Checkout Session
    """
    recurring = get_stripe_price_object_from_price_id(price_id).recurring
    mode = "subscription" if recurring else "payment"
    if not price_id:
        raise HTTPException(status_code=400, detail="Price ID is required")
    checkout_session = stripe.checkout.Session.create(
        line_items=[
            {
                    "price": price_id,
                    "quantity": 1,
                },
        ],
        metadata={ "account_unique_id": account_unique_id
        },
        mode=mode,
        success_url=f"{FE_BASE_URL}/accounts/",
        cancel_url=f"{FE_BASE_URL}/accounts/",
    )
    return responses.RedirectResponse(checkout_session.url, status_code=303)


@app.post("/api/v1/webhook/")
async def stripe_webhook(request: Request, session: Session = Depends(get_session)):
    payload = await request.body()
    event = None

    try:
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except ValueError as e:
        print("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    if event["type"] == "product.created":
        new_product = process_stripe_product_created_event(event, session)

    elif event["type"] == "product.updated":
        updated_product = process_stripe_product_updated_event(event, session)

    elif event["type"] == "invoice.paid":
        price_type = event["data"]["object"]["lines"]["data"][0]["price"]["type"]
        customer_email = event["data"]["object"]["customer_email"]
        if price_type == "recurring":
            # Create initial subscription in DB
            subscription = process_stripe_subscription_invoice_paid_event(event, session)
            print(f"Created new subscription: {subscription}")
            update_active_customer_groups(email=customer_email)
        
    elif event["type"] == "checkout.session.completed":
        if event["data"]["object"]["mode"] == "subscription":
            subscription_id = event.get('data', {}).get('object', {}).get('subscription', {})
            db_subscription = get_db_subscription_by_subscription_id(subscription_id, session)
            print("db_subscription: ", db_subscription)
            if db_subscription:
                updated_subscription = add_account_unique_id_to_subscription(event, session)
            else:
                subscription = process_stripe_subscription_checkout_session_completed_event(event, session)

    elif event["type"] == "customer.subscription.updated":
        # Get subscription details from Stripe
        updated_subscription = process_stripe_subscription_updated_event(event, session)

    elif event["type"] == "customer.subscription.deleted":
        deleted_subscription = process_stripe_subscription_deleted_event(event, session)
        customer_id = event["data"]["object"]["customer"]
        customer = get_stripe_customer_from_customer_id(customer_id)
        customer_email = customer.get('email', None)
        update_cancelled_customer_groups(email=customer_email)
    print(f"Received event: {event}")
    return {}


@app.post("/api/v1/cancel-stripe-sub/{account_unique_id}/{subscription_id}")
async def cancel_stripe_subscription(account_unique_id: str, subscription_id: str,
                                     current_user: Annotated[User, Depends(get_current_active_user)],
                                     session: Session = Depends(get_session)):
    """
    Cancel a Stripe Subscription - from the customer's in-app action
    """
    try:
        process_in_app_subscription_cancellation(subscription_id, session)
        print(f"Subscription {subscription_id} cancelled successfully for account {account_unique_id}")
    except Exception as e:
        print(f"Error cancelling subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")
    
    return {"response": "success",
            "message": f"Subscription {subscription_id} cancelled successfully."}


############################################
#  Dashboard Routes
############################################


@app.get("/api/v1/get-dashboard-data/{account_unique_id}")
async def get_dashboard_data(account_unique_id: str,
                          current_user: Annotated[User, Depends(get_current_active_user)],
                          session: Session = Depends(get_session)) -> dict[str, Any]:
    
    chat_session_count = get_chat_session_count(account_unique_id, session)
    questions_answered_count = get_questions_answered_count(account_unique_id, session)
    processed_docs_count = get_processed_docs_count_for_user_account(account_unique_id, session)
    email_message_count = get_email_message_count(account_unique_id, session)

    print("chat_session_count: ", chat_session_count)
    print("questions_answered_count: ", questions_answered_count)
    print("processed_docs_count: ", processed_docs_count)
    print("email_message_count: ", email_message_count)

    return {"chat_session_count": chat_session_count,
            "questions_answered_count": questions_answered_count,
            "processed_docs_count": processed_docs_count,
            "email_message_count": email_message_count}


############################################
#  UserProduct Routes
############################################

@app.get("/api/v1/user-products/{account_unique_id}")
async def get_user_products(account_unique_id: str,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Get UserProducts
    """
    user_products = prod_utils.get_user_products_for_account(account_unique_id, session)

    if not user_products:
        return {"error": "No user products found"}
    
    if user_products:
        return {"response": "success",
                "user_products": user_products}
    

@app.get("/api/v1/active-user-products/{account_unique_id}")
async def get_active_user_products(account_unique_id: str,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Get Active UserProducts
    """
    active_user_products = prod_utils.get_active_user_products_for_account(account_unique_id, session)

    if not active_user_products:
        return {"error": "No active user products found"}
    
    if active_user_products:
        return {"response": "success",
                "active_user_products": active_user_products}


@app.get("/api/v1/user-products/{account_unique_id}/{product_id}")
async def get_user_product(account_unique_id: str,
                     product_id: int,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Get UserProduct
    """
    user_product = prod_utils.get_user_product_by_id(account_unique_id, product_id, session)
    
    if not user_product:
        return {"error": "No user product found"}
    
    if user_product:
        return {"response": "success",
                "user_product": user_product}


class UserProduct(BaseModel):
    product_title: str = Field(default="", nullable=False)
    product_description: str = Field(default="", nullable=False)
    product_sale_url: str = Field(default="", nullable=False)
    who_is_this_for: str = Field(default="", nullable=False)
    is_active: bool = Field(default=True, nullable=False)


@app.post("/api/v1/user-products/{account_unique_id}")
async def create_user_product(account_unique_id: str,
                        payload: UserProduct,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)):
    """
    Create UserProduct
    """
    user_product = prod_utils.get_user_product_by_product_title(account_unique_id, payload.product_title, session)
    
    if user_product:
        return {"error": "UserProduct already exists",
                "product_title": user_product.product_title,
                "product_id": user_product.id,
                "account_unique_id": account_unique_id}
        
    user_product = prod_utils.create_new_user_product_in_db(account_unique_id, payload, session)
    
    return {"response": "success",
            "user_product": user_product,
            "product_title": user_product.product_title,
            "account_unique_id": user_product.account_unique_id}
    

@app.put("/api/v1/user-products/{account_unique_id}/{product_id}")
async def edit_user_product(account_unique_id: str, product_id: int, payload: UserProduct,
                      current_user: Annotated[User, Depends(get_current_active_user)],
                      session: Session = Depends(get_session)):
    """
    Edit UserProduct
    """
    user_product = prod_utils.get_user_product_by_id(account_unique_id, product_id, session)
    
    if not user_product:
        return {"error": "UserProduct not found",
                "user_product": user_product}
    
    updated_user_product = prod_utils.update_user_product(account_unique_id, product_id, payload, session)
    
    return updated_user_product


@app.delete("/api/v1/user-products/{account_unique_id}/{product_id}")
async def delete_user_product(
                        product_id: int,
                        account_unique_id: str,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)):
    """
    Delete UserProduct
    """
    response = prod_utils.delete_user_product_from_db(account_unique_id, product_id, session)
    if response.get('error'):
        return {"error": response['error'],
                'product_id': product_id}
    
    return {'response': 'success',
            'product_id': product_id}


############################################
#  MailerLite Routes
############################################

@app.post("/api/v1/mailerlite/webhook/")
async def receiving_webhook(request: Request, session: Session = Depends(get_session)):
    """
    Webhooks received into our expertecho account - Internal use only
    """
    try:
        payload = await request.json()
        print("DEBUG: Received MailerLite webhook payload:", payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # ScoreApp Quiz Finished Event
    if payload.get("event_name") == "QUIZ_FINISHED":

        data = payload.get("data", {})

        # Extract lead details directly from data
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        full_name = data.get("full_name", "")  # Often provided as fallback
        email = data.get("email", "")

        # Check if subscriber already exists
        existing_subscriber = get_subscriber(email)
        if not existing_subscriber:
            # Add subscriber to MailerLite
            subscriber = add_subscriber(email=email, fields={"name": first_name, "last_name": last_name})
            if not subscriber:
                raise HTTPException(status_code=500, detail="Failed to add subscriber to MailerLite")
        else:
            update_subscriber(email=email, fields={"name": first_name, "last_name": last_name})

        # Add subscriber to Waiting List group
        try:
            assign_subscriber_to_group(email=email, group_id=int(os.getenv("MAILERLITE_WAITING_LIST_GROUP_ID")))
        except ValueError as e:
            print(f"DEBUG: Error assigning subscriber {email} to Waiting List group: {e}")
            return {"error": str(e)}
        
    elif not payload.get("event_name"):

        # New Enquiries Event
        if payload.get("visitorUuid"):

            # Extract lead details
            first_name = payload.get("name", "")
            email = payload.get("email", "")

            # Check if subscriber already exists
            existing_subscriber = get_subscriber(email)
            if not existing_subscriber:
                # Add subscriber to MailerLite
                subscriber = add_subscriber(email=email, fields={"name": first_name})
                if not subscriber:
                    raise HTTPException(status_code=500, detail="Failed to add subscriber to MailerLite")
            
            else:
                update_subscriber(email=email, fields={"name": first_name})
            
            # Add subscriber to New Enquiries List group
            try:
                assign_subscriber_to_group(email=email, group_id=int(os.getenv("MAILERLITE_NEW_ENQUIRIES_GROUP_ID")))
            except ValueError as e:
                print(f"DEBUG: Error assigning subscriber {email} to New Enquiries List group: {e}")
                return {"error": str(e)}
            
        # Unanswered Questions Event
        elif payload.get("contact_info"):

            # Extract lead details
            contact_info = payload.get("contact_info", {})
            print("DEBUG: contact_info: ", contact_info)
            first_name = contact_info.get("name", "")
            print("DEBUG: first_name: ", first_name)
            email = contact_info.get("email", "")
            print("DEBUG: email: ", email)

            # Check if subscriber already exists
            existing_subscriber = get_subscriber(email)
            if not existing_subscriber:
                # Add subscriber to MailerLite
                subscriber = add_subscriber(email=email, fields={"name": first_name})
                if not subscriber:
                    raise HTTPException(status_code=500, detail="Failed to add subscriber to MailerLite")
            
            else:
                update_subscriber(email=email, fields={"name": first_name})
            # Add subscriber to New Enquiries List group
            try:
                assign_subscriber_to_group(email=email, group_id=int(os.getenv("MAILERLITE_UNANSWERED_QUESTIONS_GROUP_ID")))
            except ValueError as e:
                print(f"DEBUG: Error assigning subscriber {email} to Unanswered Questions List group: {e}")
                return {"error": str(e)}

    return {"response": "success"}

############################################
#  Reporting Routes
############################################

@app.get("/api/v1/reporting/wordcloud/{account_unique_id}")
async def generate_wordcloud(account_unique_id: str,
                             current_user: Annotated[User, Depends(get_current_active_user)],
                             session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Get Wordcloud Data for an Account
    """
    s3_key = f"wordclouds/{account_unique_id}_last7days.png"
    
    # Get Wordcloud Data
    wordcloud_data = query_utils.generate_wordcloud_data(account_unique_id, session)

    if not wordcloud_data or isinstance(wordcloud_data, dict) and "error" in wordcloud_data:
        raise HTTPException(
            status_code=404,
            detail=wordcloud_data.get("error", "No wordcloud data available")
        )
    
    # Generate Wordcloud
    wordcloud = WordCloud(
        width=1200, 
        height=600, 
        background_color='white', 
        max_words=200,
        collocations=False,
        colormap='plasma',
        ).generate_from_frequencies(wordcloud_data)

    # Save Wordcloud Image
    img_buffer = BytesIO()
    wordcloud.to_image().save(img_buffer, format="PNG")
    img_buffer.seek(0)


    url = s3_services.upload_bytes_to_s3(
        data=img_buffer.getvalue(),
        key=s3_key,
        content_type="image/png"
    )

    return {"response": "success", "wordcloud_url": url}