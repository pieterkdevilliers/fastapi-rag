import os
import shutil
from typing import Any
from secrets import token_hex
from fastapi import FastAPI, UploadFile, Depends, File
from sqlmodel import select, Session
from file_management.models import SourceFile
from file_management.utils import save_file_to_db
from accounts.models import Account, User
from accounts.utils import create_new_account_in_db, update_account_in_db, delete_account_from_db, \
    create_new_user_in_db, update_user_in_db, delete_user_from_db
from db import engine
import query_data.query_source_data as query_source_data


app = FastAPI()

# Define the upload directory
UPLOAD_DIR = "data"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Dependency
def get_session():
    """
    Get Session
    """
    with Session(engine) as session:
        yield session


############################################
# Main Routes
############################################

@app.get("/api/v1/root")
async def read_root():
    """
    Root Route
    """
    return {"Hello": "World"}


@app.get("/api/v1/query-data")
async def query_data(query: str) -> dict[str, Any]:
    """
    Query Data
    """
    if not query:
        return {"error": "No query provided"}
    
    response = query_source_data.query_source_data(query)
    print(response)
    return response

############################################
# File Management Routes
############################################

@app.get("/api/v1/get-files")
async def get_files(session: Session = Depends(get_session)):
    """
    Get All Files
    """
    returned_files = []
    statement = select(SourceFile).filter()
    result = session.exec(statement)
    files = result.all()
    for file in files:
        returned_files.append(file)
    print(type(returned_files))

    if not returned_files:
        return {"error": "No files found",
                "files": returned_files}
    
    return {"files": returned_files}


@app.post("/api/v1/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)):
    """
    Upload File
    """
    if not file:
        return {"error": "No file provided"}
    
    file_ext = file.filename.split('.')[-1]
    if file_ext != 'md':
        return {"error": "File must be a markdown file"}
    
    file_name = file.filename.rsplit('.', 1)[0]
    file_name = f'{file_name}_{token_hex(8)}.{file_ext}'
    file_path = f'./files/{file_name}'

    db_file = save_file_to_db(file_name, file_path, session)
    
    return {"response": "success",
            "file_name": file_name,
            "file_path": file_path,
            "file_id": db_file.id}


############################################
# Accounts Routes
############################################

@app.get("/api/v1/accounts")
async def get_accounts(session: Session = Depends(get_session)):
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


@app.put("/api/v1/accounts/{account_organisation}/{account_unique_id}")
async def edit_account(account_organisation: str, account_unique_id: str, session: Session = Depends(get_session)):
    """
    Edit Account
    """
    account = update_account_in_db(account_organisation, account_unique_id, session)
    
    return {"response": "success",
            "account": account,
            "account_organisation": account.account_organisation,
            "account_unique_id": account.account_unique_id}


@app.delete("/api/v1/accounts/{account_unique_id}")
async def delete_account(account_unique_id: str, session: Session = Depends(get_session)):
    """
    Delete Account
    """
    response = delete_account_from_db(account_unique_id, session)
    return {'response': 'success',
            'account_unique_id': response['account_unique_id']}


@app.get("/api/v1/accounts/{account_unique_id}")
async def get_account(account_unique_id: str, session: Session = Depends(get_session)):
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
async def get_users(session: Session = Depends(get_session)):
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
async def create_user(account_unique_id: str, user_email: str, user_password: str, session: Session = Depends(get_session)):
    """
    Create User
    """
    user = create_new_user_in_db(user_email, user_password, account_unique_id, session)
    
    return {"response": "success",
            "user": user,
            "user_email": user.user_email,
            "user_id": user.id}


@app.put("/api/v1/users/{account_unique_id}/{user_id}/{user_email}/{user_password}")
async def edit_user(account_unique_id: str, user_id: int, user_email: str, user_password: str, session: Session = Depends(get_session)):
    """
    Edit User
    """
    user = update_user_in_db(user_id, user_email, user_password, account_unique_id, session)
    
    return {"response": "success",
            "user": user,
            "user_email": user.user_email,
            "user_id": user.id}


@app.delete("/api/v1/users/{account_unique_id}/{user_id}")
async def delete_user(account_unique_id: str, user_id: int, session: Session = Depends(get_session)):
    """
    Delete User
    """
    response = delete_user_from_db(account_unique_id, user_id, session)
    
    return {"response": "success",
            "user_id": response['user_id']}


@app.get("/api/v1/users/{account_unique_id}/{user_id}")
async def get_user(account_unique_id: str, user_id: int, session: Session = Depends(get_session)):
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