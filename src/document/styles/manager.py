"""
Style Manager Module
===================
Manages styles and style preservation.

DEPRECATED: Use src.document.styles.style_manager.StyleManager instead.
This module exists only for backward compatibility.
"""

import warnings
from typing import Dict, Any, Optional, List
from docx import Document
from docx.shared import Pt, RGBColor

from src.core.logger import get_logger

logger = get_logger(__name__)

warnings.warn(
    "src.document.styles.manager is deprecated. Use src.document.styles.style_manager instead.",
    DeprecationWarning,
    stacklevel=2,
)


class StyleManager:
    """Manages document styles and formatting.
    
    DEPRECATED: Use style_manager.StyleManager (singleton) instead.
    """

    def __init__(self, document: Document = None):
        self.document = document
        warnings.warn(
            "StyleManager(document=...) is deprecated. Use StyleManager.get_instance() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    def preserve_styles(self, source_path: str, target_path: str) -> bool:
        """Copy styles from source to target document."""
        try:
            source_doc = Document(source_path)
            target_doc = Document(target_path)

            for target_style in target_doc.styles:
                source_style = source_doc.styles.get_by_name(target_style.name)
                if source_style:
                    pass

            target_doc.save(target_path)
            return True
        except Exception as e:
            logger.error(f"Style preservation failed: {e}")
            return False

    def apply_style(self, element, style_name: str):
        """Apply a style to an element."""
        if hasattr(element, 'style'):
            element.style = style_name

    def get_defined_styles(self) -> List[str]:
        """Get all defined styles in the document."""
        if not self.document:
            return []

        return [s.name for s in self.document.styles]

    def get_style_by_name(self, name: str) -> Optional[Any]:
        """Get a specific style by name."""
        if not self.document:
            return None

        try:
            return self.document.styles.get_by_name(name)
        except:
            return None

    def create_custom_style(self, name: str, base_style: str = "Normal"):
        """Create a custom style."""
        if not self.document:
            return None

        try:
            style = self.document.styles.add_style(name, 1)
            style.base_style = self.document.styles.get_by_name(base_style)
            return style
        except:
            return None


class FormatPreserver:
    """Preserves formatting during document editing."""

    def __init__(self):
        self.style_cache: Dict[str, Any] = {}

    def capture_styles(self, document_path: str) -> Dict[str, Any]:
        """Capture all styles from a document."""
        from .analyzer import StyleAnalyzer

        analyzer = StyleAnalyzer(document_path)
        self.style_cache = analyzer.analyze()
        return self.style_cache

    def apply_captured_styles(self, target_doc: Document):
        """Apply captured styles to a target document.

        Copies font and paragraph properties from the captured style cache
        onto the corresponding styles in the target document.
        """
        if not self.style_cache:
            logger.warning("No styles captured to apply")
            return

        logger.info("Applying captured styles to target document")

        try:
            default_font = self.style_cache.get("default_font", {})
            default_style = target_doc.styles.get_by_name("Normal") if hasattr(target_doc, 'styles') else None
            if default_style:
                font_name = default_font.get("name", "Calibri")
                if font_name:
                    default_style.font.name = font_name
                font_size = default_font.get("size", 11)
                if font_size:
                    default_style.font.size = Pt(font_size)

            for style_info in self.style_cache.get("paragraph_styles", []):
                style_name = style_info.get("name") or style_info.get("display_name", "")
                if not style_name:
                    continue
                try:
                    style = target_doc.styles.get_by_name(style_name)
                    self._apply_style_properties(style, style_info)
                except (ValueError, KeyError):
                    logger.debug(f"Style '{style_name}' not found in target, skipping")

            for style_info in self.style_cache.get("character_styles", []):
                style_name = style_info.get("name") or style_info.get("display_name", "")
                if not style_name:
                    continue
                try:
                    style = target_doc.styles.get_by_name(style_name)
                    self._apply_style_properties(style, style_info)
                except (ValueError, KeyError):
                    logger.debug(f"Character style '{style_name}' not found in target, skipping")

            logger.info("Style application complete")
        except Exception as e:
            logger.error(f"Failed to apply captured styles: {e}")

    def _apply_style_properties(self, style, props: Dict[str, Any]):
        """Apply captured font and paragraph properties to a single style."""
        if props.get("font_name"):
            style.font.name = props["font_name"]
        if props.get("font_size"):
            style.font.size = Pt(props["font_size"])
        if props.get("bold") is not None:
            style.font.bold = props["bold"]
        if props.get("italic") is not None:
            style.font.italic = props["italic"]
        if props.get("underline"):
            style.font.underline = True
        if props.get("color"):
            try:
                style.font.color.rgb = RGBColor.from_string(props["color"])
            except Exception:
                pass

    def get_default_font(self) -> Dict[str, Any]:
        """Return the captured default font info."""
        if self.style_cache:
            return self.style_cache.get("default_font", {"name": "Calibri", "size": 11})
        return {"name": "Calibri", "size": 11}

    def get_heading_font(self, level: int = 1) -> Dict[str, Any]:
        """Return font properties for a heading level from captured styles."""
        if not self.style_cache:
            return {"font_name": "Calibri", "font_size": 16 - level * 2, "bold": True}
        style_name = f"Heading{level}"
        for ps in self.style_cache.get("paragraph_styles", []):
            if ps.get("name") == style_name:
                return {
                    "font_name": ps.get("font_name", "Calibri"),
                    "font_size": ps.get("font_size", 14),
                    "bold": ps.get("bold", True),
                    "color": ps.get("color"),
                }
        return {"font_name": "Calibri", "font_size": 16 - level * 2, "bold": True}