
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from services.sse_service import send_hospital_sse
from db.mongo import hospitals_collection, patients_collection, amb_collection, emergency_request_collection
from bson import ObjectId

async def get_hospital_info(hospital):
    return{
        "hospitalid": hospital["hospitalid"],
        "name": hospital["name"],
        "er_status": hospital.get("er_status"),
        "or_status": hospital.get("or_status")       
    }

async def get_patient_requests(hospital):
    hospitalid = hospital["hospitalid"]

    cursor = emergency_request_collection.find({
        "hospitalid": hospitalid,"request_status":"pending"
        }).sort([("severity",1), ("created_at", -1)])

    requests = await cursor.to_list(length=100)

    for item in requests:
        item["id"] = str(item.pop("_id"))
        item["patientid"] = str(item["patientid"])

    return requests

async def get_accepted_patients(hospital):
    cursor = patients_collection.find({
        "hospitalid": hospital["hospitalid"], "request_status": "accepted"
                                       }).sort("handled_at",-1)

    patients = await cursor.to_list(length=100)

    for patient in patients:
        patient["id"] = str(patient.pop("_id"))

    return patients

async def get_requests_list(hospital):
    cursor = patients_collection.find({
        "hospitalid": hospital["hospitalid"], "request_status": {
            "$in": ["accepted","rejected"]
            }
        }).sort("handled_at",-1)

    items = await cursor.to_list(length=50)

    for item in items:
        item["id"] = str(item.pop("_id"))

    return items

async def get_hospital_map(hospital):
    hospital_location = hospital.get("location")

    if not hospital_location:
        raise HTTPException(status_code=409,detail="병원 좌표가 등록되지 않았습니다.")

    return {
        "hostpial":{
        "hospitalid": hospital["hospitalid"],
        "name": hospital.get("name"),
        "location": hospital_location
        }
    }

async def execute_decision_request(patientid, body, hospital):
    now = datetime.now(timezone(timedelta(hours=9)))
    mongoid = ObjectId(patientid)

    result = await emergency_request_collection.find_one({
        "patientid": mongoid,
        "hospitalid": hospital["hospitalid"],
        "request_status": "pending"
    })

    if result is None:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")

    if body.decision == "accepted":
        #환자 문서 상태 기록
        patients = await patients_collection.update_one({"_id": result["patientid"], "hospitalid": None, "request_status": "pending"},{
            "$set":{
                "hospitalid":hospital["hospitalid"],
                "request_status":"accepted",
                "handled_at": now    
            }
        })
        if patients.modified_count != 1:
            raise HTTPException(status_code=409, detail="다른 병원이 먼저 수락했습니다.")

        await emergency_request_collection.update_one({"patientid": mongoid, "request_status": "pending", "hospitalid": hospital["hospitalid"]},
                                                {
                                                    "$set":{
                                                        "request_status": body.decision,
                                                        "handled_at":now
                                                    }
                                                })

        await emergency_request_collection.update_many({"patientid": mongoid, "request_status": "pending"},{
            "$set":{
                "request_status": "cancelled",
                "handled_at": now
            }
        })

        hospitalids = await emergency_request_collection.distinct("hospitalid",{
            "patientid": mongoid, "request_status": "cancelled"
        })
        for hospitalid in hospitalids:
            await send_hospital_sse(hospitalid, "request_changed", "emergency_request_changed")

    else:
        await emergency_request_collection.update_one({"patientid": mongoid, "request_status": "pending", "hospitalid": hospital["hospitalid"]},
                                                        {
                                                            "$set":{
                                                                "request_status": body.decision,
                                                                "handled_at":now
                                                            }
                                                        })

    return {
        "message": "요청 처리 완료",
        "patientid": patientid,
        "request_status": body.decision
    }