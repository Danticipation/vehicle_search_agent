from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml
import os

class LocationConfig(BaseModel):
    zip: str
    radius_miles: int

class VehicleCriteria(BaseModel):
    make: str
    model: str
    year_min: Optional[int] = None
    year_max: Optional[int] = None

class AgentParameters(BaseModel):
    vehicles: List[VehicleCriteria] = Field(default_factory=list)
    makes: List[str] = Field(default_factory=list)
    models: List[str] = Field(default_factory=list)
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_max: Optional[float] = None
    mileage_max: Optional[int] = None
    location: Optional[LocationConfig] = None
    features_any: List[str] = Field(default_factory=list)
    features_all: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)

class AgentConfig(BaseModel):
    id: str
    name: str
    enabled: bool = True
    schedule: str = "0 */2 * * *" # Default every 2 hours
    parameters: AgentParameters
    sources: List[str]
    notifications: dict # Simplified for now, can be expanded

class AppSettings(BaseSettings):
    DATABASE_URL: str
    GMAIL_USER: str
    GMAIL_APP_PASSWORD: str
    MARKETCHECK_API_KEY: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

def load_agents_from_yaml(path: str) -> List[AgentConfig]:
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
        return [AgentConfig(**agent) for agent in data.get('agents', [])]
