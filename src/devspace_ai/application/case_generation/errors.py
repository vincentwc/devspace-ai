"""可预期的输入拒绝：映射为 HTTP 400，不进入模型调用。"""


class InputRejectedError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
