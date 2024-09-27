import os
import shutil
from typing import Any
from secrets import token_hex
from fastapi import FastAPI, UploadFile, Depends, File
from sqlmodel import select, Session
from file_management.models import SourceFile
from file_management.utils import save_file_to_db
from accounts.models import Account
from accounts.utils import save_new_account_to_db, update_account_in_db, delete_account_from_db
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
# Users and Accounts Routes
############################################

@app.get("/api/v1/accounts")
async def accounts(session: Session = Depends(get_session)):
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
    account = save_new_account_to_db(account_organisation, session)
    
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
    print(response)
    return {'response': 'success',
            'account_unique_id': response['account_unique_id']}


@app.get("/api/v1/accounts/{account_unique_id}")
async def account(account_unique_id: str, session: Session = Depends(get_session)):
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