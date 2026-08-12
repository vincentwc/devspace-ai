"""单条草稿校验失败；`field` 为 JSON 路径风格定位（如 steps[0].action）。"""


class CaseDraftValidationError(ValueError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field
