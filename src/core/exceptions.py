"""
Exceptions Module
=================
Custom exception hierarchy for the report generation framework.
"""


class ReportGenException(Exception):
    """Base exception for all report generation errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": self.__class__.__name__, "message": self.message, "details": self.details}


class SkillException(ReportGenException):
    """Base exception for skill-related errors."""

    pass


class SkillNotFoundError(SkillException):
    """Raised when a requested skill is not found."""

    pass


class SkillLoadError(SkillException):
    """Raised when a skill fails to load."""

    pass


class SkillExecutionError(SkillException):
    """Raised when skill execution fails."""

    pass


class AgentException(ReportGenException):
    """Base exception for agent errors."""

    pass


class TaskParsingError(AgentException):
    """Raised when task parsing fails."""

    pass


class ContentGenerationError(AgentException):
    """Raised when content generation fails."""

    pass


class PipelineException(ReportGenException):
    """Base exception for pipeline errors."""

    pass


class PipelineNotFoundError(PipelineException):
    """Raised when a pipeline is not found."""

    pass


class PipelineExecutionError(PipelineException):
    """Raised when pipeline execution fails."""

    pass


class ProviderException(ReportGenException):
    """Base exception for LLM provider errors."""

    pass


class ProviderNotAvailableError(ProviderException):
    """Raised when provider is not available."""

    pass


class ProviderTimeoutError(ProviderException):
    """Raised when provider request times out."""

    pass


class ProviderRateLimitError(ProviderException):
    """Raised when provider rate limit is exceeded."""

    pass


class DocumentException(ReportGenException):
    """Base exception for document-related errors."""

    pass


class TemplateLoadError(DocumentException):
    """Raised when template loading fails."""

    pass


class StyleExtractionError(DocumentException):
    """Raised when style extraction fails."""

    pass


class DocumentSaveError(DocumentException):
    """Raised when document save fails."""

    pass


class DocumentParseError(DocumentException):
    """Raised when document parsing fails."""

    pass


class PlaceholderError(DocumentException):
    """Raised when placeholder handling fails."""

    pass


class ValidationException(ReportGenException):
    """Base exception for validation errors."""

    pass


class SchemaValidationError(ValidationException):
    """Raised when schema validation fails."""

    pass


class ContentValidationError(ValidationException):
    """Raised when content validation fails."""

    pass


class ConfigurationException(ReportGenException):
    """Base exception for configuration errors."""

    pass


class ConfigNotFoundError(ConfigurationException):
    """Raised when configuration is not found."""

    pass


class ConfigValidationError(ConfigurationException):
    """Raised when configuration validation fails."""

    pass


class MemoryException(ReportGenException):
    """Base exception for memory/context errors."""

    pass


class ContextError(MemoryException):
    """Raised when context operations fail."""

    pass


class ExportException(ReportGenException):
    """Base exception for export errors."""

    pass


class ExportNotAvailableError(ExportException):
    """Raised when export method is not available."""

    pass


def format_exception_chain(exc: Exception) -> str:
    """Format exception with full chain."""
    lines = []
    current = exc
    while current:
        if hasattr(current, "message"):
            lines.append(f"{current.__class__.__name__}: {current.message}")
        else:
            lines.append(f"{current.__class__.__name__}: {str(current)}")
        current = getattr(current, "__cause__", None)
    return " -> ".join(lines)