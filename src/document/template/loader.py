"""
Template Loader Module
======================
Loads and manages DOCX templates.
"""

import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from docx import Document

from src.core.logger import get_logger
from src.core.exceptions import TemplateLoadError
from src.core.config import get_config

logger = get_logger(__name__)


class TemplateLoader:
    """Loads DOCX templates for document generation."""

    def __init__(self, template_dir: str = None):
        config = get_config()
        self.template_dir = Path(template_dir or config.template.directory)
        self._templates: Dict[str, str] = {}
        self._discover_templates()

    def _discover_templates(self):
        """Discover available templates."""
        if not self.template_dir.exists():
            logger.warning(f"Template directory not found: {self.template_dir}")
            return

        for template_file in self.template_dir.glob("*.docx"):
            self._templates[template_file.stem] = str(template_file)
            logger.debug(f"Found template: {template_file.name}")

        logger.info(f"Discovered {len(self._templates)} templates")

    def load(self, name: str) -> Document:
        """Load a template by name."""
        template_path = self._templates.get(name)

        if not template_path:
            available = ", ".join(self._templates.keys()) if self._templates else "none"
            raise TemplateLoadError(
                f"Template '{name}' not found. Available: {available}"
            )

        try:
            doc = Document(template_path)
            logger.info(f"Loaded template: {name}")
            return doc
        except Exception as e:
            raise TemplateLoadError(f"Failed to load template '{name}': {e}")

    def load_from_path(self, path: str) -> Document:
        """Load a template from a specific path."""
        if not os.path.exists(path):
            raise TemplateLoadError(f"Template file not found: {path}")

        try:
            doc = Document(path)
            logger.info(f"Loaded template from: {path}")
            return doc
        except Exception as e:
            raise TemplateLoadError(f"Failed to load template: {e}")

    def list_templates(self) -> List[Dict[str, str]]:
        """List all available templates."""
        return [
            {"name": name, "path": path}
            for name, path in self._templates.items()
        ]

    def get_template_path(self, name: str) -> Optional[str]:
        """Get the path for a template by name."""
        return self._templates.get(name)

    def exists(self, name: str) -> bool:
        """Check if a template exists."""
        return name in self._templates

    def reload(self):
        """Reload templates from disk."""
        self._templates.clear()
        self._discover_templates()


def load_template(name: str) -> Document:
    """Convenience function to load a template."""
    loader = TemplateLoader()
    return loader.load(name)


def load_template_from_path(path: str) -> Document:
    """Convenience function to load a template from path."""
    loader = TemplateLoader()
    return loader.load_from_path(path)