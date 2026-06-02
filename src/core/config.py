"""
Config Module
=============
Configuration management with environment support.
"""

import os
import yaml
import platform
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from .logger import get_logger
from .constants import DEFAULT_MODEL, DEFAULT_SKILLS_DIR, DEFAULT_TEMPLATES_DIR

_MAX_YAML_SIZE = 10 * 1024 * 1024  # 10MB max config file

logger = get_logger(__name__)


def _load_dotenv(dotenv_path: Optional[str] = None):
    """Load .env file into os.environ without requiring python-dotenv."""
    path = Path(dotenv_path or ".env")
    if not path.exists():
        alt = Path(__file__).parent.parent.parent / ".env"
        if alt.exists():
            path = alt
        else:
            return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = val
        logger.info(f"Loaded environment from {path}")
    except Exception as e:
        logger.debug(f".env load skipped: {e}")


_load_dotenv()


@dataclass
class ProviderConfig:
    """LLM provider configuration."""
    max_concurrent_sections: int = 4
    name: str = "ollama"
    model: str = DEFAULT_MODEL
    host: str = "http://localhost:11434"
    temperature: float = 0.7
    top_p: float = 0.9
    timeout: int = 120
    max_retries: int = 3


@dataclass
class SkillsConfig:
    """Skills configuration."""
    directory: str = DEFAULT_SKILLS_DIR
    auto_discover: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 3600


@dataclass
class TemplateConfig:
    """Template configuration."""
    directory: str = DEFAULT_TEMPLATES_DIR
    default_styles_preserved: bool = True
    auto_placeholder_detection: bool = True


@dataclass
class ExportConfig:
    """Export configuration."""
    pdf_method: str = "auto"
    output_directory: str = "output"
    preserve_formatting: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    directory: str = "logs"
    max_file_size: int = 10 * 1024 * 1024
    backup_count: int = 5


@dataclass
class SearchConfig:
    """Web search configuration."""
    enabled: bool = False
    provider: str = "tavily"
    api_key: str = ""
    api_url: str = "https://api.tavily.com/search"
    max_results: int = 5
    results_per_section: int = 3


@dataclass
class SystemConfig:
    """System configuration."""
    check_dependencies: bool = True
    gpu_detection: bool = True
    context_persistence: bool = False
    response_cache: bool = True


@dataclass
class AppConfig:
    """Main application configuration."""
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    template: TemplateConfig = field(default_factory=TemplateConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    search: SearchConfig = field(default_factory=SearchConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.__dict__,
            "skills": self.skills.__dict__,
            "template": self.template.__dict__,
            "export": self.export.__dict__,
            "logging": self.logging.__dict__,
            "system": self.system.__dict__,
            "search": self.search.__dict__,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        return cls(
            provider=ProviderConfig(**data.get("provider", {})),
            skills=SkillsConfig(**data.get("skills", {})),
            template=TemplateConfig(**data.get("template", {})),
            export=ExportConfig(**data.get("export", {})),
            logging=LoggingConfig(**data.get("logging", {})),
            system=SystemConfig(**data.get("system", {})),
            search=SearchConfig(**data.get("search", {})),
        )


class ConfigManager:
    """Configuration manager with environment support."""

    _config: Optional[AppConfig] = None
    _config_path: Optional[Path] = None

    @classmethod
    def load(cls, config_path: str = None) -> AppConfig:
        """Load configuration from file or defaults."""
        if cls._config is not None:
            return cls._config

        if config_path is None:
            config_path = os.environ.get("REPORT_GEN_CONFIG", "config/default.yaml")

        cls._config_path = Path(config_path)

        if cls._config_path.exists():
            try:
                size = cls._config_path.stat().st_size
                if size > _MAX_YAML_SIZE:
                    raise ValueError(f"Config file too large: {size} bytes (max {_MAX_YAML_SIZE})")
                raw = cls._config_path.read_text(encoding="utf-8")
                data = yaml.load(raw, Loader=yaml.SafeLoader)
                cls._config = AppConfig.from_dict(data)
                logger.info(f"Loaded configuration from {cls._config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
                cls._config = cls._create_default_config()
        else:
            cls._config = cls._create_default_config()
            logger.info("Using default configuration")

        cls._setup_from_environment()
        return cls._config

    @classmethod
    def _create_default_config(cls) -> AppConfig:
        """Create default configuration."""
        return AppConfig()

    @classmethod
    def _setup_from_environment(cls):
        """Override config from environment variables."""
        if cls._config is None:
            return

        if model := os.environ.get("LLM_MODEL"):
            cls._config.provider.model = model
        if host := os.environ.get("OLLAMA_HOST"):
            cls._config.provider.host = host
        if skills_dir := os.environ.get("SKILLS_DIR"):
            cls._config.skills.directory = skills_dir
        if api_key := os.environ.get("TAVILY_API_KEY"):
            cls._config.search.api_key = api_key
            cls._config.search.enabled = True
        if api_url := os.environ.get("SEARCH_API_URL"):
            cls._config.search.api_url = api_url

    @classmethod
    def get(cls) -> AppConfig:
        """Get current configuration."""
        if cls._config is None:
            return cls.load()
        return cls._config

    @classmethod
    def reload(cls, config_path: str = None) -> AppConfig:
        """Reload configuration."""
        cls._config = None
        return cls.load(config_path)

    @classmethod
    def save(cls, config_path: str = None):
        """Save current configuration to file."""
        if cls._config is None:
            return

        if config_path is None:
            config_path = cls._config_path or "config/default.yaml"

        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(cls._config.to_dict(), default_flow_style=False), encoding="utf-8")
        logger.info(f"Saved configuration to {path}")


def get_config() -> AppConfig:
    """Convenience function to get config."""
    return ConfigManager.get()


def reload_config(config_path: str = None) -> AppConfig:
    """Convenience function to reload config."""
    return ConfigManager.reload(config_path)


def check_dependencies() -> Dict[str, bool]:
    """Check and report availability of optional dependencies."""
    deps = {}

    try:
        import ollama
        deps["ollama"] = True
    except ImportError:
        deps["ollama"] = False

    try:
        import docx2pdf
        deps["docx2pdf"] = True
    except ImportError:
        deps["docx2pdf"] = False

    try:
        from docx import Document
        deps["python-docx"] = True
    except ImportError:
        deps["python-docx"] = False

    try:
        import win32com.client
        deps["win32com"] = True
    except ImportError:
        deps["win32com"] = False

    return deps