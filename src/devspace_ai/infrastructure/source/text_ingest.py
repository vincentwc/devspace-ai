from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.domain.requirement.models import RequirementDocument

ALLOWED_SUFFIXES = {".txt", ".md"}


def ingest_text(text: str, *, max_chars: int) -> RequirementDocument:
    if text is None or not str(text).strip():
        raise InputRejectedError("INVALID_INPUT", "text must be non-empty when provided")
    normalized = str(text)
    if len(normalized) > max_chars:
        raise InputRejectedError(
            "INPUT_TOO_LONG",
            f"text length {len(normalized)} exceeds limit {max_chars}",
        )
    return RequirementDocument(source_type="paste", text=normalized, metadata={"chars": len(normalized)})


def ingest_upload(filename: str, raw: bytes, *, max_bytes: int, max_chars: int) -> RequirementDocument:
    name = filename or ""
    lower = name.lower()
    if not any(lower.endswith(suf) for suf in ALLOWED_SUFFIXES):
        raise InputRejectedError(
            "UNSUPPORTED_FILE_TYPE",
            "only .txt and .md uploads are supported",
        )
    if len(raw) > max_bytes:
        raise InputRejectedError(
            "FILE_TOO_LARGE",
            f"file size {len(raw)} bytes exceeds limit {max_bytes} bytes",
        )
    text = raw.decode("utf-8", errors="replace")
    doc = ingest_text(text, max_chars=max_chars)
    doc.source_type = "upload"
    doc.title = name
    doc.metadata.update({"filename": name, "bytes": len(raw)})
    return doc
