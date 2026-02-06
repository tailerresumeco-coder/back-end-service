from pydantic import BaseModel

class FeedbackModel(BaseModel):
    liked: bool
    unLiked: bool
    message: str