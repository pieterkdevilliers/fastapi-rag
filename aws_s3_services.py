import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
load_dotenv()

s3 = boto3.client('s3')
BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')

def s3_object_exists(key: str) -> bool:
    """Check if object exists without downloading it"""
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise  # other errors → let them bubble up

def upload_bytes_to_s3(data: bytes, key: str, content_type: str = "image/png") -> str:
    """Upload bytes and return public/presigned URL"""
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl="max-age=3600",
    )

    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=86400  # 24 hours
    )
    return presigned_url