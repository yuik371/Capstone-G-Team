import os
import re
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import traceback

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pwdlib import PasswordHash
from bson import ObjectId

from db.mongo import users_collection, account_request_collection
from models.user import LoginRequest, RegisterRequest, TokenResponse, HospitalLinkRequestCreate, AccountRequestCreate


router = APIRouter()
password_hash = PasswordHash.recommended()

ER_API_KEY = os.getenv("ER_API_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120


#JWT 생성
def create_access_token(user_id: str):
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="환경 변수 없음")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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

#병원 이름 == hpid 반환
@router.get("/link/hospitals" , summary="병원 hpid 반환")
async def link_hospitals(name: str = Query(min_length=2,max_length=100), current_user=Depends(get_current_user)):
    url = ("https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire")
    try:
        
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url,
                                        params={
                                            "serviceKey": ER_API_KEY,
                                            "pageNo": 1,
                                            "numOfRows": 1000
                                        })

            response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"공공데이터 API 호출 실패: {type(exc).__name__}: {exc!r}")
        raise HTTPException(status_code=502, detail="공공데이터 API 연결 실패") from exc

    except httpx.RequestError as exc:
        print("공공데이터 연결 오류:", repr(exc))
        raise HTTPException(status_code=502, detail="병원 조회 실패") from exc



    def normalize(value: str):
        return re.sub(r"\s+","",value).casefold()

    search_name = normalize(name)
    exact_matches = []
    similar_matches = []
    root = ET.fromstring(response.text)

    for item in root.iter("item"):
        hospital_name = item.findtext("dutyName")
        hpid = item.findtext("hpid")

        if not hospital_name or not hpid:
            continue

        normalized_hospital_name = normalize(hospital_name)
        hospital = {
            "name": hospital_name,
            "hpid": hpid,
            "address": item.findtext("dutyAddr"),
        }

        if normalized_hospital_name == search_name:
            exact_matches.append(hospital)
        elif search_name in normalized_hospital_name:
            similar_matches.append(hospital)

    print("검색병원명:", name)
    return {
        "exact_matches": exact_matches,
        "similar_matches": similar_matches[:10],
    }




#역할 추출
@router.get("/me", summary="역할 및 아이디 반환")
async def me(user=Depends(get_current_user)):
    return {"role": user.get("role"),
            "userid": user.get("userid")
            }

#회원가입
@router.post("/register", status_code=status.HTTP_201_CREATED, summary="회원가입")
async def register(user: RegisterRequest):

    userid = user.userid.strip().lower()

    if await users_collection.find_one({"userid": userid}):
        raise HTTPException(
            status_code=409, detail="이미 가입된 계정입니다.")

#사용자 정보
    document = {
        "userid": user.userid.strip(),
        "hospitalid": None,
        "ambid": None,
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


@router.post("/login", response_model=TokenResponse, summary="로그인")
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


#병원 계정 발급 요청
@router.post("/link/requests",  status_code=status.HTTP_201_CREATED, summary="계정 발급 요청")
async def create_account_request(request: AccountRequestCreate, current_user=Depends(get_current_user)):
    userid = str(current_user["_id"])

    existing = await account_request_collection.find_one({
        "userid": userid,
        "account_type": request.account_type,
        "status": "pending",
    })

    if existing:
        raise HTTPException(status_code=409, detail="같은 종류의 계정 연결이 이미 존재합니다.")

    document = request.model_dump()
    document.update({
        "userid": userid,
        "status": "pending",
        "created_at": datetime.now(timezone(timedelta(hours=9)))
    })

    result = await account_request_collection.insert_one(document)

    return{
        "message": "계정 연결 신청을 완료하였습니다."
    }