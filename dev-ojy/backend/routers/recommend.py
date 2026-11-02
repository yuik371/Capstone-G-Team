#현재 구조가 1위 병원 -> 바로선택 -> 환자 컬랙션에 저장
from fastapi import FastAPI, Depends, HTTPException,APIRouter
from db.mongo import hospitals_collection, patients_collection
from bson import ObjectId
from datetime import datetime, timezone
import os
import math
import uuid
import xml.etree.ElementTree as ET

from routers.auth import get_current_user
from models.recommend import EmergencyLinkRequest

from dotenv import load_dotenv
import httpx
import xml.etree.ElementTree as ET

router = APIRouter()
ER_API_KEY= os.getenv("ER_API_KEY")
ER_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService"

def xml_items(xml_data: bytes):
    root = ET.fromstring(xml_data)
    items = []

    for item in root.findall(".//item"):
        items.append({
            child.tag: (child.text or "").strip()
            for child in item
        })

    return items

def to_float(value: str | None):
    try:
        return float(value) if value else None
    except ValueError:
        return None

def to_int(value: str | None):
    try:
        return max(0, int(value)) if value else 0
    except ValueError:
        return 0

#최단거리 계산
def distance_km(lat1: float, lon1: float, lat2: float, lon2: float):
    earth_radius_km = 6371
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def fetch_items(
    client: httpx.AsyncClient,
    operation: str,
    params: dict,
) -> list[dict[str, str]]:
    response = await client.get(
        f"{ER_URL}/{operation}",
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return xml_items(response.content)

#/emergency-call
@router.post("/emergency-call")
async def create_emergency_link(request: EmergencyLinkRequest, current_user=Depends(get_current_user)):
    if not ER_API_KEY:
        raise HTTPException(status_code=401, detail="ER_API_KEY 설정 이상")

    ambid = current_user.get("ambid")
    if not ambid:
        raise HTTPException(status_code=403, detail="구급대원 계정 연결 이상")

    params={
        "pageNo":1,
        "numOfRows": 1000,
        "ServiceKey": ER_API_KEY
    }

    try:
        async with httpx.AsyncClient() as client:
            hospital_items, bed_items = await __import__("asyncio").gather(
                fetch_items(
                    client,
                    "getEgytListInfoInqire",
                    {
                        **params,
                        "Q0": request.region1,
                        "Q1": request.region2,
                    },
                ),
                fetch_items(
                    client,
                    "getEmrrmRltmUsefulSckbdInfoInqire",
                    {
                        **params,
                        "STAGE1": request.region1,
                        "STAGE2": request.region2,
                    },
                ),
            )
    except (httpx.HTTPError, ET.ParseError): 
        raise HTTPException(status_code=404, detail="의료기관 정보를 가져오지 못했습니다.")


    beds_hpid = {
        item.get("hpid"): to_int(item.get("hvec"))
        for item in bed_items
        if item.get("hpid")
    }

    candidates = []

    for item in hospital_items:
        # 응급실 운영 여부 코드 1인 병원만 후보에 포함
        if item.get("dutyEryn") != "1":
            continue

        hpid = item.get("hpid")
        latitude = to_float(item.get("wgs84Lat"))
        longitude = to_float(item.get("wgs84Lon"))

        if not hpid or latitude is None or longitude is None:
            continue

        candidates.append({
            "hpid": hpid,
            "name": item.get("dutyName", "이름 미상"),
            "address": item.get("dutyAddr", ""),
            "distance_km": distance_km(
                request.latitude,
                request.longitude,
                latitude,
                longitude,
            ),
            "available_beds": beds_hpid.get(hpid, 0),
        })

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="해당 지역에서 응급실 운영 병원을 찾지 못했습니다.",
        )

    # 점수는 후보 병원 사이에서 0~100으로 정규화한다.
    min_distance = min(item["distance_km"] for item in candidates)
    max_distance = max(item["distance_km"] for item in candidates)
    max_beds = max(item["available_beds"] for item in candidates)

    for item in candidates:
        if max_distance == min_distance:
            distance_score = 100
        else:
            distance_score = (
                (max_distance - item["distance_km"])
                / (max_distance - min_distance)
                * 100
            )

        bed_score = (
            item["available_beds"] / max_beds * 100
            if max_beds > 0
            else 0
        )

        item["score"] = round(distance_score * 0.6 + bed_score * 0.4, 2)
        item["distance_km"] = round(item["distance_km"], 2)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected = candidates[0]

    # 공공데이터 병원 ID(hpid)를 내부 병원 문서와 연결한다.
    hospital = await hospitals_collection.find_one({"hpid": selected["hpid"]})
    if not hospital:
        raise HTTPException(status_code=409,detail="추천 병원이 hospitals 컬렉션에 연결되어 있지 않습니다. 병원 문서에 hpid를 등록해 주세요.")

    patientid = str(uuid.uuid4())
    patient_document = {
        "patientid": patientid,
        "hospitalid": hospital["hospitalid"],
        "hpid": selected["hpid"],
        "ambid": ambid,
        "name": request.patient_name or "미상",
        "patient_status": request.patient_status,
        "image": request.image_url,
        "request_status": "pending",
        "created_at": datetime.now(timezone.utc),
        "handled_at": None,
        "match_score": selected["score"],
        "distance_km": selected["distance_km"],
        "available_beds": selected["available_beds"],
    }

    await patients_collection.insert_one(patient_document)

    return {
        "message": "병원 매칭 및 수용 요청 등록이 완료되었습니다.",
        "patientid": patientid,
        "selected_hospital": selected,
        "hospital_candidates": candidates,
    }    