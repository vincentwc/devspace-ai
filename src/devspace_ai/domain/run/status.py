from .models import RunStatus


def resolve_status(valid_count: int, issue_count: int) -> RunStatus:
    if valid_count <= 0:
        return RunStatus.FAILED
    if issue_count > 0:
        return RunStatus.PARTIAL
    return RunStatus.SUCCEEDED
