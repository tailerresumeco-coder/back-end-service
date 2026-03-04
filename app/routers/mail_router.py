import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from app.utils.query_manager import getAllUsers
from app.services.mail_service import send_bulk_emails_task


router = APIRouter(
    prefix="/mails",
    tags=["Users"],
)


@router.get("/get-user-details")
async def getAllUserDetails(page: int, size: int, search: str):
    """
    Get user details for displaying in user management table.
    This is needed to list users but emails are sent directly from frontend.
    """
    print('Begin mail_router.py -> getUserDetails()')
    return await getAllUsers(page, size, search)


class RecipientInfo(BaseModel):
    name: str
    email: str


@router.post("/send")
async def send_mail(
    background_tasks: BackgroundTasks,
    recipients: str = Form(...),  # JSON string of [{name, email}, ...]
    subject: str = Form(...),
    body: str = Form(...),
    attachment: Optional[UploadFile] = File(None)
):
    """
    Send mail to selected users using background tasks.
    Recipients are sent directly from frontend to reduce backend load.
    """
    print('Begin mail_router.py -> send_mail()')
    try:
        # Parse recipients from JSON string
        recipients_list = json.loads(recipients)
        
        if not recipients_list:
            return {"success": False, "message": "No recipients provided"}
        
        # Read attachment content if present
        attachment_content = None
        attachment_filename = None
        if attachment:
            attachment_content = await attachment.read()
            attachment_filename = attachment.filename
        
        # Add email sending to background tasks
        background_tasks.add_task(
            send_bulk_emails_task,
            email_list=recipients_list,
            subject=subject,
            body=body,
            attachment_content=attachment_content,
            attachment_filename=attachment_filename
        )
        
        return {"success": True, "message": f"Emails queued for {len(recipients_list)} recipient(s)"}
    except Exception as e:
        print(f"Error sending mail: {e}")
        raise HTTPException(status_code=500, detail=str(e))
