import os
import shutil
from typing import Any, Union
from secrets import token_hex
from fastapi import FastAPI, UploadFile, Depends, File, Body, HTTPException, APIRouter
from sqlmodel import select, Session
from file_management.models import SourceFile
from file_management.utils import save_file_to_db, update_file_in_db, delete_file_from_db
from accounts.models import Account, User
from accounts.utils import create_new_account_in_db, update_account_in_db, delete_account_from_db, \
    create_new_user_in_db, update_user_in_db, delete_user_from_db
from create_database import generate_chroma_db
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


@app.get("/api/v1/query-data/{account_unique_id}")
async def query_data(query: str, account_unique_id: str) -> dict[str, Any]:
    """
    Query Data
    """
    if not query:
        return {"error": "No query provided"}
    
    response = query_source_data.query_source_data(query, account_unique_id)
    print(response)
    return response


@app.get("/api/v1/generate-chroma-db/{account_unique_id}")
async def generate_chroma_db_datastore(account_unique_id: str, replace: bool = False) -> dict[str, Any]:
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
async def clear_chroma_db_datastore(account_unique_id: str) -> dict[str, Any]:
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
async def get_files(account_unique_id: str, session: Session = Depends(get_session)):
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
async def get_file(account_unique_id: str, file_id: int, session: Session = Depends(get_session)):
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


# @app.post("/api/v1/files/{account_unique_id}")
# async def upload_file(
#     account_unique_id: str,
#     file: UploadFile = File(...),
#     session: Session = Depends(get_session)):
#     """
#     Upload File
#     """
#     if not file:
#         return {"error": "No file provided"}
    
#     file_ext = file.filename.split('.')[-1]
#     # if file_ext != 'md':
#     #     return {"error": "File must be a markdown file"}
    
#     file_name = file.filename.rsplit('.', 1)[0]
#     file_name = f'{file_name}_{token_hex(8)}.{file_ext}'
#     directory = f'./files/{account_unique_id}'
#     file_path = os.path.join(directory, file_name)
#     file_account = account_unique_id
    
#     os.makedirs(directory, exist_ok=True)

#     with open(file_path, "wb") as buffer:
#         content = await file.read()
#         buffer.write(content)
    
#     db_file = save_file_to_db(file_name, file_path, file_account, session)
    
#     return {"response": "success",
#             "file_name": file_name,
#             "file_path": file_path,
#             "file_id": db_file.id}


@app.post("/api/v1/files/{account_unique_id}")
async def upload_files(
    account_unique_id: str,
    files: list[UploadFile] = File(...),  # Accepting a list of files
    session: Session = Depends(get_session)):
    """
    Upload Multiple Files
    """
    if not files:
        return {"error": "No files provided"}
    
    uploaded_files_info = []  # To store information about all uploaded files
    
    directory = f'./files/{account_unique_id}'
    os.makedirs(directory, exist_ok=True)
    
    for file in files:
        file_ext = file.filename.split('.')[-1]
        
        # Generate unique file name
        file_name = file.filename.rsplit('.', 1)[0]
        file_name = f'{file_name}_{token_hex(8)}.{file_ext}'
        file_path = os.path.join(directory, file_name)
        file_account = account_unique_id

        # Write file to the disk
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Save file information to the database
        db_file = save_file_to_db(file_name, file_path, file_account, session)
        
        # Collect file details for response
        uploaded_files_info.append({
            "file_name": file_name,
            "file_path": file_path,
            "file_id": db_file.id
        })
    
    return {"response": "success", "uploaded_files": uploaded_files_info}


@app.put("/api/v1/files/{account_unique_id}/{file_id}", response_model=Union[SourceFile, dict])
async def update_file(file_id: int,
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
async def delete_file(account_unique_id: str, file_id: int, session: Session = Depends(get_session)):
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


@app.put("/api/v1/accounts/{account_unique_id}", response_model=Union[Account, dict])
async def edit_account(account_unique_id: str, updated_account: Account, session: Session = Depends(get_session)):
    """
    Edit Account
    """
    account = session.get(Account, account_unique_id)

    account = update_account_in_db(account_unique_id, updated_account, session)
    
    return account


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


@app.put("/api/v1/users/{account_unique_id}/{user_id}", response_model=Union[User, dict])
async def edit_user(account_unique_id: str, user_id: int, updated_user: User, session: Session = Depends(get_session)):
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