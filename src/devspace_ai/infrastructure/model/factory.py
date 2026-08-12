from devspace_ai.application.port.outbound.model_port import ModelPort
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter


def build_model_adapter(settings: Settings) -> ModelPort:
    provider = settings.model_provider
    if provider == "fake" or not settings.model_api_key:
        return FakeModelAdapter()
    from devspace_ai.infrastructure.model.openai_compatible import OpenAICompatibleModelAdapter

    return OpenAICompatibleModelAdapter(settings)
