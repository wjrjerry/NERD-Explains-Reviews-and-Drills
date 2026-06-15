from typing import Any, TypeVar

from app.schemas.response import ApiResponse, PageResult

T = TypeVar("T")


def success(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    return ApiResponse[T](code=0, message=message, data=data)


def fail(code: int, message: str, data: Any = None) -> ApiResponse[Any]:
    return ApiResponse[Any](code=code, message=message, data=data)


def page_result(items: list[T], total: int, page: int, page_size: int) -> PageResult[T]:
    return PageResult[T](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
