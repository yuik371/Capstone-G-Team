from pydantic import BaseModel, ConfigDict, EmailStr, Field

class HospitalCreate(BaseModel):
    hospitalid: int
    name: str = Field(min_length=1, max_length=100)
    er_status: str
    or_status: str

class HospitaLlink(BaseModel):
    hospitalid: int