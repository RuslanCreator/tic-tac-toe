import os

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import URL


class JwtSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    secret_key: SecretStr
    algorithm: str = Field(default="HS256", min_length=1)
    expire_minutes: int = Field(default=60, gt=0)

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET должен быть не короче 32 символов")
        return value

    @classmethod
    def from_env(cls) -> "JwtSettings":
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise RuntimeError("Не задана переменная окружения JWT_SECRET")

        return cls(
            secret_key=secret,
            algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
            expire_minutes=os.environ.get("JWT_EXPIRE_MINUTES", "60"),
        )


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    db_user: str = Field(min_length=1)
    db_name: str = Field(min_length=1)
    db_password: SecretStr | None = None
    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)

    jwt: JwtSettings

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.db_user,
            password=(
                self.db_password.get_secret_value() if self.db_password else None
            ),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @classmethod
    def from_env(cls) -> "Settings":
        required = ("DB_USER", "DB_NAME")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError(
                "Не заданы обязательные переменные окружения: " + ", ".join(missing)
            )

        return cls(
            db_user=os.environ["DB_USER"],
            db_name=os.environ["DB_NAME"],
            db_password=os.environ.get("DB_PASSWORD") or None,
            db_host=os.environ.get("DB_HOST", "localhost"),
            db_port=os.environ.get("DB_PORT", "5432"),
            jwt=JwtSettings.from_env(),
        )
