from typing import Any
from fastapi import FastAPI, File, UploadFile, Depends
import query_data.query_source_data as query_source_data
import file_management.source_db as source_db
import file_management.source_models as source_models
from secrets import token_hex

source_models.Base.metadata.create_all(bind=source_db.engine)

app = FastAPI()

# Dependency
def get_db():
    db = source_db.SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

@app.post("/api/v1/upload-file")
async def upload_file(file: UploadFile):
    """
    Upload File
    """
    if not file:
        return {"error": "No file provided"}
    
    file_ext = file.filename.split('.')[-1]
    if file_ext != 'md':
        return {"error": "File must be a markdown file"}
    
    file_name = f'{file.filename}_{token_hex(8)}.{file_ext}'
    file_path = f'./files/{file_name}'

    with open(file_path, 'wb') as f:
        f.write(file.file.read())
    
    return {"response": "success",
            "file_name": file_name,
            "file_path": file_path}