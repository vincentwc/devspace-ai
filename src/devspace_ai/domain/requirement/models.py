"""摄入后的需求文档：后续 Graph 只读 text，元数据供审计/扩展。"""

from dataclasses import dataclass, field


@dataclass
class RequirementDocument:
    source_type: str  # paste | upload（预留外部系统适配）
    text: str
    title: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
