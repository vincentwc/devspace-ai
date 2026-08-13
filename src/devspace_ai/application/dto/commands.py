"""应用层入站命令：与 HTTP Form 字段对应，不含框架类型。"""

from dataclasses import dataclass


@dataclass
class GenerateCaseDraftsCommand:
    # text 与 file_* 由服务层强制二选一
    text: str | None
    file_name: str | None
    file_bytes: bytes | None
    language: str = "zh-CN"
    max_cases: int | None = None  # None → 使用 Settings.default_max_cases
    domain_hint: str | None = None
    style_pack_id: str | None = None  # None / 空字符串 → 未选包
