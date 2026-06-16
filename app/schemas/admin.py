from pydantic import BaseModel


class AdminSummaryResponse(BaseModel):
    """管理员后台总览统计。"""

    total_users: int
    student_users: int
    admin_users: int
    active_users: int
    inactive_users: int
    total_materials: int
    material_parse_status: dict[str, int]
    parse_task_status: dict[str, int]
    failed_tasks: int
    recent_logs: int


class AdminUserStatusUpdateRequest(BaseModel):
    """管理员启用或禁用用户请求。"""

    is_active: bool
