from fastapi import APIRouter, Depends
from datetime import datetime
from routers.auth import get_current_user

router = APIRouter()

@router.get("/status")
async def control_status(current_user=Depends(get_current_user)):
    return {"controller_name": "중앙관제센터", "current_time": datetime.now()}

@router.get("/map")
def control_map():
    return {
        "ambulances": [{"id": "a001", "location": "충주 시내"}],
        "hospitals": [{"id": "h001", "location": "충주병원", "status": "ON"}]
    }

@router.get("/members")
def control_members():
    return {"hospitals": ["h001", "h002"], "ambulances": ["a001", "a002"]}

@router.get("/notifications")
def control_notifications():
    return [{"hospital_id": "h001", "action": "accepted"}]
