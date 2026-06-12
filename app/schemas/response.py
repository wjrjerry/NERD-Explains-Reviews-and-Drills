from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="Business status code. 0 means success.")
    message: str = Field(default="success", description="Human-readable response message.")
    data: T | None = Field(default=None, description="Actual response payload.")


class PageResult(BaseModel, Generic[T]):
    items: list[T] = Field(description="Current page items.")
    total: int = Field(ge=0, description="Total number of matched records.")
    page: int = Field(ge=1, description="Current page number.")
    page_size: int = Field(ge=1, description="Number of records per page.")
