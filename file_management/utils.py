import os
import boto3
from botocore.exceptions import ClientError
import logging
from sqlmodel import Session
from sqlmodel.sql.expression import select
from file_management.models import SourceFile, Folder
from secrets import token_hex
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup


# Initialize the S3 client
s3 = boto3.client('s3')

# The name of your S3 bucket
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
        
logger = logging.getLogger(__name__)

def save_file_to_db(filename: str, file_path: str, file_account: str, folder_id: int, session: Session):
    """
    Save Source File to DB
    """
    filename = filename.lower().replace(" ", "_")
    db_file = SourceFile(file_name=filename,
                         folder_id=folder_id,
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


async def prepare_for_s3_upload(extracted_text: str, file_name: str, account_unique_id: str, folder_id: int, session: Session):
    """
    Prepare File for S3 Upload
    """
    print("Preparing file for S3 upload...")
    # Step 5: Prepare the File for S3 Upload
    # Generate unique file name
    unique_file_name = f'{file_name}_{token_hex(8)}.pdf'.lower().replace(" ", "_")
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
        ContentType="application/pdf"
    )

    # Get the S3 file URL
    file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"

    # Save file information to the database (adjust this function to your schema)
    db_file = save_file_to_db(unique_file_name, file_url, file_account, folder_id, session)
            
    return {"message": "File successfully prepared for S3 upload", "file": unique_file_name}


async def delete_file_from_s3(account_unique_id: str, file, session: Session):
    """
    Delete file from S3 bucket account
    """
    file_path = file.file_path
    print( '**********File Object: ', file)
    if not file_path:
        raise HTTPException(status_code=404, detail={"error": "file_path not found in DB", "file_path": file_path})
    
    s3_object_key = f"{file.account_unique_id}/{file.file_name}"
    original_file_name_for_logging = file.file_name # For logging/response
    
    if not s3 or not BUCKET_NAME: # Basic check
        # Log this critical misconfiguration
        logger.error("S3 client or Bucket Name is not configured. Cannot delete from S3.")
        raise HTTPException(status_code=500, detail="S3 storage not configured for deletion.")

    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=s3_object_key)
        logger.info(f"Successfully deleted {s3_object_key} from bucket {BUCKET_NAME}")
        return True

    except ClientError as e:
        # If the error is NoSuchKey, it means the file wasn't there anyway,
        # which can be considered a "successful" deletion in some contexts.
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.warning(f"Object {s3_object_key} not found in bucket {BUCKET_NAME} during delete attempt. Assuming already deleted.")
            return True 
        logger.error(f"Failed to delete {s3_object_key} from S3 bucket {BUCKET_NAME}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while deleting {s3_object_key} from S3: {e}")
        return False


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


async def convert_file_to_pdf(original_file):
    """
    Convert permitted file types to pdf before saving
    """

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

    else:
        return pdf_content_bytes


def create_new_folder_in_db(account_unique_id: str, folder_name: str, session: Session):
    """
    Save New Folder to DB
    """

    folder = Folder(account_unique_id=account_unique_id,
                      folder_name=folder_name)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    
    return folder


def update_folder_in_db(folder_id: int, updated_folder: Folder, session: Session):
    """
    Update Folder in DB
    """
    folder = session.exec(select(Folder).where(Folder.id == folder_id)).first()
    
    if not folder:
        return {"error": "Folder not found"}
    
    updated_folder_dict = updated_folder.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in updated_folder_dict.items():
        setattr(folder, key, value)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    
    return folder


def delete_folder_from_db(folder_id: str, session: Session):
    """
    Delete Account from DB
    """
    statement = select(Folder).filter(Folder.id == folder_id)
    result = session.exec(statement)
    folder = result.first()
    
    if not folder:
        return {"error": "Folder not found",
                "folder_id": folder_id}
    
    session.delete(folder)
    session.commit()
    
    return {"response": "success",
            "folder_id": folder_id}
