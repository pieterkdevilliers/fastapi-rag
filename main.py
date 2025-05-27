import os
import subprocess
import tempfile
from typing import Any, Union, Annotated
from secrets import token_hex
import shutil
import boto3
import convert_to_pdf
import io
from datetime import timedelta
from fastapi import FastAPI, UploadFile, Depends, File, Body, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import select, Session
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from pydantic import BaseModel
from file_management.models import SourceFile, Folder
from file_management.utils import save_file_to_db, update_file_in_db, delete_file_from_db, \
    fetch_html_content, extract_text_from_html, prepare_for_s3_upload, create_new_folder_in_db, \
    update_folder_in_db, delete_folder_from_db
from accounts.models import Account, User
from accounts.utils import create_new_account_in_db, update_account_in_db, delete_account_from_db, \
    create_new_user_in_db, update_user_in_db, delete_user_from_db
from create_database import generate_chroma_db
from db import engine
import query_data.query_source_data as query_source_data
from authentication import oauth2_scheme, Token, authenticate_user, get_password_hash, create_access_token, \
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
from dependencies import get_session
    

# Initialize the S3 client
s3 = boto3.client('s3')

# The name of your S3 bucket
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')


app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Replace with your frontend's origin
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
    

@app.post("/token")
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
    return Token(account_unique_id=account_unique_id, access_token=access_token, token_type="bearer")


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


@app.get("/api/v1/generate-chroma-db/{account_unique_id}")
async def generate_chroma_db_datastore(account_unique_id: str,
                                       current_user: Annotated[User, Depends(get_current_active_user)],
                                       replace: bool = False) -> dict[str, Any]:
    """
    Generate Chroma DB
    """
    print(f"Received request to generate Chroma DB for account {account_unique_id} with replace={replace}")
    
    try:
        response = await generate_chroma_db(account_unique_id, replace)
        print(f"Chroma DB generation successful: {response}")
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
    
    chroma_path = f"./chroma/{account_unique_id}"
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        return {"response": "success"}
    
    else:
        return {"error": "Chroma DB not found"}

############################################
# File Management Routes
############################################

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


@app.post("/api/v1/files/{account_unique_id}/{folder_id}")
async def upload_files(account_unique_id: str,
                       folder_id: int,
                       current_user: Annotated[User, Depends(get_current_active_user)],
                       files: list[UploadFile] = File(...),
                       session: Session = Depends(get_session)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded_files_info = []

    for original_file in files:
        original_filename = original_file.filename
        original_file_ext = original_filename.split('.')[-1].lower()
        file_base_name = original_filename.rsplit('.', 1)[0]

        # New unique filename will always have .pdf extension
        unique_pdf_filename = f'{file_base_name}_{token_hex(8)}.pdf'.lower()
        s3_key = f"{account_unique_id}/{unique_pdf_filename}"
        
        pdf_content_bytes = None
        temp_input_file = None
        temp_output_dir = None

        try:
            original_content = await original_file.read()

            if original_file_ext == 'pdf':
                pdf_content_bytes = original_content
                final_content_type = 'application/pdf'
            else:
                # For non-PDFs, we need to convert
                # Create a temporary directory for input and output of conversion
                temp_output_dir = tempfile.mkdtemp()
                temp_input_file_path = None

                if original_file_ext in ['doc', 'docx']: # Add other Pandoc supported types
                        # 1. Write original content to a temporary file for Pandoc
                        # Ensure the suffix matches the original file extension for Pandoc to potentially auto-detect
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{original_file_ext}", dir=temp_output_dir) as temp_input_file_obj:
                            temp_input_file_obj.write(original_content)
                            temp_input_file_path = temp_input_file_obj.name

                        
                        # 2. Convert DOCX/DOC/etc. to HTML using Pandoc
                        temp_html_file_path = convert_to_pdf.convert_to_html_pandoc(
                            input_path=temp_input_file_path,
                            output_dir=temp_output_dir,
                            input_format=original_file_ext
                        )
                        
                        # 3. Convert the HTML (from Pandoc) to PDF using WeasyPrint
                        final_temp_pdf_path = os.path.join(temp_output_dir, "final_converted_document.pdf")
                        convert_to_pdf.convert_html_to_pdf_weasyprint(
                            html_input=temp_html_file_path, # Pass the path to the HTML file
                            output_pdf_path=final_temp_pdf_path,
                            is_file_path=True # Indicate that html_input is a file path
                        )
                        
                        with open(final_temp_pdf_path, 'rb') as f_pdf:
                            pdf_content_bytes = f_pdf.read()
                        final_content_type = 'application/pdf' # Output is always PDF
                        
                        # Clean up the converted PDF immediately after reading
                        if os.path.exists(final_temp_pdf_path):
                            os.remove(final_temp_pdf_path)

                elif original_file_ext == 'txt':
                    converted_pdf_path = os.path.join(temp_output_dir, "converted.pdf")
                    convert_to_pdf.convert_text_to_pdf(original_content.decode('utf-8', errors='replace'), converted_pdf_path) # Ensure decoding
                    with open(converted_pdf_path, 'rb') as f_pdf:
                        pdf_content_bytes = f_pdf.read()
                    final_content_type = 'application/pdf'
                    if os.path.exists(converted_pdf_path): os.remove(converted_pdf_path)

                elif original_file_ext == 'md':
                    converted_pdf_path = os.path.join(temp_output_dir, "converted.pdf")
                    convert_to_pdf.convert_markdown_to_pdf(original_content.decode('utf-8', errors='replace'), converted_pdf_path) # Ensure decoding
                    with open(converted_pdf_path, 'rb') as f_pdf:
                        pdf_content_bytes = f_pdf.read()
                    final_content_type = 'application/pdf'
                    if os.path.exists(converted_pdf_path): os.remove(converted_pdf_path)
                
                else:
                    # If format is not supported for conversion, you can choose to:
                    # 1. Reject the file
                    # 2. Upload as-is (but then frontend needs to handle it)
                    # For this strategy, we'll reject unsupported types for PDF conversion
                    raise HTTPException(status_code=400, detail=f"File type '.{original_file_ext}' is not supported for PDF conversion.")

                # Clean up temporary input file if created
                if temp_input_file_path and os.path.exists(temp_input_file_path):
                    os.remove(temp_input_file_path)


            if not pdf_content_bytes:
                raise HTTPException(status_code=500, detail=f"Failed to obtain PDF content for {original_filename}")

            # Upload the (potentially converted) PDF content to S3
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=pdf_content_bytes,
                ContentType=final_content_type # Should always be 'application/pdf' now
            )

            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
            
            # Save file information to the database
            # The 'unique_pdf_filename' is what you store as the filename
            db_file = save_file_to_db(unique_pdf_filename, file_url, account_unique_id, folder_id, session)

            uploaded_files_info.append({
                "file_name": unique_pdf_filename, # This is now always a .pdf file
                "original_filename": original_filename, # Good to keep for user reference
                "file_url": file_url,
                "file_id": db_file.id
            })

        except HTTPException: # Re-raise HTTPExceptions
            raise
        except NoCredentialsError:
            raise HTTPException(status_code=500, detail="AWS credentials not found") # 500 for server config issues
        except PartialCredentialsError:
            raise HTTPException(status_code=500, detail="Incomplete AWS credentials")
        except RuntimeError as e: # Catch RuntimeError from LibreOffice check
             raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            print(f"Error processing file {original_filename}: {str(e)}") # Log the full error
            # For other exceptions, provide a more generic message to the user
            raise HTTPException(status_code=500, detail=f"An error occurred while processing file: {original_filename}. Details: {str(e)}")
        finally:
            # Clean up temporary directory
            if temp_output_dir and os.path.exists(temp_output_dir):
                # Safety: Ensure all files within are removed before rmtree
                for root, dirs, files_in_dir in os.walk(temp_output_dir, topdown=False):
                    for name in files_in_dir:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(temp_output_dir)


    return {"response": "success", "uploaded_files": uploaded_files_info}


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
        
    response = delete_file_from_db(account_unique_id, file_id, session)
    return {'response': 'success',
            'file_id': response['file_id']}


@app.api_route("/api/v1/files/view/{account_unique_id}/{file_identifier}",
                    response_class=StreamingResponse,
                    summary="View a specific document from S3",
                    tags=["Documents"],
                    methods=["GET", "HEAD"])
async def stream_file_from_s3(account_unique_id: str, file_identifier: str,
                   current_user: Annotated[User, Depends(get_current_active_user)],
                   session: Session = Depends(get_session)):
    """
    Get File By S3 key identifier
    """
    if hasattr(current_user, 'account_unique_id') and current_user.account_unique_id != account_unique_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You are not authorized to access files for this account."
        )
    

        try:
        # For a HEAD request, we only need metadata, not the whole body initially.
        # However, to get ContentLength and ContentType reliably for the response headers,
        # S3's head_object is more efficient than get_object if we only need headers.
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
            # For HEAD, FastAPI/Starlette will automatically strip the body
            # We just need to provide the headers.
            # Returning an empty StreamingResponse or even just a Response with headers is fine.
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

    # try:
    #     s3_object = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
    # except s3.exceptions.NoSuchKey:
    #     print(f"S3 Error: NoSuchKey for Key='{s3_key}'")
    #     raise HTTPException(status_code=404, detail=f"File '{file_identifier}' not found.")
    # except Exception as e:
    #     print(f"S3 Error fetching Key='{s3_key}': {e}")
    #     raise HTTPException(status_code=500, detail=f"Error accessing file: {str(e)}")

    # file_content_bytes = s3_object['Body'].read()
    
    # # Assuming all files retrieved via this endpoint are PDFs due to earlier conversion
    # content_type = s3_object.get('ContentType', 'application/pdf') # Default to application/pdf
    # if not content_type.lower().startswith('application/pdf'):
    #     print(f"Warning: S3 ContentType for '{s3_key}' is '{content_type}'. Forcing 'application/pdf' for response.")
    #     content_type = 'application/pdf'


    # response_headers = {
    #     "Content-Disposition": f"inline; filename=\"{file_identifier}\"", # Use the identifier as filename
    #     "Content-Type": content_type
    # }

    # return StreamingResponse(
    #     io.BytesIO(file_content_bytes),
    #     media_type=content_type,
    #     headers=response_headers
    # )
    
    
class URLRequest(BaseModel):
    """
    URL Request
    """
    url: str
    
@app.post("/api/v1/get-text-from-url/{account_unique_id}")
async def get_text_from_url(request: URLRequest, account_unique_id: str,
                            current_user: Annotated[User, Depends(get_current_active_user)],
                            session: Session = Depends(get_session)):
    """
    Get Text from URL
    """
    url = request.url
    html_content = await fetch_html_content(url)
    extracted_text = await extract_text_from_html(html_content)
    saved_file = await prepare_for_s3_upload(extracted_text['text'], extracted_text['title'], account_unique_id, session)
    # saved_file = await save_text_to_file(extracted_text['text'], extracted_text['title'], account_unique_id, url, session)
    print(f"Received request to get text from URL: {request.url}")
    return {"response": "success", "url": request.url}


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
        return {"response": "success",
                "folders": folders}


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
    account = session.get(Account, account_unique_id)

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


@app.post("/api/v1/users/{account_unique_id}/{user_email}/{user_password}")
async def create_user(account_unique_id: str, user_email: str, user_password: str,
                      current_user: Annotated[User, Depends()],
                      session: Session = Depends(get_session)):
    """
    Create User
    """
    user_password = get_password_hash(user_password)
    user = create_new_user_in_db(user_email, user_password, account_unique_id, session)
    
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
