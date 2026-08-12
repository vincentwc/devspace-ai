"""按配置选择模型适配器。

规则：显式 fake、或未配置 API Key 时走 Fake（本地/CI 无需真实模型）。
"""

from devspace_ai.application.port.outbound.model_port import ModelPort
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter


def build_model_adapter(settings: Settings) -> ModelPort:
    provider = settings.model_provider
    if provider == "fake" or not settings.model_api_key:
        return FakeModelAdapter()
    from devspace_ai.infrastructure.model.openai_compatible import OpenAICompatibleModelAdapter

    return OpenAICompatibleModelAdapter(settings)
