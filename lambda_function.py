# lambda_function.py
import boto3
import json

# Initialize the S3 client. This happens once when the Lambda container starts.
s3_client = boto3.client('s3')

def handler(event, context):
    """
    A simple Lambda to verify it can be triggered and can "see" a file in S3.
    """
    print(f"Lambda triggered. Received event: {json.dumps(event)}")

    # 1. Safely get the file details from the event payload
    s3_bucket = event.get('s3_bucket')
    s3_key = event.get('s3_key')

    if not s3_bucket or not s3_key:
        print("ERROR: Missing 's3_bucket' or 's3_key' in the event payload.")
        # We don't raise an error here, just log it for this simple test
        return {"statusCode": 400, "body": "Invalid payload."}

    print(f"Tasked to check for file: s3://{s3_bucket}/{s3_key}")

    # 2. Check if the file exists in S3 using head_object
    # head_object is a lightweight way to get metadata without downloading the file.
    try:
        s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
        print(f"SUCCESS: File found at s3://{s3_bucket}/{s3_key}")

    except s3_client.exceptions.ClientError as e:
        # If a '404' error is caught, the file was not found
        if e.response['Error']['Code'] == '404':
            print(f"FAILURE: File not found at s3://{s3_bucket}/{s3_key}")
        else:
            # Handle other possible errors like '403 Forbidden' (permission issue)
            print(f"ERROR: A client error occurred: {e.response['Error']['Message']}")
        return {"statusCode": 500, "body": "Failed to access S3 object."}

    # 3. Final completion message
    print("Process completed.")

    return {
        'statusCode': 200,
        'body': json.dumps('Verification successful!')
    }