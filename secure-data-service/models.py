from pydantic import BaseModel, Field
from typing import Any, Dict

class StoreRequest(BaseModel):
    source: str = Field(...)
    timestamp: str = Field(...)
    payload: Dict[str, Any] = Field(...)
