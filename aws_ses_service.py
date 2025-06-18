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

    def send_email(self, to_email: str, subject: str, text_body: str, html_body: str):
        """
        Sends an email with both HTML and plain text content.
        """
        try:
            response = self.ses.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {
                        "Text": {"Data": text_body},
                        "Html": {"Data": html_body},
                    },
                },
            )
            print(f"Email sent successfully. MessageId: {response['MessageId']}")
            return response["MessageId"]
        except ClientError as e:
            print(f"Email sending failed: {e.response['Error']['Message']}")
            raise Exception(f"Email sending failed: {e.response['Error']['Message']}")

    def send_password_reset_email(self, to_email: str, reset_link: str):
            """
            Constructs and sends a password reset email.
            """
            subject = "Your Password Reset Link"
            
            html_body = f"""
            <html>
            <body>
            <h1>Password Reset Request</h1>
            <p>We received a request to reset your password. Click the link below to proceed.</p>
            <a href="{reset_link}">Reset Your Password</a>
            <p>This link will expire in 1 hour.</p>
            </body>
            </html>
            """
            
            text_body = f"""
            Password Reset Request
            
            Please use the following link to reset your password: {reset_link}
            
            This link will expire in 1 hour.
            """
            
            # Call the generic sender method
            return self.send_email(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )
