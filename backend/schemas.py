"""Request bodies. Responses are built as plain dicts in main.py."""
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")


class AddSymbolIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)


class SensitivityIn(BaseModel):
    level: str = Field(pattern="^(normal|low|muted)$")
