"""Security utilities for authentication and encryption"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import hashlib
import copy
from app.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


# Token encryption for GitLab/GitHub PATs
def get_cipher():
    """Get Fernet cipher from master key"""
    # Derive a valid Fernet key from the master key
    key = hashlib.sha256(settings.APP_MASTER_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_token(token: str) -> str:
    """Encrypt a token (PAT)"""
    cipher = get_cipher()
    encrypted = cipher.encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token (PAT)"""
    cipher = get_cipher()
    decrypted = cipher.decrypt(encrypted_token.encode())
    return decrypted.decode()


def get_token_last4(token: str) -> str:
    """Get last 4 characters of token for display"""
    return token[-4:] if len(token) >= 4 else "***"


def mask_sensitive_data(text: str) -> str:
    """Mask sensitive data in logs"""
    # Mask common token patterns
    import re
    
    # GitLab PAT pattern: glpat-xxxxx
    text = re.sub(r'glpat-[A-Za-z0-9_-]+', 'glpat-****', text)
    
    # GitHub PAT patterns
    text = re.sub(r'ghp_[A-Za-z0-9]{36}', 'ghp_****', text)
    text = re.sub(r'github_pat_[A-Za-z0-9_]{82}', 'github_pat_****', text)
    
    # Generic Bearer tokens
    text = re.sub(r'Bearer [A-Za-z0-9._-]+', 'Bearer ****', text)
    
    return text


def sanitize_project_settings(settings: dict) -> dict:
    """
    Sanitize project settings by masking sensitive tokens.
    
    Args:
        settings: Raw project settings dictionary containing gitlab/github configs
        
    Returns:
        Sanitized settings with tokens masked showing only last 4 characters
    """
    # Use deep copy to ensure complete isolation from original settings
    sanitized = copy.deepcopy(settings)
    
    # Sanitize GitLab settings
    if "gitlab" in sanitized and isinstance(sanitized["gitlab"], dict):
        if "token" in sanitized["gitlab"]:
            token = sanitized["gitlab"]["token"]
            # Replace full token with token_last4
            del sanitized["gitlab"]["token"]
            sanitized["gitlab"]["token_last4"] = get_token_last4(token)
    
    # Sanitize GitHub settings
    if "github" in sanitized and isinstance(sanitized["github"], dict):
        if "token" in sanitized["github"]:
            token = sanitized["github"]["token"]
            # Replace full token with token_last4
            del sanitized["github"]["token"]
            sanitized["github"]["token_last4"] = get_token_last4(token)
    
    return sanitized
