from pydantic import BaseModel, ConfigDict, EmailStr, Field

class AmbCreate(BaseModel):
    ambid: int
    name: str = Field(min_length=1, max_length=100)

class AmbLink(BaseModel):
    ambid: int