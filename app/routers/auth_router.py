from fastapi import APIRouter, HTTPException
from app.models.auth_model import SignupModel, LoginModel, GoogleSignupModel
from app.services.auth_service import signup as signup_service, login as login_service, google_signup as google_signup_service

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

@router.post("/sign-up")
async def signup(payload: SignupModel):
    result = await signup_service(
        payload.email,
        payload.password,
        payload.confirmPassword
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post('/login')
async def login(payload: LoginModel):
    result = await login_service(payload.email, payload.password)

    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])

    return result

@router.post('/oauth/google-signup')
async def google_signup(token: GoogleSignupModel):
    print('Begin auth_router.py -> google_signup()')
    result = await google_signup_service(
        token.credential
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
