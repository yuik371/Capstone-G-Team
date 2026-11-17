from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import os

from db.mongo import users_collection, account_request_collection, amb_collection, patients_collection, emergency_request_collection, hospitals_collection
from routers.auth import get_current_user
from services.er_service import get_hospital_basic_status, get_hospital_distance
from services.amb_service import get_recommend_hospital, create_patient_status, get_transported_patient
from services.sse_service import execute_amb_sse
from models.amb import EmergencyCallPatientRequests
from services.sse_service import send_hospital_sse

router = APIRouter()

ER_API_KEY = os.getenv("ER_API_KEY")

#amb id 가져오기
async def get_current_amb(user=Depends(get_current_user),):
    ambid = user.get("ambid")

    if user.get("role") != "amb":
        raise HTTPException(status_code=403, detail="구급대원 계정만 접근 가능합니다.")

    if ambid is None:
        raise HTTPException(status_code=403, detail="구급대원과의 연결이 되어있지 않습니다. 관리자에게 문의해주세요.")

    amb = await amb_collection.find_one({"ambid": ambid})

    if not amb:
        raise HTTPException(status_code=404, detail="구급대원 정보가 없습니다.")

    return amb

#amb sse
@router.get("/sse", summary="sse 접속유지")
async def amb_sse(amb = Depends(get_current_amb)):
    return await execute_amb_sse(amb)

#중증도 예측 모델 임시
async def severity_model(image: str):
    severity = 1
    return severity

#emergency-call
@router.post("/emergency/call",summary="모바일 응급구조 콜(모바일에 hospital_recommend 반환)")
async def get_emergency_call(req: EmergencyCallPatientRequests,amb = Depends(get_current_amb)):
    #중증도 예측 모델(severity 값 채우기)
    severity = await severity_model(req.image)
    ambid = amb["ambid"]

    #플러터(모바일 앱)에서 환자 정보 입력
    result = await create_patient_status(req, ambid, severity)
    patientid = result.inserted_id

    #추천 병원 탐색(hospital_all 으로 전체 좌표 조회) =>   
    hospital_recommend = await get_recommend_hospital(req ,req.lat, req.lon, severity, patientid)

    return hospital_recommend

#수행한 환자 list
@router.get("/patient/list", summary="수행한 환자 리스트")
async def get_patient_list(amb = Depends(get_current_amb)):
    patients = await get_transported_patient(amb)

    return patients
                           

@router.get("/sse-test")
async def test_sse(amb=Depends(get_current_amb)):
    await send_hospital_sse(7,"test","TEST")
    return {"ok": True, "sent_to": 7}

#길찾기 