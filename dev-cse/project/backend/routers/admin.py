from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from db.mongo import hospitals_collection, users_collection, amb_collection
from routers.auth import get_current_user
from models.hospital import HospitalCreate, HospitaLlink
from models.amb import AmbCreate, AmbLink

router = APIRouter()

async def get_current_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자만 사용가능합니다. ")

    return user


#병원 등록
@router.post("/hospitals")
async def enrollhospital(hospital: HospitalCreate,admin=Depends(get_current_admin)):
    last_hospital = await hospitals_collection.find_one(sort=[("hospitalid", -1)])

    if not last_hospital:
        new_id = 1
    else:
        new_id = last_hospital["hospitalid"] + 1

    document = hospital.model_dump()
    document["hospitalid"] = new_id
   

    document["created_at"] = datetime.now(timezone(timedelta(hours=9)))
    result = await hospitals_collection.insert_one(document)

    return {
        "message": f"병원 등록 완료 {hospital.name}",
        "hospitalid": new_id,
        "mongoid": str(result.inserted_id)
    }


#사용자 id와 병원 id 연결
@router.patch("/users/{userid}/hospital")
async def link_user_hospital(userid: str, body: HospitaLlink, admin=Depends(get_current_admin)):
    hospital = await hospitals_collection.find_one({"hospitalid": body.hospitalid})
    if not hospital:
        raise HTTPException(status_code=404, detail="병원 ID가 존재하지않습니다.")

    user = await users_collection.find_one({"userid": userid})
    if not user:
        raise HTTPException(status_code=404,detail="유저 ID가 존재하지않습니다.")

    await users_collection.update_one({"_id": user["_id"]},
                                      {
                                          "$set":{
                                              "hospitalid": body.hospitalid,
                                              "role": "hospital",
                                          }
                                      },
                                      
                                      )
    return {
        "meassge": "사용자 계정을 병원에 연결했습니다.",
        "userid": userid,
        "hospitalid": body.hospitalid,
    }

#amb 캘랙션 생성
@router.post("/ambs")
async def enrollhospital(amb: AmbCreate,admin=Depends(get_current_admin)):
    last_amb = await amb_collection.find_one(sort=[("ambid", -1)])

    if not last_amb:
        new_id = 1
    else:
        new_id = last_amb["ambid"] + 1

    document = amb.model_dump()
    document["ambid"] = new_id
   

    document["created_at"] = datetime.now(timezone(timedelta(hours=9)))
    result = await amb_collection.insert_one(document)

    return {
        "message": f"구급차 등록 완료 {amb.name}",
        "ambid": new_id,
        "mongoid": str(result.inserted_id)
    }


#사용자 id와 amb 연결