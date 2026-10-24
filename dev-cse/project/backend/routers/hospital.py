from fastapi import FastAPI, Depends, HTTPException,APIRouter
from routers.auth import get_current_user
from db.mongo import hospitals_collection, patients_collection, amb_collection

from bson import ObjectId

from datetime import datetime, timezone

from models.patient import RequestDecision

router = APIRouter()

#hospital id 가져오기
async def get_current_hospital(user=Depends(get_current_user),):
    hospitalid = user.get("hospitalid")

    if hospitalid is None:
        raise HTTPException(status_code=403, detail="병원과의 연결이 되어있지 않습니다. 관리자에게 문의해주세요.")

    hospital = await hospitals_collection.find_one({"hospitalid": hospitalid})

    if not hospital:
        raise HTTPException(status_code=404, detail="병원 정보가 없습니다.")

    return hospital

#병원 정보 top
@router.get("/topstatus")
async def top_status_hospital(hospital=Depends(get_current_hospital),):
    return {
        "hospitalid": hospital["hospitalid"],
        "name": hospital["name"],
        "er_status": hospital.get("er_status"),
        "or_status": hospital.get("or_status")
    }

#환자 수용 요청 
@router.get("/requests")
async def get_patients_request(hospital=Depends(get_current_hospital)):
    hospitalid = hospital["hospitalid"]

    cursor = patients_collection.find({
        "hospitalid": hospitalid,
        "request_status": "None",
    }).sort([
        ("serverity",1),
        ("created_at",-1)
    ])

    requests = await cursor.to_list(length=100)

    for item in requests:
        item["id"] = str(item.pop("_id"))

    return requests

#환자 요청 수락|거절
@router.patch("/requsts/{requestsid}/decision")
async def decide_reqeust(
    requestid: str,
    body: RequestDecision,
    hospital=Depends(get_current_user),
):
    
    mongoid = ObjectId(requestid)

    result = await patients_collection.update_one({

    
        "_id": mongoid,
        "hospitalid": hospital["hospitalid"],
        "request_status" : "None",
    },
    {
        "$set": {
            "requests_status": body.decision,
            "handled_at": datetime.now(timezone.utc),
        }
    }
    )

    return {
        "message": "요청 처리",
        "reqeustid": requestid,
        "request_status": body.decision
    }

    
#수락 환자 리스트
@router.get("/accepted")
async def get_accepted_patients(hospital=Depends(get_current_hospital)):
    cursor = patients_collection.find({
        "hospitalid": hospital["hospitalid"],
        "request_status": "accepted",
    }).sort('handled_at',-1)

    patients = await cursor.to_list(length=100)

    for patient in patients:
        patients["id"] = str(patient.pop("_id"))

    return patients

#최근 요청 리스트
@router.get("/requestlist")
async def get_reqeustlist(hospital = Depends(get_current_hospital)):
    cursor = patients_collection.find({
        "hospitalid": hospital["hospitalid"],
        "request_status": {"$in": ["accepted", "rejected"]},
    }).sort("handled_at",-1)

    history = await cursor.to_list(length=50)

    for item in history:
        item["id"] = str(item.pop("_id"))

    return history

#구급차 위치 조회

#지도