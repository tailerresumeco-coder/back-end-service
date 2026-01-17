import os
from email.message import EmailMessage
import aiosmtplib
from app.utils.mail_templates import TESTING

EMAIL = os.getenv('SMTP_EMAIL')
PASSWORD = os.getenv('SMPT_PASSWORD')
PORT = os.getenv('SMTP_PORT')
SERVER = os.getenv('SMTP_SERVER')


async def send_email_test(to: str = 'ranaabashetty@gmail.com', subject: str = 'Testing'):
    body = TESTING
    print('Begin send_email()', EMAIL, to, subject, body, PASSWORD)
    message = EmailMessage()
    message["From"] = EMAIL
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    print(await aiosmtplib.send(
        message,
        hostname=SERVER,
        port=PORT,
        start_tls=True,
        username=EMAIL,
        password=PASSWORD,
    ))
    print('End send mail', message)
    