from dataclasses import dataclass, field


@dataclass
class RequirementDocument:
    source_type: str  # paste | upload
    text: str
    title: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
