import os
import jwt
from jwt.exceptions import InvalidTokenError
from typing import Annotated
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlmodel import select, Session
from datetime import datetime, timedelta, timezone
from accounts.models import User, WidgetAPIKey
from fastapi import Depends, HTTPException, status, Header, Request
from pydantic import BaseModel
from dependencies import get_session

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY')
ALGORITHM = os.environ.get('ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES'))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
api_key_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    account_unique_id: str
    account_organisation: str
    docs_count: int
    active_subscription: bool
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    

def verify_password(plain_password, hashed_password):
    """
    Verify Password
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    Get Password Hash
    """
    return pwd_context.hash(password)


def get_auth_user(user_email: str, session: Session = Depends(get_session)):
    """
    Get Auth User
    """
    statement = select(User).where(User.user_email == user_email)
    result = session.exec(statement)
    user = result.first()
    if user:
        user_dict = user.model_dump()
        return user_dict
    return None


def authenticate_user(user_email: str, password: str, session: Session = Depends(get_session)):
    """
    Authenticate User
    """
    user = get_auth_user(user_email, session=session)
    if not user:
        return False
    if not verify_password(password, user['user_password']):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Create Access Token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_api_key_hash(api_key: str):
    """
    Get API Key Hash
    """
    return api_key_context.hash(api_key)

def get_api_key(api_key_prefix: str, session: Session = Depends(get_session)):
    """
    Get API Key by Prefix
    """
    statement = select(WidgetAPIKey).where(WidgetAPIKey.display_prefix == api_key_prefix)
    result = session.exec(statement)
    widget_api_key = result.first()
    if widget_api_key:
        return widget_api_key
    return None


def validate_api_key_against_hash(api_key: str, api_key_hash: str):
    """
    Validate API Key against stored hash
    """
    return api_key_context.verify(api_key, api_key_hash)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: Session = Depends(get_session)):
    """
    Get Current User
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None:
            raise credentials_exception
        token_data = TokenData(username=user_email)
    except InvalidTokenError:
        raise credentials_exception
    user = get_auth_user(token_data.username, session=session)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get Current Active User
    """
    return current_user


async def get_widget_api_key_user(request: Request, x_api_key: str | None = Header(None, alias="X-API-Key"), session: Session = Depends(get_session)):
    """
    Get User from Widget API Key for CORS and API Key validation on widget queries.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header missing")
    
    api_key_prefix = x_api_key[:8]  # Example prefix, adjust as needed
    widget_api_key = get_api_key(api_key_prefix, session=session)
    if not widget_api_key:
        raise HTTPException(status_code=403, detail="Invalid or inactive API Key")
    
    # Verify the full API key against the stored hash
    api_key_validation_status = validate_api_key_against_hash(x_api_key, widget_api_key.api_key_hash)
    if not api_key_validation_status:
        # If the hash verification fails, raise an exception
        raise HTTPException(status_code=403, detail="Invalid or inactive API Key")

    if api_key_validation_status:
        validated_account_id = widget_api_key.account_unique_id
        key_allowed_origins = widget_api_key.allowed_origins

    # Validate allowed_origins
    if not key_allowed_origins:
        raise HTTPException(status_code=500, detail="No allowed_origins set for this API Key")
    
    if isinstance(key_allowed_origins, list) and not all(isinstance(origin, str) for origin in key_allowed_origins):
        raise HTTPException(status_code=500, detail="Invalid allowed_origins format in API Key record")
    
    elif isinstance(key_allowed_origins, str):
        key_allowed_origins = [key_allowed_origins]
    
    elif not isinstance(key_allowed_origins, list):
        raise HTTPException(status_code=500, detail="Invalid allowed_origins format in API Key record")

    if not validated_account_id:
        raise HTTPException(status_code=403, detail="Invalid or inactive API Key")

    # CORS Check
    origin = request.headers.get("origin")
    if origin: # Browser requests will have an Origin header
        if "*" not in key_allowed_origins and origin not in key_allowed_origins:
            raise HTTPException(status_code=403, detail=f"Origin {origin} not allowed for this API key")
        
    elif key_allowed_origins and "*" not in key_allowed_origins: # Non-browser request, but key has origin restrictions
        raise HTTPException(status_code=403, detail="This API key is restricted by origin and request has no origin.")
    # If all checks pass, return the validated account ID and API key
    return {"account_unique_id": validated_account_id, "api_key": x_api_key}