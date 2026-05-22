"""
Provider Factory Module
=======================
Factory for creating and managing LLM providers.
"""

from typing import Optional, Dict, Type
from .base import BaseProvider, ProviderType
from .ollama import OllamaProvider
from src.core.config import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)


class ProviderFactory:
    """Factory for creating and managing LLM providers."""

    _providers: Dict[str, BaseProvider] = {}
    _default: Optional[BaseProvider] = None
    _registry: Dict[str, Type[BaseProvider]] = {
        "ollama": OllamaProvider,
    }

    @classmethod
    def register(cls, name: str, provider_class: Type[BaseProvider]):
        """Register a new provider class."""
        cls._registry[name.lower()] = provider_class
        logger.info(f"Registered provider: {name}")

    @classmethod
    def create(
        cls,
        name: str = "ollama",
        model: Optional[str] = None,
        **kwargs
    ) -> BaseProvider:
        """Create a provider by name."""
        config = get_config()
        model = model or config.provider.model
        key = f"{name}_{model}"

        if key not in cls._providers:
            if name.lower() not in cls._registry:
                raise ValueError(f"Unknown provider: {name}. Available: {list(cls._registry.keys())}")

            provider_class = cls._registry[name.lower()]
            cls._providers[key] = provider_class(model=model, **kwargs)
            logger.info(f"Created provider: {key}")

        return cls._providers[key]

    @classmethod
    def get_default(cls) -> Optional[BaseProvider]:
        """Get default available provider."""
        if cls._default is not None:
            return cls._default

        config = get_config()

        try:
            ollama = OllamaProvider(
                model=config.provider.model,
                host=config.provider.host
            )
            if ollama.is_available():
                cls._default = ollama
                logger.info("Using Ollama as default provider")
                return cls._default
        except Exception as e:
            logger.warning(f"Could not initialize Ollama: {e}")

        logger.warning("No default provider available")
        return None

    @classmethod
    def get_all_providers(cls) -> Dict[str, BaseProvider]:
        """Get all created providers."""
        return cls._providers.copy()

    @classmethod
    def check_all_providers(cls) -> Dict[str, bool]:
        """Check availability of all registered provider types."""
        status = {}

        for name, provider_class in cls._registry.items():
            try:
                provider = provider_class()
                status[name] = provider.is_available()
            except Exception as e:
                logger.debug(f"Provider {name} check failed: {e}")
                status[name] = False

        return status

    @classmethod
    def clear_cache(cls):
        """Clear provider cache."""
        cls._providers.clear()
        cls._default = None
        logger.info("Cleared provider cache")

    @classmethod
    def reset(cls):
        """Reset all providers and cache."""
        cls._providers.clear()
        cls._default = None
        cls._registry.clear()
        cls._registry["ollama"] = OllamaProvider
        logger.info("Reset provider factory")


def get_provider(name: str = "ollama", **kwargs) -> Optional[BaseProvider]:
    """Convenience function to get a provider."""
    return ProviderFactory.create(name, **kwargs)


def get_default_provider() -> Optional[BaseProvider]:
    """Convenience function to get the default provider."""
    return ProviderFactory.get_default()