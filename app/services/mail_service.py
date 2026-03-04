import os
from typing import List
from app.utils.mail_templates import TESTING as testing_mail_template, TOKEN_NEARLY_EXHAUSTED
import httpx
from app.utils.query_manager import getAllUsers
import smtplib
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL = os.getenv('SMTP_EMAIL')

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")


def replace_template_placeholders(template: str, recipient: dict) -> str:
    """
    Replace placeholders in email template with recipient-specific values.
    
    Supported placeholders:
    - [First Name] - Replaced with the recipient's first name (extracted from full name)
    
    Args:
        template: The email template string with placeholders
        recipient: Dictionary containing recipient info (name, email)
    
    Returns:
        The template with all placeholders replaced
    """
    if not template:
        return template
    
    result = template
    
    # Extract first name from full name
    full_name = recipient.get("name", "")
    if full_name:
        # Get first name - handle names with multiple parts
        name_parts = full_name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        
        # Replace [First Name] placeholder
        result = result.replace("[First Name]", first_name)
    
    return result

async def send_email(to: str, subject: str, body: str):
    print('Start send mail')
    url = "https://api.sendgrid.com/v3/mail/send"

    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "personalizations": [{
            "to": [{"email": to}]
        }],
        "from": {"email": EMAIL},
        "subject": subject,
        "content": [{
            "type": "text/html",
            "value": body
        }]
    }
    
    
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, headers=headers, json=payload)

    print('response', response)
    return response.status_code


async def send_email_test():
    print('Start send mail test')
    await send_email('ranaabashetty@gmail.com', 'Testing', testing_mail_template)
    print('End send mail test')
    
async def send_token_nearly_exhausted_email():
    print('Start send token nearly exhausted email')
    await send_email('tailer.resume.co@gmail.com', 'Warning: Your Groq API token is near to exhaust', TOKEN_NEARLY_EXHAUSTED)
    
async def tailored_notify_email(name: str, email: str):
    subject = "Your Tailored Resume is Ready!"
    body = f"""
    <html>
      <body>
        <p>Hey Admin</p>
        <p>{name} ({email}) has tailored their resume with {email}.</p>
        <p>Best regards,<br/>Tailer Resume Team</p>
      </body>
    </html>
    """
    await send_email('ranaabashetty@gmail.com', subject, body)

async def get_user_details(page: int, size: int, search: str):
    print('Begin mail_router.py -> get_user_details()')
    return await getAllUsers(page, size, search)


SMTP_SERVER = "smtp.hostinger.com"
SMTP_PORT = 465
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


def send_bulk_emails_task(email_list: List[dict], subject: str, body: str, attachment_content: bytes = None, attachment_filename: str = None):
    """
    Background task to send bulk emails.
    This runs in the background to not block the main thread.
    Accepts email_list as [{name, email}, ...] directly.
    """
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)

            for recipient in email_list:
                email = recipient.get("email")
                if not email:
                    print(f"Skipping - no email address")
                    continue
                    
                message = MIMEMultipart()
                message["From"] = SMTP_EMAIL
                message["To"] = email
                message["Subject"] = subject
                
                # Replace placeholders in email body with recipient-specific values
                personalized_body = replace_template_placeholders(body, recipient)
                message.attach(MIMEText(personalized_body, "html"))

                # Add attachment if provided
                if attachment_content and attachment_filename:
                    from email.encoders import encode_base64
                    from email.mime.base import MIMEBase
                    
                    attachment_part = MIMEBase("application", "octet-stream")
                    attachment_part.set_payload(attachment_content)
                    encode_base64(attachment_part)
                    attachment_part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {attachment_filename}"
                    )
                    message.attach(attachment_part)

                server.sendmail(SMTP_EMAIL, email, message.as_string())
                print(f"Sent to {email}")

                time.sleep(1.5)  # 🔥 avoid rate limit

        print(f"Successfully sent to {len(email_list)} recipients")
    except Exception as e:
        print("Bulk sending failed:", str(e))
