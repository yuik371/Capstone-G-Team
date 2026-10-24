"""회원가입, 로그인, JWT access token 발급 라우터."""

import os
from datetime import datetime, timedelta, timezone

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt
from fastapi import APIRouter, HTTPException, status, Depends
from pwdlib import PasswordHash
from bson import ObjectId

from db.mongo import users_collection
from models.user import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter()
password_hash = PasswordHash.recommended()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120


#JWT 생성
def create_access_token(user_id: str):
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="환경 변수 없음")

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)



bearer_scheme = HTTPBearer()
#JWT 사용
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="user_id 없음")
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=401, detail="user 없음")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="토큰 오류")



#회원가입
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: RegisterRequest):

    userid = user.userid.strip().lower()

    if await users_collection.find_one({"userid": userid}):
        raise HTTPException(
            status_code=409, detail="이미 가입된 계정입니다.")

#사용자 정보
    document = {
        "userid": user.userid.strip(),
        "hospitalid": None,
        "password_hash": password_hash.hash(user.password),
        "role": "user",
        "hospitalid": None,
        "created_at": datetime.now(timezone(timedelta(hours=9))),
    }
    
    try:
        result = await users_collection.insert_one(document)
    except Exception as exc:
        # email unique index가 이미 있다면 동시 가입 중복도 안전하게 처리한다.
        if getattr(exc, "code", None) == 11000:
            raise HTTPException(
                status_code=409, detail="이미 가입된 계정입니다.") from exc
        raise

    return {"message": "회원가입이 완료되었습니다.", "user_id": str(result.inserted_id)}


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    userid = credentials.userid.strip().lower()
    user = await users_collection.find_one({"userid": userid})

    if not user or not password_hash.verify(
        credentials.password, user.get("password_hash", "")
    ):
        raise HTTPException(
            status_code=401,detail="계정 또는 비밀번호가 올바르지 않습니다.",headers={"WWW-Authenticate": "Bearer"})

    return {
        "access_token": create_access_token(str(user["_id"])),
        "message": f"로그인 완료 {userid}님"
    }

@router.post("/userslist")
async def userlist():
    users_list = users_collection.find({})
    users = await users_list.to_list(length=None)
    for u in users:
        u["_id"] = str(u["_id"])

    userid = [u.get("userid") for u in users]
    return {"messages": userid} 
