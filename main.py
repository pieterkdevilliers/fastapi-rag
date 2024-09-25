import os
import shutil
from typing import Any
from secrets import token_hex
from fastapi import FastAPI, UploadFile, Depends, File
from sqlmodel import select, Session
from file_management.models import engine, SourceFileModel
from file_management.utils import save_file_to_db
import query_data.query_source_data as query_source_data


# source_models.Base.metadata.create_all(bind=source_db.engine)

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
    statement = select(SourceFileModel).filter()
    result = session.exec(statement)
    files = result.all()
    for file in files:
        returned_files.append(file)
    print(type(returned_files))

    if not returned_files:
        return {"error": "No files found"}
    
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

