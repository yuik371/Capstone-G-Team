from datetime import datetime, timezone, timedelta
from db.mongo import hospitals_collection, users_collection, amb_collection, account_request_collection, patients_collection, hospital_all_collection
from bson import ObjectId
from fastapi import HTTPException

async def execute_decision_request(request_id, body, admin):
    account_request = await account_request_collection.find_one({"_id": ObjectId(request_id)})

    if account_request["status"] != "pending":
        raise HTTPException(status_code=409, detail="이미 처리되었습니다.")

    if body.decision == "accepted":
        if account_request["account_type"] == "hospital":
            userid = account_request["userid"]
            hpid = account_request["hpid"]

            if await hospitals_collection.find_one({"hpid": hpid}):
                raise HTTPException(status_code=400, detail="이미 등록된 병원입니다.")
            
            user = await users_collection.find_one({"_id": ObjectId(userid)})
            if user.get("hospitalid") is not None:
                raise HTTPException(status_code=409, detail="사용자는 이미 병원에 연결되어있습니다.")

            last_hospital = await hospitals_collection.find_one(sort=[("hospitalid", -1)])

            if not last_hospital:
                new_hospital = 1
            else:
                new_hospital = last_hospital["hospitalid"] + 1

            hospital_info = await hospital_all_collection.find_one({"hpid": hpid}) 

            if not hospital_info:
                raise HTTPException(status_code=404,detail="병원 hpid를 찾을 수 없습니다.")

            await hospitals_collection.insert_one({
                "hospitalid": new_hospital,
                "hpid": hospital_info["hpid"],
                "name": account_request["account_name"],
                "er_status": "OFF",
                "or_status": "OFF",
                "location":{
                    "lat": hospital_info["location"]["lat"],
                    "lon": hospital_info["location"]["lon"]
                },
                "created_at": datetime.now(timezone(timedelta(hours=9)))
            })

            await users_collection.update_one({"_id": ObjectId(userid)},{
                "$set":{
                    "hospitalid": new_hospital,
                    "ambid": None,
                    "role": "hospital"
                }
            })

        elif account_request["account_type"] == "amb":
            userid = account_request.get("userid")

            user = await users_collection.find_one({"_id": ObjectId(userid)})
            if user.get("ambid") is not None:
                raise HTTPException(status_code=409, detail="사용자는 이미 구급대원에 연결되어있습니다.")            

            last_amb = await amb_collection.find_one(sort=[("ambid",-1)])

            if not last_amb:
                new_amb = 1
            else:
                new_amb = last_amb["ambid"] +1       

            await amb_collection.insert_one({
                "ambid": new_amb,
                "name": account_request["account_name"],
                "created_at": datetime.now(timezone(timedelta(hours=9)))
            })    

            await users_collection.update_one({"_id": ObjectId(userid)},{
                "$set":{
                    "ambid": new_amb,
                    "hospitalid": None,
                    "role": "amb"
                }
            })

        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 타입입니다.")

    await account_request_collection.update_one({"_id": ObjectId(request_id)},{
        "$set":{
            "status": body.decision,
            "decision_at": datetime.now(timezone(timedelta(hours=9))),
            "decision_by": str(admin["_id"])
        }
    })

    return {
        "message": "신청이 승인되었습니다." if body.decision == "accepted"
                else "신청이 거절되었습니다.",
        "status": body.decision
        }

async def get_account_requests():
    cursor = account_request_collection.find({"status": "pending"}).sort("created_at",-1)

    requests = await cursor.to_list(length = 100)

    for request in requests:
        request["id"] = str(request.pop("_id"))

    return {"requests": requests}


async def get_user_list():
    cursor = users_collection.find({"role": {"$in": ["hospital", "amb", "user"]}},{
        "password_hash": 0
    }).sort("created_at",-1)

    users = await cursor.to_list(length = 1000)

    for user in users:
        user["id"] = str(user.pop("_id"))

    return {"users": users}

async def get_patient_list():
    cursor = patients_collection.find().sort("created_at",-1)

    patients = await cursor.to_list(length=1000)

    for patient in patients:
            patient["id"] = str(patient.pop("_id"))

    return {"patients": patients}   

async def get_admin_map():
    hospitals_location = await hospitals_collection.find(
        {},
        {
            "_id": 0,
            "name": 1,
            "location": 1
        }
    ).to_list(length=1000)

    return {"hospitals_location": hospitals_location}