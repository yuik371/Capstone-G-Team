from typing import Literal
from pydantic import BaseModel

class AccountRequestDecision(BaseModel):
    decision: Literal["accepted", "rejected"]