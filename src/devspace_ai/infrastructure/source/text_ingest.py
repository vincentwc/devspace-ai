"""需求文本摄入：粘贴与上传统一成 RequirementDocument。

v1 只支持 .txt / .md；外部需求系统适配器以后再挂。
"""

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.domain.requirement.models import RequirementDocument

ALLOWED_SUFFIXES = {".txt", ".md"}


def ingest_text(text: str, *, max_chars: int) -> RequirementDocument:
    if text is None or not str(text).strip():
        raise InputRejectedError("INVALID_INPUT", "文本不能为空")
    normalized = str(text)
    if len(normalized) > max_chars:
        raise InputRejectedError(
            "INPUT_TOO_LONG",
            f"文本长度 {len(normalized)} 超出上限 {max_chars}",
        )
    return RequirementDocument(
        source_type="paste",
        text=normalized,
        metadata={"chars": len(normalized)},
    )


def ingest_upload(
    filename: str,
    raw: bytes,
    *,
    max_bytes: int,
    max_chars: int,
) -> RequirementDocument:
    name = filename or ""
    lower = name.lower()
    if not any(lower.endswith(suf) for suf in ALLOWED_SUFFIXES):
        raise InputRejectedError(
            "UNSUPPORTED_FILE_TYPE",
            "仅支持上传 .txt 或 .md 文件",
        )
    if len(raw) > max_bytes:
        raise InputRejectedError(
            "FILE_TOO_LARGE",
            f"文件大小 {len(raw)} 字节超出上限 {max_bytes} 字节",
        )
    # 非法字节用 replacement，避免因编码问题直接 500
    text = raw.decode("utf-8", errors="replace")
    doc = ingest_text(text, max_chars=max_chars)
    doc.source_type = "upload"
    doc.title = name
    doc.metadata.update({"filename": name, "bytes": len(raw)})
    return doc
