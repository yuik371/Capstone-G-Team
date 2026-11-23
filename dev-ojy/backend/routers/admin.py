from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from db.mongo import hospitals_collection, users_collection, amb_collection, account_request_collection, patients_collection
from routers.auth import get_current_user
from services.er_service import get_hospital_basic_status, hospital_all_update
from models.hospital import HospitalCreate, HospitaLlink
from models.amb import AmbCreate, AmbLink
from models.admin import AccountRequestDecision
from services.er_service import hospital_all_first
from services.admin_service import execute_decision_request, get_account_requests, get_user_list, get_patient_list, get_admin_map
from bson import ObjectId
import os
import httpx
import xml.etree.ElementTree as ET

ER_API_KEY  = os.getenv("ER_API_KEY")

router = APIRouter()

async def get_current_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자만 사용가능합니다. ")
    return user

#계정 발급 decision
@router.patch("/account/requests/{request_id}/decision", summary="계정 발급 수락|거절")
async def decision_account_request(request_id: str,body: AccountRequestDecision, admin=Depends(get_current_admin)):
    return await execute_decision_request(request_id, body, admin)
    
    
#계정 발급 요청 list 조회
@router.get("/account/requests", summary="계정 발급 요청 조회")
async def account_request(admin=Depends(get_current_admin)):
    return await get_account_requests()    

#사용자 계정 목록 조회
@router.get("/user/list", summary="유저 목록 조회")
async def user_list(admin=Depends(get_current_admin)):
    return await get_user_list() 

#요청된 환자 목록 총 조회
@router.get("/patient/list", summary="요청된 환자 목록 총 조회")
async def patient_list(admin=Depends(get_current_admin)):
    return await get_patient_list()

#가입된 병원 위치 조회
@router.get("/hospital/map",summary="가입된 병원 위치 조회")
async def admin_map(admin=Depends(get_current_admin)):
    return await get_admin_map()

#모든 병원 위치 수동 작성
@router.get("/hospital/all/first", summary="모든 병원 정보 작성")
async def hospital_all_base_info(admin=Depends(get_current_admin)):
    result = await hospital_all_first()
    await hospital_all_update()
    return result


