import pytest

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.infrastructure.source.text_ingest import ingest_text, ingest_upload


def test_reject_empty_text():
    with pytest.raises(InputRejectedError) as ei:
        ingest_text("  ", max_chars=100)
    assert ei.value.code == "INVALID_INPUT"


def test_reject_too_long():
    with pytest.raises(InputRejectedError) as ei:
        ingest_text("a" * 11, max_chars=10)
    assert ei.value.code == "INPUT_TOO_LONG"
    assert "10" in ei.value.message


def test_reject_bad_extension_and_size():
    with pytest.raises(InputRejectedError) as ei:
        ingest_upload("a.pdf", b"x", max_bytes=10, max_chars=100)
    assert ei.value.code == "UNSUPPORTED_FILE_TYPE"
    with pytest.raises(InputRejectedError) as ei:
        ingest_upload("a.txt", b"01234567890", max_bytes=10, max_chars=100)
    assert ei.value.code == "FILE_TOO_LARGE"


def test_accept_md():
    doc = ingest_upload("req.md", b"# hello", max_bytes=100, max_chars=100)
    assert doc.text == "# hello"
    assert doc.source_type == "upload"
