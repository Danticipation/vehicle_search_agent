from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel

class RawListing(BaseModel):
    external_id: str
    source: str
    url: str
    title: str
    price: Optional[float] = None
    mileage: Optional[int] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    images: List[str] = []
    raw_data: dict = {}

class BaseProvider(ABC):
    @abstractmethod
    async def search(self, params: dict) -> List[RawListing]:
        pass
