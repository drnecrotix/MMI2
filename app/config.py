from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MMI2 Schedule System"
    database_url: str = "sqlite:///./mmi2.db"
    jwt_secret: str = "change-this-in-production"
    access_token_minutes: int = 43200

    # Admin credentials are deployment secrets and must be overridden in .env.
    admin_username: str = "admin"
    admin_password: str = "change-this-admin-password"
    admin_token_minutes: int = 480

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
