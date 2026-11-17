from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime, timezone, timedelta

class HospitalCreate(BaseModel):
    hospitalid: int
    hpid: str
    name: str = Field(min_length=1, max_length=100)
    er_status: str
    or_status: str
    created_at:  datetime

class HospitaLlink(BaseModel):
    hospitalid: int