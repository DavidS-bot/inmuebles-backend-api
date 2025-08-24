# app/routers/auth.py
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
from ..config import settings
from ..db import get_session
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def make_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.jwt_expires_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp},
                      settings.jwt_secret, algorithm=settings.jwt_algorithm)

class RegisterIn(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register(data: RegisterIn, session: Session = Depends(get_session)):
    exists = session.exec(select(User).where(User.email == data.email)).first()
    if exists:
        raise HTTPException(400, "Email ya registrado")

    user = User(email=data.email, hashed_password=pwd.hash(data.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"id": user.id, "email": user.email}

@router.post("/login")
def login(session: Session = Depends(get_session),
          form: OAuth2PasswordRequestForm = Depends()):
    # OAuth2 usa "username" → lo usamos como email
    user = session.exec(select(User).where(User.email == form.username)).first()
    if not user or not pwd.verify(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Credenciales inválidas")
    return {"access_token": make_token(user.id), "token_type": "bearer"}
