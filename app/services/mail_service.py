import os
from email.message import EmailMessage
from app.utils.mail_templates import TESTING as testing_mail_template, TOKEN_NEARLY_EXHAUSTED
import httpx

EMAIL = os.getenv('SMTP_EMAIL')

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

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