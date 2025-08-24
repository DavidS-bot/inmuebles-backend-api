# app/deps.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from sqlmodel import Session, select

from .config import settings
from .db import get_session
from .models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2),
    session: Session = Depends(get_session),
) -> User:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(data.get("sub"))
    except Exception:
        raise HTTPException(401, "Token inválido")
    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Usuario inactivo o no existe")
    return user
