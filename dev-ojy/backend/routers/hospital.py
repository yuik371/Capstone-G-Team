from fastapi import FastAPI, Depends, HTTPException,APIRouter
from routers.auth import get_current_user
from db.mongo import hospitals_collection, patients_collection, amb_collection, emergency_request_collection
from bson import ObjectId

from datetime import datetime, timezone, timedelta

from models.patient import RequestDecision

from services.hospital_service import get_hospital_info, get_patient_requests, get_accepted_patients, get_requests_list, get_hospital_map, execute_decision_request
from services.sse_service import send_hospital_sse, execute_hospital_sse

router = APIRouter()

#hospital id 가져오기
async def get_current_hospital(user=Depends(get_current_user),):
    hospitalid = user.get("hospitalid")

    if user.get("role") != "hospital":
        raise HTTPException(status_code=403, detail="병원 계정만 접근 가능합니다.")

    if hospitalid is None:
        raise HTTPException(status_code=403, detail="병원과의 연결이 되어있지 않습니다. 관리자에게 문의해주세요.")

    hospital = await hospitals_collection.find_one({"hospitalid": hospitalid})

    if not hospital:
        raise HTTPException(status_code=404, detail="병원 정보가 없습니다.")

    return hospital



#hospital sse
@router.get("/sse", summary="sse 접속유지")
async def hospital_sse(hospital = Depends(get_current_hospital)):
    return await execute_hospital_sse(hospital)
    

#병원 정보 top
@router.get("/info", summary="병원 기본 정보")
async def hospital_info(hospital=Depends(get_current_hospital),):
    return await get_hospital_info(hospital)

#환자 수용 요청 
@router.get("/requests", summary="요청 환자 list 반환")
async def patient_requests(hospital=Depends(get_current_hospital)):
    return await get_patient_requests(hospital)

#환자 요청 수락|거절
@router.patch("/requests/{patientid}/decision", summary="요청 환자 수락|거절")
async def decision_reqeust(patientid: str, body: RequestDecision, hospital=Depends(get_current_hospital)):
    return await execute_decision_request(patientid, body, hospital)
    
#수락 환자 리스트
@router.get("/accepted", summary="수락된 환자 리스트")
async def accepted_patients(hospital=Depends(get_current_hospital)):
    return await get_accepted_patients(hospital)

#최근 요청 리스트
@router.get("/requests/list", summary="최근 환자 리스트 반환")
async def reqeusts_list(hospital = Depends(get_current_hospital)):
    return await get_requests_list(hospital)

#병원 location 반환 
@router.get("/map",summary="병원 위치 조회(kakaomap)")
async def hospital_map(hospital = Depends(get_current_hospital)):
    return await get_hospital_map(hospital)




