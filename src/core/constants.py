"""
Constants Module
================
Shared constants and default values for the framework.
"""

from pathlib import Path
from enum import Enum


DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_SKILLS_DIR = "skills"
DEFAULT_TEMPLATES_DIR = "config/templates"
OUTPUT_DOCX = "output.docx"
OUTPUT_PDF = "output.pdf"

MAX_CONTENT_LENGTH = 50000
MAX_RETRIES = 3
TIMEOUT_SECONDS = 120
CACHE_TTL_SECONDS = 3600

DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9

LOG_DIR = "logs"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5


class ExecutionMode(Enum):
    SCRATCH = "scratch"
    TEMPLATE = "template"
    APPEND = "append"
    HYBRID = "hybrid"


class DocumentFormat(Enum):
    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"


class SkillMatchThreshold:
    HIGH = 2.0
    MEDIUM = 1.0
    LOW = 0.5
    DEFAULT = 0.5


DEFAULT_PAGE_MARGIN = 1440
DEFAULT_FONT_NAME = "Calibri"
DEFAULT_FONT_SIZE = 12

SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "gif", "bmp", "svg"]