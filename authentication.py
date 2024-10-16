import os
import jwt
from jwt.exceptions import InvalidTokenError
from typing import Annotated
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlmodel import select, Session
from datetime import datetime, timedelta, timezone
from accounts.models import User
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from dependencies import get_session

load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY')
ALGORITHM = os.environ.get('ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES'))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
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