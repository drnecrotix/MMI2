from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MMI2 Schedule System"
    database_url: str = "sqlite:///./mmi2.db"
    jwt_secret: str = "change-this-in-production"
    admin_import_key: str = "change-this-admin-key"
    access_token_minutes: int = 43200

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
