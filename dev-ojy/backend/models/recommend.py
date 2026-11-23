from pydantic import BaseModel, ConfigDict, EmailStr, Field

class EmergencyLinkRequest(BaseModel):
    region1: str = Field(description="예: 충청북도")
    region2: str = Field(description="예: 충주시")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    patient_status: str
    patient_name: str | None = None
    image_url: str | None = None
