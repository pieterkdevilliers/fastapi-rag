# lambda_function.py

import boto3
import os
import tempfile
import shutil  # Import shutil for robust directory cleanup
from secrets import token_hex
import requests
import json
import convert_to_pdf # Your conversion logic module

s3_client = boto3.client('s3')

# Environment Variables for Lambda:
FINAL_BUCKET = os.environ['FINAL_BUCKET_NAME']
FASTAPI_CALLBACK_URL = os.environ['FASTAPI_CALLBACK_URL']
INTERNAL_API_KEY = os.environ['INTERNAL_API_KEY'] # Match the variable name from your last snippet

def lambda_handler(event, context):
    # 1. Parse the event from the FastAPI invocation
    db_file_id = event['db_file_id']
    staging_bucket = event['staging_bucket']
    staging_s3_key = event['staging_s3_key']
    original_filename = event['original_filename']
    account_unique_id = event['account_unique_id']
    
    callback_payload = {"db_file_id": db_file_id}
    
    # Lambda's ephemeral storage is at /tmp
    download_path = f'/tmp/{original_filename}'
    temp_output_dir = None # To hold the temp directory path for cleanup

    try:
        # 2. Download the original file from the staging bucket to /tmp
        s3_client.download_file(staging_bucket, staging_s3_key, download_path)

        # 3. --- Start of ACTUAL Conversion Logic ---
        original_file_ext = original_filename.split('.')[-1].lower()
        pdf_content_bytes = None

        # Read the downloaded file content into memory
        with open(download_path, 'rb') as f:
            original_content = f.read()

        if original_file_ext == 'pdf':
            # If the file is already a PDF, just use its content directly
            pdf_content_bytes = original_content
        
        else:
            # For non-PDFs, we need a temporary directory for conversion artifacts
            temp_output_dir = tempfile.mkdtemp(dir="/tmp")

            if original_file_ext in ['doc', 'docx']:
                # 1. Convert DOCX/DOC to HTML using Pandoc
                temp_html_file_path = convert_to_pdf.convert_to_html_pandoc(
                    input_path=download_path, # Use the downloaded file path directly
                    output_dir=temp_output_dir,
                    input_format=original_file_ext
                )
                
                # 2. Convert the intermediate HTML to PDF using WeasyPrint
                final_temp_pdf_path = os.path.join(temp_output_dir, "final_converted_document.pdf")
                convert_to_pdf.convert_html_to_pdf_weasyprint(
                    html_input=temp_html_file_path,
                    output_pdf_path=final_temp_pdf_path,
                    is_file_path=True
                )
                
                with open(final_temp_pdf_path, 'rb') as f_pdf:
                    pdf_content_bytes = f_pdf.read()

            elif original_file_ext == 'txt':
                # Decode the text content and convert to PDF
                decoded_content = original_content.decode('utf-8', errors='replace')
                pdf_content_bytes = convert_to_pdf.convert_text_to_pdf(decoded_content)

            elif original_file_ext == 'md':
                # Convert Markdown to PDF
                converted_pdf_path = os.path.join(temp_output_dir, "converted.pdf")
                decoded_content = original_content.decode('utf-8', errors='replace')
                convert_to_pdf.convert_markdown_to_pdf(decoded_content, converted_pdf_path)
                with open(converted_pdf_path, 'rb') as f_pdf:
                    pdf_content_bytes = f_pdf.read()
            
            else:
                # If the format is not supported, raise an error to trigger the FAILED callback
                raise ValueError(f"File type '.{original_file_ext}' is not supported for PDF conversion.")

        # --- End of Conversion Logic ---

        if not pdf_content_bytes:
             raise ValueError("Conversion process resulted in empty PDF content.")
             
        # 4. Upload the converted PDF to the final bucket
        file_base_name = original_filename.rsplit('.', 1)[0]
        unique_pdf_filename = f'{file_base_name}_{token_hex(8)}.pdf'.lower().replace(" ", "_")
        final_s3_key = f"{account_unique_id}/{unique_pdf_filename}"
        
        s3_client.put_object(
            Bucket=FINAL_BUCKET,
            Key=final_s3_key,
            Body=pdf_content_bytes,
            ContentType='application/pdf'
        )
        file_url = f"https://{FINAL_BUCKET}.s3.amazonaws.com/{final_s3_key}"

        # 5. Prepare the SUCCESS payload for the callback
        callback_payload['status'] = 'COMPLETED'
        callback_payload['final_file_url'] = file_url
        callback_payload['final_unique_filename'] = unique_pdf_filename

    except Exception as e:
        # If anything goes wrong during download or conversion, prepare the FAILED payload
        print(f"Error processing file for db_file_id {db_file_id}: {str(e)}")
        callback_payload['status'] = 'FAILED'
        callback_payload['error_message'] = str(e)[:1024] # Truncate error for DB

    finally:
        # 6. ALWAYS send the callback to the FastAPI app
        print(f"Sending callback for db_file_id {db_file_id} with status: {callback_payload.get('status')}")
        headers = {
            "Content-Type": "application/json",
            "X-Internal-API-Key": INTERNAL_API_KEY
        }
        try:
            response = requests.post(
                FASTAPI_CALLBACK_URL, 
                data=json.dumps(callback_payload), 
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            print("Callback successful.")
        except requests.exceptions.RequestException as e:
            print(f"FATAL: Could not send callback to FastAPI: {e}")
            raise e # Re-raise to mark Lambda invocation as failed for potential retries

        # 7. Clean up all local temporary files and directories from /tmp
        if os.path.exists(download_path):
            os.remove(download_path)
        if temp_output_dir and os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir) # Safely remove the temp directory and all its contents
        
        # 8. Clean up the original file from the staging S3 bucket
        try:
            s3_client.delete_object(Bucket=staging_bucket, Key=staging_s3_key)
        except Exception as e:
            # Log this error but don't fail the lambda, as the core job is done
            print(f"Warning: Could not delete {staging_s3_key} from staging bucket: {e}")
            
    return callback_payload # The return value is for Lambda's own logs