import os
from typing import Any, Union, Annotated
from secrets import token_hex
import shutil
import jwt
import boto3
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, UploadFile, Depends, File, Body, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from sqlmodel import select, Session
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from passlib.context import CryptContext
from pydantic import BaseModel
from file_management.models import SourceFile
from file_management.utils import save_file_to_db, update_file_in_db, delete_file_from_db, \
    fetch_html_content, extract_text_from_html, prepare_for_s3_upload
from accounts.models import Account, User
from accounts.utils import create_new_account_in_db, update_account_in_db, delete_account_from_db, \
    create_new_user_in_db, update_user_in_db, delete_user_from_db
from create_database import generate_chroma_db
from db import engine
import query_data.query_source_data as query_source_data

# Initialize the S3 client
s3 = boto3.client('s3')

# The name of your S3 bucket
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')


app = FastAPI()


############################################
#  Authentication
############################################

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Dependency
def get_session():
    """
    Get Session
    """
    with Session(engine) as session:
        yield session
        


############################################
#  Authentication Routes
############################################


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


def verify_password(plain_password, hashed_password):
    """
    Verify Password
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    Get Password Hash
    """
    return pwd_context.hash(password)



@app.get("/api/v1/root")
async def read_root(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Root Route
    """
    return {"token": token}
    

def get_auth_user(user_email: str, session: Session = Depends(get_session)):
    """
    Get Auth User
    """
    statement = select(User).where(User.user_email == user_email)
    result = session.exec(statement)
    user = result.first()
    if user:
        user_dict = user.model_dump()
        return user_dict
    return None


def authenticate_user(user_email: str, password: str, session: Session = Depends(get_session)):
    """
    Authenticate User
    """
    user = get_auth_user(user_email, session=session)
    if not user:
        return False
    if not verify_password(password, user['user_password']):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Create Access Token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: Session = Depends(get_session)):
    """
    Get Current User
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None:
            raise credentials_exception
        token_data = TokenData(username=user_email)
    except InvalidTokenError:
        raise credentials_exception
    user = get_auth_user(token_data.username, session=session)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get Current Active User
    """
    return current_user


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
    return Token(access_token=access_token, token_type="bearer")


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
async def get_files(account_unique_id: str, current_user: Annotated[User, Depends(get_current_active_user)],
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


@app.post("/api/v1/files/{account_unique_id}")
async def upload_files(account_unique_id: str,
                       current_user: Annotated[User, Depends(get_current_active_user)],
                       files: list[UploadFile] = File(...),
                       session: Session = Depends(get_session)):
    """
    Upload Multiple Files to S3 in a subfolder for the given account_unique_id,
    and store metadata in the database.
    """
    if not files:
        return {"error": "No files provided"}
    
    uploaded_files_info = []  # To store information about all uploaded files

    for file in files:
        try:
            file_ext = file.filename.split('.')[-1]
            
            # Generate unique file name
            file_name = file.filename.rsplit('.', 1)[0]
            unique_file_name = f'{file_name}_{token_hex(8)}.{file_ext}'
            file_account = account_unique_id

            # Simulate the subfolder by including account_unique_id in the S3 key
            s3_key = f"{account_unique_id}/{unique_file_name}"

            # Read the file content
            content = await file.read()

            # Upload file to S3, saving it under the account_unique_id "folder"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,  # Upload to account subfolder
                Body=content,
                ContentType=file.content_type
            )

            # Get the S3 file URL
            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"

            # Save file information to the database (adjust this function to your schema)
            db_file = save_file_to_db(unique_file_name, file_url, file_account, session)

            # Collect file details for response
            uploaded_files_info.append({
                "file_name": unique_file_name,
                "file_url": file_url,
                "file_id": db_file.id
            })
        
        except NoCredentialsError:
            raise HTTPException(status_code=400, detail="AWS credentials not found")
        except PartialCredentialsError:
            raise HTTPException(status_code=400, detail="Incomplete AWS credentials")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

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
    statement = select(Account).filter()
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
    statement = select(User).filter()
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
                      current_user: Annotated[User, Depends(get_current_active_user)],
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