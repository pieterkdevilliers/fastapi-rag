import os
import shutil
from typing import Any
from fastapi import FastAPI, UploadFile, Depends, File
from sqlalchemy.orm import Session
from file_management.source_db import engine
import query_data.query_source_data as query_source_data
from file_management.source_db import SourceFileModel
from secrets import token_hex


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

# @app.post("/api/v1/upload-file")
# async def upload_file(file: UploadFile):
#     """
#     Upload File
#     """
#     if not file:
#         return {"error": "No file provided"}
    
#     file_ext = file.filename.split('.')[-1]
#     if file_ext != 'md':
#         return {"error": "File must be a markdown file"}
    
#     file_name = f'{file.filename}_{token_hex(8)}.{file_ext}'
#     file_path = f'./files/{file_name}'

#     with open(file_path, 'wb') as f:
#         f.write(file.file.read())
    
#     return {"response": "success",
#             "file_name": file_name,
#             "file_path": file_path}


@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    # Save the uploaded file to the server
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Save file metadata in the database
    source_file = SourceFileModel(
        file_name=file.filename,
        file_path=file_location
    )
    session.add(source_file)
    session.commit()
    session.refresh(source_file)

    return {"file_id": source_file.id, "file_name": source_file.file_name}
