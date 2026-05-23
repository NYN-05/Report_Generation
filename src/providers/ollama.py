"""
Ollama Provider Module
=======================
Ollama LLM provider implementation.
"""

from typing import List, Optional, Dict
from .base import BaseProvider, LLMResponse, Message, CompletionOptions, ProviderType
from .retry import RetryStrategy, CircuitBreaker, with_retry
from src.core.exceptions import ProviderException, ProviderNotAvailableError, ProviderTimeoutError
from src.core.logger import get_logger
from src.core.config import get_config

logger = get_logger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama LLM provider implementation."""

    def __init__(
        self,
        model: str = "llama3.2:3b",
        host: str = "http://localhost:11434",
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: int = 120,
        **kwargs
    ):
        super().__init__(model, temperature, top_p, timeout, **kwargs)
        self.host = host
        self._client = None
        self._import_error: Optional[str] = None
        self._retry_strategy = RetryStrategy(max_attempts=3, base_delay=1.0)
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Ollama client."""
        try:
            import ollama
            self._client = ollama
            logger.debug(f"Initialized Ollama client for model {self.model}")
        except ImportError as e:
            self._import_error = str(e)
            logger.warning(f"Ollama not available: {e}")

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        if self._import_error:
            logger.debug(f"Ollama not available: {self._import_error}")
            return False

        if not self._circuit_breaker.can_attempt():
            logger.warning("Circuit breaker is open, Ollama not available")
            return False

        try:
            response = self._client.chat(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                options={"num_predict": 1}
            )
            self._circuit_breaker.record_success()
            return True
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.debug(f"Ollama not accessible: {e}")
            return False

    @with_retry(strategy=RetryStrategy(max_attempts=3, base_delay=2.0), circuit_breaker=None)
    def chat(
        self,
        messages: List[Message],
        options: Optional[CompletionOptions] = None
    ) -> LLMResponse:
        """Send chat request to Ollama."""
        if not self.is_available():
            raise ProviderNotAvailableError(
                "Ollama is not available. Please ensure Ollama is running.",
                details={"host": self.host, "model": self.model}
            )

        try:
            msg_dicts = [msg.to_dict() for msg in messages]
            completion_options = options or CompletionOptions(
                temperature=self.temperature,
                top_p=self.top_p
            )

            request_options = {
                "temperature": completion_options.temperature,
                "top_p": completion_options.top_p,
                "num_gpu": -1,
                "num_thread": 4,
            }

            if completion_options.max_tokens:
                request_options["num_predict"] = completion_options.max_tokens

            if completion_options.stop:
                request_options["stop"] = completion_options.stop

            logger.debug(f"Sending chat request to Ollama: {len(messages)} messages")

            response = self._client.chat(
                model=self.model,
                messages=msg_dicts,
                options=request_options,
            )

            self._circuit_breaker.record_success()

            return LLMResponse(
                content=response["message"]["content"],
                model=self.model,
                usage={"tokens": response.get("eval_count", 0)},
                finish_reason="stop" if response.get("done", True) else "length",
                raw_response=response
            )

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Ollama chat failed: {e}")
            raise ProviderException(f"Failed to communicate with Ollama: {e}")

    @with_retry(strategy=RetryStrategy(max_attempts=3, base_delay=2.0), circuit_breaker=None)
    def generate(
        self,
        prompt: str,
        options: Optional[CompletionOptions] = None
    ) -> LLMResponse:
        """Generate text from prompt."""
        if not self.is_available():
            raise ProviderNotAvailableError("Ollama is not available.")

        try:
            completion_options = options or CompletionOptions(
                temperature=self.temperature,
                top_p=self.top_p
            )

            request_options = {
                "temperature": completion_options.temperature,
                "num_gpu": -1,
            }

            if completion_options.max_tokens:
                request_options["num_predict"] = completion_options.max_tokens

            if completion_options.stop:
                request_options["stop"] = completion_options.stop

            logger.debug(f"Sending generate request to Ollama")

            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options=request_options
            )

            self._circuit_breaker.record_success()

            return LLMResponse(
                content=response["response"],
                model=self.model,
                usage={"tokens": response.get("eval_count", 0)},
                finish_reason="stop" if response.get("done", True) else "length",
                raw_response=response
            )

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Ollama generate failed: {e}")
            raise ProviderException(f"Generation failed: {e}")

    def get_provider_type(self) -> ProviderType:
        return ProviderType.OLLAMA

    def list_models(self) -> List[Dict]:
        """List available models."""
        if not self.is_available():
            return []

        try:
            response = self._client.list()
            return response.get("models", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []