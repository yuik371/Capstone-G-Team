from pydantic import BaseModel, ConfigDict, EmailStr, Field

class AmbCreate(BaseModel):
    ambid: int
    name: str = Field(min_length=1, max_length=100)

class AmbLink(BaseModel):
    ambid: int

class EmergencyCallPatientRequests(BaseModel):
    name: str
    image: str
    age: str
    symptom: str
    lat: float
    lon: float