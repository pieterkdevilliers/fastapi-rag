import os
import json
import tempfile
import stripe
import secrets
import chromadb
from bs4 import BeautifulSoup
from typing import Any, Union, Annotated, List, Optional
from datetime import datetime, timezone
from secrets import token_hex
import shutil
import boto3
import convert_to_pdf
import io
from mailerlite_services import sync_to_mailerlite, delete_subscriber_from_mailerlite, update_active_customer_groups, update_cancelled_customer_groups
from aws_ses_service import EmailService, get_email_service
from datetime import timedelta
from fastapi import FastAPI, UploadFile, Depends, File, Body, HTTPException, status, Request, Security, responses
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
from accounts.models import Account, User, WidgetAPIKey, StripeSubscription
from accounts.utils import create_new_account_in_db, update_account_in_db, delete_account_from_db, \
    create_new_user_in_db, update_user_in_db, delete_user_from_db, get_notification_users, get_user_by_email, \
    create_password_reset_token, get_reset_token, update_user_password, delete_reset_token, get_account_by_account_unique_id, \
    check_active_subscription_status, get_account_webhook_url
# from create_database import generate_chroma_db
from db import engine
import query_data.query_source_data as query_source_data
from authentication import oauth2_scheme, Token, authenticate_user, get_password_hash, create_access_token, \
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES, get_widget_api_key_user, get_api_key_hash, get_api_key, get_internal_api_key
from dependencies import get_session
from chat_messages.models import ChatSession, ChatMessage
from chat_messages.utils import create_or_identify_chat_session, create_chat_message, get_session_id_by_visitor_uuid, \
    get_chat_messages_by_session_id, get_chat_session_count, get_questions_answered_count, create_email_message, \
    get_email_message_count
from stripe_service import process_stripe_product_created_event, process_stripe_product_updated_event, get_stripe_price_object_from_price_id, \
    process_stripe_subscription_checkout_session_completed_event, get_stripe_subscription_from_subscription_id, \
    process_retrieved_stripe_subscription_data, process_stripe_subscription_invoice_paid_event, add_account_unique_id_to_subscription, \
    process_stripe_subscription_updated_event, process_stripe_subscription_deleted_event, process_in_app_subscription_cancellation, \
    get_stripe_customer_from_customer_id
from core.models import Product, PasswordResetToken, ContactPayload
from core.utils import create_stripe_subscription_in_db, get_db_subscription_by_subscription_id, update_stripe_subscription_in_db
from chroma_db_api import clear_chroma_db_datastore_for_replace
from webhook_utils import send_chat_messages_webhook_notification


# Initialize the S3 client
s3 = boto3.client('s3')

#Stripe Setup
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# The name of your S3 bucket
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
lambda_client = boto3.client("lambda", region_name="us-east-1")

# Front-end Env Settings
FE_BASE_URL = os.getenv('FE_BASE_URL', 'http://localhost:3000')  # Default to localhost if not set

CHROMA_SERVER_AUTHN_CREDENTIALS = os.environ['CHROMA_SERVER_AUTHN_CREDENTIALS']
chroma_headers = {'X-Chroma-Token': CHROMA_SERVER_AUTHN_CREDENTIALS}
CHROMA_ENDPOINT = os.environ['CHROMA_ENDPOINT']

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend's origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
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
    user = authenticate_user(form_data.username, form_data.password, session=session)
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
    return Token(account_unique_id=account_unique_id, account_organisation=organisation, docs_count=docs_count, active_subscription=active_subscription, processed_docs_count=processed_docs_count, access_token=access_token, token_type="bearer")


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
    return {"api_key": api_key, "account_unique_id": account_unique_id, "allowed_origins": api_key_create_request.allowed_origins}


@app.get("/api/v1/list-api-keys/{account_unique_id}")
async def list_api_keys(account_unique_id: str,
                        current_user: Annotated[User, Depends(get_current_active_user)],
                        session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    List API Keys
    """
    statement = select(WidgetAPIKey).where(WidgetAPIKey.account_unique_id == account_unique_id)
    result = session.exec(statement)
    api_keys = result.all()
    return {"api_keys": api_keys}


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
    session.delete(api_key)
    session.commit()
    return {"message": "API Key deleted successfully"}


class APIKeyUpdateRequest(BaseModel):
    name: str = None
    allowed_origins: List[str] = None


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
    
    return {"message": "API Key updated successfully", "api_key": api_key}

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


# Queries received from the web widget
@app.post("/api/v1/widget/query") # Or your existing endpoint
async def process_widget_query(
                                payload: WidgetQueryPayload,
                                auth_info: dict = Security(get_widget_api_key_user),
                                session: Session = Depends(get_session)
                                ):
    account_unique_id = auth_info["account_unique_id"]
    query = payload.query.strip() if payload.query else None

    if not query:
        return {"error": "No query provided"}
    active_subscription = check_active_subscription_status(account_unique_id, session)
    if active_subscription:
        response = query_source_data.query_source_data(query, account_unique_id, session)
    else:

        recipients = get_notification_users(auth_info["account_unique_id"], session)
        if not recipients:
            raise HTTPException(status_code=404, detail="No notification users found for this account")
    
        email_service = get_email_service()

        try:
            for recipient in recipients:
                email_service.send_unsubscribed_widget_email(recipient['user_email'], 'www.yourdocsai.app/login?redirect=/accounts')

        except Exception as e:
            print(f"ERROR sending email: {e}") 
            raise HTTPException(status_code=500, detail=str(e))

        response = {
                "response": {
                    "response_text": "Unable to process your query at this time, please contact us via email."
                }
            }

    return response


@app.get("/api/v1/generate-chroma-db/{account_unique_id}")
async def generate_chroma_db_datastore(account_unique_id: str,
                                       current_user: Annotated[User, Depends(get_current_active_user)],
                                       replace: bool = False,
                                       session: Session = Depends(get_session)) -> dict[str, Any]:
    """
    Generate Chroma DB
    """
    print(f"Received request to generate Chroma DB for account {account_unique_id} with replace={replace}")
    
    try:
        documents_from_s3 = await load_documents_from_s3(account_unique_id=account_unique_id, replace=replace, session=session)

        if replace:
            try:
                print("Clearing ChromaDB before replacing")
                clear_chroma_db_datastore_for_replace(account_unique_id=account_unique_id)
            except Exception as e:
                error_message = f"ERROR: Failed to invoke Lambda: {e}"
                print(error_message)
                return {"status": "error", "message": error_message}
        

        print(f"Loaded {len(documents_from_s3)} documents from S3 based on DB query.")
        for db_file in documents_from_s3:
            # Construct S3 key (path in S3) using account_unique_id and file name
            s3_key = f"{account_unique_id}/{db_file.file_name}"
            print(f"Attempting to trigger Lambda for file: {s3_key}")

            # The payload our Lambda expects
            lambda_payload = {
                "s3_bucket": BUCKET_NAME,
                "s3_key": s3_key,
                "account_unique_id": account_unique_id,
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

        # response = await generate_chroma_db(account_unique_id, replace)
        # print(f"Chroma DB generation successful: {response}")
    except Exception as e:
        print(f"Error generating Chroma DB: {e}")
        return {"error": str(e)}
    
    return response


@app.get("/api/v1/clear-chroma-db/{account_unique_id}")
async def clear_chroma_db_datastore(account_unique_id: str, current_user: Annotated[User, Depends(get_current_active_user)]) -> dict[str, Any]:
    """
    Clear Chroma DB
    """
    print(f"Received request to clear Chroma DB for account {account_unique_id}")
    print(f"Connecting to ChromaDB at {CHROMA_ENDPOINT}...")
    chroma_client = chromadb.HttpClient(
        host=CHROMA_ENDPOINT,
        headers=chroma_headers
    )

    print(f"Successfully connected to ChromaDB.")
    collection_name = f"collection-{account_unique_id}"
    
    try:
        # This is the correct way to delete a collection from the ChromaDB server.
        chroma_client.delete_collection(name=collection_name)
        print(f"Successfully deleted collection: {collection_name}")
        return {"response": f"success, collection '{collection_name}' deleted"}

    except ValueError as e:
        # The chromadb client raises a ValueError if the collection doesn't exist.
        # This is not necessarily an error in our endpoint's logic.
        print(f"Attempted to delete a non-existent collection: {collection_name}. Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_name}' not found for this account."
        )
    except Exception as e:
        # Catch other potential errors (e.g., network issues connecting to Chroma)
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while trying to clear the database."
        )
    


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
    if not recipients:
        raise HTTPException(status_code=404, detail="No notification users found for this account")
    
    chat_session_id = get_session_id_by_visitor_uuid(
        account_unique_id=auth_info["account_unique_id"],
        visitor_uuid=payload.visitorUuid,
        session=session
    )

    if not chat_session_id:
        print(f"No chat session found for visitor UUID {payload.visitorUuid} in account {auth_info['account_unique_id']}.")
        chat_session_id = create_or_identify_chat_session(
            account_unique_id=auth_info["account_unique_id"],
            visitor_uuid=payload.visitorUuid,
            session=session
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
        response = delete_file_from_db(account_unique_id, file_id, session)
        new_docs_count = get_docs_count_for_user_account(account_unique_id, session)
        return {'response': 'success',
                'file_id': response['file_id'], 'new_docs_count': new_docs_count}
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
    response = delete_account_from_db(account_unique_id, session)
    return {'response': 'success',
            'account_unique_id': response['account_unique_id']}


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
    user = create_new_user_in_db(payload.user_email, user_password, account_unique_id, session, receive_notifications)
    user_type = 'additional_user'
    company = get_account_by_account_unique_id(account_unique_id, session).account_organisation
    sync_to_mailerlite(email=payload.user_email, company=company, account_unique_id=account_unique_id, user_type=user_type, session=session)

    return {"response": "success",
            "user": user,
            "user_email": user.user_email,
            "user_id": user.id}


@app.post("/api/v1/first-user/{account_unique_id}")
async def create_first_user(account_unique_id: str, 
                      payload: UserCreatePayload = Body(...),
                      session: Session = Depends(get_session)):
    """
    Create User
    """
    receive_notifications = True  # Default to True for first user
    user_password = get_password_hash(payload.user_password)
    user = create_new_user_in_db(payload.user_email, user_password, account_unique_id, session, receive_notifications)
    user_type = 'first_user'
    company = get_account_by_account_unique_id(account_unique_id, session).account_organisation
    if not company:
        raise HTTPException(status_code=404, detail="Account not found")
    sync_to_mailerlite(email=payload.user_email, company=company, account_unique_id=account_unique_id, user_type=user_type, session=session)

    return {"response": "success",
            "user": user,
            "user_email": user.user_email,
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
        account_unique_id=account_unique_id, 
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
            print(f"Created new subscription: {subscription} for account: {subscription.account_unique_id}")
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