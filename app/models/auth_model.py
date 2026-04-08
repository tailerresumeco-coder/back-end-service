from pydantic import BaseModel

class SignupModel(BaseModel):
    email: str
    password: str
    confirmPassword: str

class LoginModel(BaseModel):
    email: str
    password: str
    