import hashlib,secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException,Request
from paperfeed.db import transaction
from paperfeed.config import settings

hasher=PasswordHasher()
def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def verify(password,encoded):
    try: return hasher.verify(encoded,password)
    except VerificationError: return False

def current_user(request: Request):
    token=request.cookies.get('session')
    if not token: raise HTTPException(401,'Authentication required')
    with transaction() as conn:
        user=conn.execute('SELECT u.id,u.username,u.display_name,u.interests,u.feed_version FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=%s AND expires_at>now()', (digest(token),)).fetchone()
    if not user: raise HTTPException(401,'Session expired')
    return user

def check_origin(request):
    if request.method in {'POST','PUT','PATCH','DELETE'} and request.headers.get('origin') != settings.origin:
        raise HTTPException(403,'Invalid origin')
