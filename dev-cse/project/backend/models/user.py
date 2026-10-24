"""회원가입/로그인 요청과 토큰 응답 Pydantic 모델."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    userid: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: str


class LoginRequest(BaseModel):
    userid: str
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    message: str
    token_type: str = "bearer"
