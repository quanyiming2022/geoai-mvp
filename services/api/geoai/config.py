from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr
    redis_url: SecretStr
    supabase_url: str
    supabase_public_url: str
    service_role_key: SecretStr
    anon_key: SecretStr
    storage_bucket: str = "geoai"
    max_upload_bytes: int = Field(default=536870912, ge=1024, le=10737418240)
