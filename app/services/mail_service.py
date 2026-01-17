import os
from email.message import EmailMessage
import aiosmtplib
from app.utils.mail_templates import TESTING as testing_mail_template
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
            "type": "text/plain",
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
    