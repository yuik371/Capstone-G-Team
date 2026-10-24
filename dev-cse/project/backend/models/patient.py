from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Literal

class RequestDecision(BaseModel):
    decision: Literal["accepted", "rejected"]