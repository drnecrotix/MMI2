from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MMI2 Schedule System"
    database_url: str = "sqlite:///./mmi2.db"
    jwt_secret: str = "change-this-in-production"
    access_token_minutes: int = 43200

    # Bootstrap credentials are used only while the admin_users table is empty.
    # ADMIN_EMAIL is preferred; ADMIN_USERNAME remains as a compatibility fallback.
    # The web installer disables bootstrap after it creates the owner directly.
    admin_bootstrap_enabled: bool = True
    admin_email: str = ""
    admin_username: str = "admin"
    admin_password: str = "change-this-admin-password"
    admin_token_minutes: int = 480

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
