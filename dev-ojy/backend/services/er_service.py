import httpx
import xml.etree.ElementTree as ET
import os
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from db.mongo import hospital_all_collection, hospitals_collection
import asyncio

ER_API_KEY = os.getenv("ER_API_KEY")


async def get_hospital_basic_status(hpid: str):
    url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytBassInfoInqire"
    try:   
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url,
                                        params={
                                            "serviceKey": ER_API_KEY,
                                            "pageNo": 1,
                                            "HPID": hpid,
                                            "numOfRows": 1000
                                        })

            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="공공데이터 API 연결 실패") from exc

    root = ET.fromstring(response.text)

    item = root.find(".//item")

    return item


async def get_hospital_location():
    url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
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
        raise HTTPException(status_code=502, detail="공공데이터 API 연결 실패") from exc

    root = ET.fromstring(response.text)
    items = root.findall(".//item")
    return items 



async def get_hospital_distance(lat: float, lon: float):
    recommend_url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytLcinfoInqire"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(recommend_url,
                                        params={
                                            "serviceKey": ER_API_KEY,
                                            "WGS84_LAT": lat,
                                            "WGS84_LON": lon,
                                            "pageNo": 1,
                                            "numOfRows": 10
                                        })
            response.raise_for_status()

    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="공공데이터 API 연결 실패") from exc    

    root = ET.fromstring(response.text)

    items = root.findall(".//item")
    return items

async def hospital_all_first():
    first_url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytBassInfoInqire"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(first_url,
                                        params={
                                            "serviceKey": ER_API_KEY,
                                            "pageNo": 1,
                                            "numOfRows": 1000
                                        })
            response.raise_for_status()

    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="공공데이터 API 연결 실패") from exc    

    root = ET.fromstring(response.text)

    items = root.findall(".//item")
    for item in items:
        hpid = item.findtext("hpid")
        if not hpid:
            continue
        name = item.findtext("dutyName")
        addr = item.findtext("dutyAddr")
        lat = item.findtext("wgs84Lat")
        lon = item.findtext("wgs84Lon")
        number = item.findtext("dutyTel1")

        await hospital_all_collection.update_one({"hpid": hpid},{
            "$set":{
                "name": name,
                "addr": addr,
                "number": number,
                "location": {
                    "lat": lat,
                    "lon": lon
                },
                "updated_at": datetime.now(timezone(timedelta(hours=9))),
            },
            "$setOnInsert": {
                "hospitalid": None,
                "is_member": False,
                "er1_count":0,
                "er2_count":0,
                "er3_count":0,
                "er4_count":0,
                "or_count": 0,
                "created_at": datetime.now(timezone(timedelta(hours=9)))
            }
        },upsert=True)

    return {"status": "최초 등록 성공", "count": len(items)}

def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

#응급실 여부 및 카운트 백그라운드 함수
async def hospital_all_background():
    background_url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
    while True:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(background_url,
                                            params={
                                                "serviceKey": ER_API_KEY,
                                                "pageNo": 1,
                                                "numOfRows": 1000
                                            })

                response.raise_for_status()
        except httpx.HTTPError:
            print("API 백그라운 연결 실패")
            await asyncio.sleep(30)
            continue

        cursor = hospitals_collection.find({},{
            "_id": 0,
            "hpid": 1,
            "hospitalid": 1
        })

        members = {}

        async for hospital in cursor:
            hpid = hospital["hpid"]
            if not hpid:
                continue
            members[hpid] = hospital["hospitalid"]

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            print("XML 파싱 실패")
            await asyncio.sleep(30)
            continue
        
        items = root.findall(".//item")

        for item in items:
            hpid = item.findtext("hpid")
            if not hpid:
                continue
            hvs01 = to_int(item.findtext("hvs01"))
            hvs02 = to_int(item.findtext("hvs02"))
            hvs03 = to_int(item.findtext("hvs03"))
            hvs04 = to_int(item.findtext("hvs04"))

            is_member = hpid in members
            hospitalid = members.get(hpid)

            await hospital_all_collection.update_one({"hpid":hpid},{
                "$set":{
                    "er1_count":hvs01,
                    "er2_count":hvs02,
                    "er3_count":hvs03,
                    "er4_count":hvs04,
                    "is_member": is_member,
                    "hospitalid": hospitalid,
                    "updated_at": datetime.now(timezone(timedelta(hours=9)))
                }
            })

        await asyncio.sleep(60)

async def hospital_all_update():
    background_url = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(background_url,
                                        params={
                                            "serviceKey": ER_API_KEY,
                                            "pageNo": 1,
                                            "numOfRows": 1000
                                        })

            response.raise_for_status()
    except httpx.HTTPError:
        print("API 백그라운 연결 실패")

    cursor = hospitals_collection.find({},{
        "_id": 0,
        "hpid": 1,
        "hospitalid": 1
    })

    members = {}

    async for hospital in cursor:
        hpid = hospital["hpid"]
        if not hpid:
            continue
        members[hpid] = hospital["hospitalid"]

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        print("XML 파싱 실패")
    
    items = root.findall(".//item")

    for item in items:
        hpid = item.findtext("hpid")
        if not hpid:
            continue
        hvs01 = to_int(item.findtext("hvs01"))
        hvs02 = to_int(item.findtext("hvs02"))
        hvs03 = to_int(item.findtext("hvs03"))
        hvs04 = to_int(item.findtext("hvs04"))

        is_member = hpid in members
        hospitalid = members.get(hpid)

        await hospital_all_collection.update_one({"hpid":hpid},{
            "$set":{
                "er1_count":hvs01,
                "er2_count":hvs02,
                "er3_count":hvs03,
                "er4_count":hvs04,
                "is_member": is_member,
                "hospitalid": hospitalid,
                "updated_at": datetime.now(timezone(timedelta(hours=9)))
            }
        })   