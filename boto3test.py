import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

s3 = boto3.client('s3')
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')

if not BUCKET_NAME:
    print("Error: AWS_STORAGE_BUCKET_NAME is not set.")
else:
    print(f"Using bucket: {BUCKET_NAME}")

def fetch_file_from_s3(bucket_name, s3_key):
    try:
        s3_object = s3.get_object(Bucket=bucket_name, Key=s3_key)
        file_content = s3_object['Body'].read()
        print(f"File content length: {len(file_content)}")
    except ClientError as e:
        print(f"Error fetching file: {e}")


fetch_file_from_s3(BUCKET_NAME, 'c67fd80456ca4ff1/CLIENT REVIEW_ SSC - Blog - Shutters For Sash Windows_ 3 Essential Considerations For The Perfect Fit_c0419518a7a1de66.docx')

