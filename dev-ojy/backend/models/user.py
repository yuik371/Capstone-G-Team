from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    userid: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    userid: str
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    message: str
    token_type: str = "bearer"

class HospitalLinkRequestCreate(BaseModel):
    hospital_name: str  = Field(min_length=1, max_length=100)
    applicant_name: str = Field(min_length=1, max_length=50)
    position: str = Field(min_length=1, max_length=30)
    phone: int = Field(min_length=8, max_length=12)
    reason: str = Field(min_length=1, max_length=1000)

class AccountRequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    account_type: Literal["hospital", "amb"] = "hospital"
    account_name: str = Field(min_length=1, max_length=100)
    applicant_name: str = Field(min_length=1, max_length=80)
    position: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    reason: str = Field(min_length=1, max_length=1000)