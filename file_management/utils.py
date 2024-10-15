import os
import boto3
from sqlmodel import Session
from sqlmodel.sql.expression import select
from file_management.models import SourceFile
from secrets import token_hex
from fastapi import HTTPException, Request
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup


# Initialize the S3 client
s3 = boto3.client('s3')

# The name of your S3 bucket
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
        

def save_file_to_db(filename: str, file_path: str, file_account: str, session: Session):
    """
    Save Source File to DB
    """
    db_file = SourceFile(file_name=filename,
                         file_path=file_path,
                         account_unique_id=file_account,
                         included_in_source_data=True)
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    
    return db_file

def update_file_in_db(file_id: int, updated_file: SourceFile, session: Session):
    """
    Update Source File in DB
    """
    file = session.get(SourceFile, file_id)
    
    if not file:
        return {"error": "File not found"}
    
    updated_file_dict = updated_file.model_dump(exclude_unset=True)
    print('updated_file_dict:', updated_file_dict)
    for key, value in updated_file_dict.items():
        setattr(file, key, value)
    session.add(file)
    session.commit()
    session.refresh(file)
    
    return file


def delete_file_from_db(account_unique_id: str, file_id: int, session: Session):
    """
    Delete Source File from DB
    """
    statement = select(SourceFile).filter(SourceFile.account_unique_id == account_unique_id, SourceFile.id == file_id)
    result = session.exec(statement)
    file = result.first()
    
    if not file:
        return {"error": "File not found",
                "file_id": file_id}
    
    session.delete(file)
    session.commit()
    
    return {"response": "success",
            "file_id": file_id}


async def fetch_html_content(url: str):
    """
    Get Text from URL
    """
    print(f"Fetching HTML content from URL: {url}")
    try:
        # Step 2: Fetch the HTML content
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # Raise an error for bad responses
        
        return response.text
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Failed to fetch the URL")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    

async def extract_text_from_html(html_content):
    """
    Extract Text from HTML
    """
    print("Extracting text from HTML content...")
    # Step 3: Parse the Text from the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    # Extract the page title
    title = soup.title.string if soup.title else "No Title Found"
    text = soup.get_text(separator="\n", strip=True)
    content = {"title": title, "text": text}
    return content


async def prepare_for_s3_upload(extracted_text: str, file_name: str, account_unique_id: str, session: Session):
    """
    Prepare File for S3 Upload
    """
    print("Preparing file for S3 upload...")
    # Step 5: Prepare the File for S3 Upload
    # Generate unique file name
    unique_file_name = f'{file_name}_{token_hex(8)}.txt'
    file_account = account_unique_id
    
    # Simulate the subfolder by including account_unique_id in the S3 key
    s3_key = f"{account_unique_id}/{unique_file_name}"

    # Read the file content
    # content = await file.read()

    # Upload file to S3, saving it under the account_unique_id "folder"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,  # Upload to account subfolder
        Body=extracted_text,
        ContentType="text/plain"
    )

    # Get the S3 file URL
    file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"

    # Save file information to the database (adjust this function to your schema)
    db_file = save_file_to_db(unique_file_name, file_url, file_account, session)
            
    return {"message": "File successfully prepared for S3 upload", "file": unique_file_name}


async def save_text_to_file(text, title, account_unique_id: str, url: str, session: Session):
    """
    Save Text to File
    """
    print("Saving extracted text to file...")
    # Step 4: Save the Text as a .txt file
    filename = f"{title}.txt"
    file_account = account_unique_id
    file_path = f"./extracted_text_{os.path.basename(url)}.txt"
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(text)
    # save_file_to_db(filename, file_path, file_account, session)

    return {"message": "Text successfully extracted and saved", "file_path": file_path}


    
