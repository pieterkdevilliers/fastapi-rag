import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

# A dependency provider function
_email_service_singleton = None

def get_email_service():
    global _email_service_singleton
    if _email_service_singleton is None:
        _email_service_singleton = EmailService()
    return _email_service_singleton

class EmailService:
    def __init__(self):
        self.ses = boto3.client(
            "ses",
            region_name=os.environ.get("AWS_SES_REGION"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_KEY"),
        )
        self.sender_email = os.environ.get("AWS_SES_VERIFIED_MAIL")

    def send_email(self, to_email: str, subject: str, message: str, chat_messages: list = None):
        try:
            response = self.ses.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": message}},
                }
                if chat_messages is None else {
                    "Subject": {"Data": subject},
                    "Body": {
                        "Text": {"Data": message},
                        "Html": {"Data": "<br>".join(chat_messages)},
                    },
                }
            )
            print(response["MessageId"])
            return response["MessageId"]
        except ClientError as e:
            raise Exception(f"Email sending failed: {str(e)}")

