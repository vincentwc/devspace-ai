"""根据「合法草稿数 / 问题数」裁定终态。

规则：
- 无合法草稿 → FAILED
- 有合法草稿且仍有问题 → PARTIAL
- 全部合法 → SUCCEEDED
"""

from .models import RunStatus


def resolve_status(valid_count: int, issue_count: int) -> RunStatus:
    if valid_count <= 0:
        return RunStatus.FAILED
    if issue_count > 0:
        return RunStatus.PARTIAL
    return RunStatus.SUCCEEDED
