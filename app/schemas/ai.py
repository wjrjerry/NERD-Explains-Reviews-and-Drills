from enum import StrEnum


class AiTaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
