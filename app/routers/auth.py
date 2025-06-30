from fastapi import APIRouter, HTTPException, Depends, Form, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models import TokenResponse
from typing import Dict

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Use correct token URL for Swagger authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Simulated user database
fake_users_db: Dict[str, str] = {"bharath": "secret"}
refresh_tokens_db = {}

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username
    password = form_data.password
    if fake_users_db.get(username) != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload = {"sub": username}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)
    refresh_tokens_db[username] = refresh_token

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_token: str = Form(...)):
    try:
        payload = decode_token(refresh_token)
        username = payload["sub"]
        if refresh_tokens_db.get(username) != refresh_token:
            raise HTTPException(status_code=403, detail="Invalid refresh token")

        new_access = create_access_token({"sub": username})
        new_refresh = create_refresh_token({"sub": username})
        refresh_tokens_db[username] = new_refresh

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer"
        }
    except:
        raise HTTPException(status_code=403, detail="Invalid or expired token")

@router.post("/logout")
def logout(username: str = Form(...)):
    refresh_tokens_db.pop(username, None)
    return {"message": "Logged out"}

# ✅ Secure user info route using Security()


@router.get("/me", tags=["auth"])
def get_me(token: str = Security(oauth2_scheme)):
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Username not found in token")
        return {"username": username}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


