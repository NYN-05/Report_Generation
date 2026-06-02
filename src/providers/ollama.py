"""
Ollama Provider Module
======================
Ollama LLM provider implementation.
"""

import hashlib
import urllib.request
import urllib.error
import json
import time
import os
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
        self.host = host.rstrip('/')  # Remove trailing slash if present
        self._client = None
        self._import_error: Optional[str] = None
        self._retry_strategy = RetryStrategy(max_attempts=3, base_delay=1.0)
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)
        # Health check caching
        self._health_check_cache = None
        self._health_check_timestamp = 0
        self._health_check_ttl = 30  # 30 seconds cache TTL
        # Response caching
        self._cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'cache', 'llm')
        os.makedirs(self._cache_dir, exist_ok=True)
        self._initialize_client()
        self._availability_cache: Optional[bool] = None
        self._availability_cache_time: float = 0
        self._availability_cache_ttl: float = 10.0

    def _initialize_client(self):
        """Initialize the Ollama client."""
        try:
            import ollama
            self._client = ollama
            logger.debug(f"Initialized Ollama client for model {self.model}")
        except ImportError as e:
            self._import_error = str(e)
            logger.warning(f"Ollama not available: {e}")

    def _get_cache_key(self, prompt: str, options: Dict) -> str:
        """Generate a cache key for the given prompt and options."""
        # Create a string representation of the prompt and options
        key_data = {
            'prompt': prompt,
            'options': options,
            'model': self.model,
            'host': self.host
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[LLMResponse]:
        """Retrieve a cached response if it exists and is not expired."""
        cache_file = os.path.join(self._cache_dir, f"{cache_key}.json")
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            
            # Check if cache is expired (default 1 hour)
            cache_time = cached_data.get('timestamp', 0)
            if time.time() - cache_time > 3600:  # 1 hour TTL
                # Remove expired cache file
                os.remove(cache_file)
                return None
            
            # Reconstruct LLMResponse from cached data
            return LLMResponse(
                content=cached_data['content'],
                model=cached_data['model'],
                usage=cached_data.get('usage', {}),
                finish_reason=cached_data.get('finish_reason', 'stop'),
                raw_response=cached_data.get('raw_response')
            )
        except Exception as e:
            logger.debug(f"Failed to load cache: {e}")
            # Remove corrupted cache file
            try:
                os.remove(cache_file)
            except:
                pass
            return None

    def _save_to_cache(self, cache_key: str, response: LLMResponse) -> None:
        """Save a response to cache."""
        cache_file = os.path.join(self._cache_dir, f"{cache_key}.json")
        try:
            cache_data = {
                'content': response.content,
                'model': response.model,
                'usage': response.usage,
                'finish_reason': response.finish_reason,
                'raw_response': response.raw_response,
                'timestamp': time.time()
            }
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.debug(f"Failed to save to cache: {e}")

    def is_available(self) -> bool:
        """Check if Ollama is available using lightweight HTTP health check with caching."""
        # Check if we have a cached health check that's still valid
        current_time = time.time()
        if (self._health_check_cache is not None and 
            current_time - self._health_check_timestamp < self._health_check_ttl):
            return self._health_check_cache

        if self._import_error:
            logger.debug(f"Ollama not available: {self._import_error}")
            self._health_check_cache = False
            self._health_check_timestamp = current_time
            return False

        if not self._circuit_breaker.can_attempt():
            logger.warning("Circuit breaker is open, Ollama not available")
            self._health_check_cache = False
            self._health_check_timestamp = current_time
            return False

        try:
            # Use lightweight HTTP health check instead of model inference
            url = f"{self.host}/api/tags"
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req, timeout=5.0)  # 5 second timeout
            
            if response.getcode() == 200:
                # Successfully connected to Ollama API
                self._health_check_cache = True
                self._health_check_timestamp = current_time
                self._circuit_breaker.record_success()
                logger.debug("Ollama health check passed (cached)")
                return True
            else:
                # Unexpected HTTP status
                self._health_check_cache = False
                self._health_check_timestamp = current_time
                self._circuit_breaker.record_failure()
                logger.debug(f"Ollama health check failed with status: {response.getcode()}")
                return False
                
        except urllib.error.URLError as e:
            # Connection failed (Ollama not running, network issue, etc.)
            self._health_check_cache = False
            self._health_check_timestamp = current_time
            self._circuit_breaker.record_failure()
            logger.debug(f"Ollama health check failed (connection error): {e}")
            return False
        except Exception as e:
            # Other unexpected errors
            self._health_check_cache = False
            self._health_check_timestamp = current_time
            self._circuit_breaker.record_failure()
            logger.debug(f"Ollama health check failed (unexpected error): {e}")
            return False

    @with_retry(strategy=RetryStrategy(max_attempts=3, base_delay=2.0), circuit_breaker=None)
    def chat(
        self,
        messages: List[Message],
        options: Optional[CompletionOptions] = None
    ) -> LLMResponse:
        """Send chat request to Ollama with caching."""
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

            # Check cache first
            cache_key = self._get_cache_key(
                json.dumps(msg_dicts, sort_keys=True),
                request_options
            )
            cached_response = self._get_cached_response(cache_key)
            if cached_response is not None:
                logger.debug(f"Returning cached chat response for {len(messages)} messages")
                return cached_response

            logger.debug(f"Sending chat request to Ollama: {len(messages)} messages")

            response = self._client.chat(
                model=self.model,
                messages=msg_dicts,
                options=request_options,
            )

            llm_response = LLMResponse(
                content=response["message"]["content"],
                model=self.model,
                usage={"tokens": response.get("eval_count", 0)},
                finish_reason="stop" if response.get("done", True) else "length",
                raw_response=response
            )

            # Save to cache
            self._save_to_cache(cache_key, llm_response)

            self._circuit_breaker.record_success()

            return llm_response

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
        """Generate text from prompt with caching."""
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

            # Check cache first
            cache_key = self._get_cache_key(prompt, request_options)
            cached_response = self._get_cached_response(cache_key)
            if cached_response is not None:
                logger.debug("Returning cached generate response")
                return cached_response

            logger.debug(f"Sending generate request to Ollama")

            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options=request_options
            )

            llm_response = LLMResponse(
                content=response["response"],
                model=self.model,
                usage={"tokens": response.get("eval_count", 0)},
                finish_reason="stop" if response.get("done", True) else "length",
                raw_response=response
            )

            # Save to cache
            self._save_to_cache(cache_key, llm_response)

            self._circuit_breaker.record_success()

            return llm_response

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