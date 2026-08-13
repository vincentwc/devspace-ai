"""风格包应用层异常：映射为 HTTP 404 / 多 issue 400。"""

from __future__ import annotations

from devspace_ai.domain.run.models import Issue


class PackNotFoundError(Exception):
    code = "PACK_NOT_FOUND"
    message = "风格包不存在"

    def __init__(self) -> None:
        super().__init__(self.message)


class IssuesRejectedError(Exception):
    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__(f"{len(issues)} issue(s)")
