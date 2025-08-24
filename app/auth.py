from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGO = "HS256"

def hash_password(p: str) -> str:
    return pwd_context.hash(p)

def verify_password(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)

def create_access_token(sub: str, expires_minutes: int = 60*24) -> str:
    payload = {"sub": sub, "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
