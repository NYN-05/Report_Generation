"""
Document Module
==============
Document generation and manipulation.
"""

from .docx_v2_generator import DOCXV2Generator
from .base import BaseDocument, DocumentMetadata
from .builder import DocumentBuilder
from .parser import DocumentParser
from .styles.analyzer import StyleAnalyzer
from .styles.extractor import StyleExtractor
from .styles.manager import StyleManager
from .template.loader import TemplateLoader
from .template.analyzer import TemplateAnalyzer
from .template.placeholder import PlaceholderHandler
from .content.manager import ContentManager
from .formatter.font import FontFormatter
from .formatter.paragraph import ParagraphFormatter
from .formatter.table import TableFormatter
from .structure import (
    build_tree, DocumentNode, SectionNode, ParagraphNode, NodeType,
    SectionLocator,
    ReplaceSection, InsertSection, ExpandSection, DeleteSection, MoveSection,
    EditingPlanner,
)
from .blueprint import (
    Blueprint, BlueprintSection, ReportPlan, PlanSection,
    BlueprintLoader, BlueprintSelector, AIReportPlanner,
    BlueprintBuilder, BlueprintValidator,
)
from .rules import (
    ReportRules, SectionRule, GlobalRules, RuleValidationResult,
    RulesLoader, RulesEngine,
)

__all__ = [
    "DOCXV2Generator",
    "BaseDocument",
    "DocumentMetadata",
    "DocumentBuilder",
    "DocumentParser",
    "StyleAnalyzer",
    "StyleExtractor",
    "StyleManager",
    "TemplateLoader",
    "TemplateAnalyzer",
    "PlaceholderHandler",
    "ContentManager",
    "FontFormatter",
    "ParagraphFormatter",
    "TableFormatter",
    "build_tree", "DocumentNode", "SectionNode", "ParagraphNode", "NodeType",
    "SectionLocator",
    "ReplaceSection", "InsertSection", "ExpandSection", "DeleteSection", "MoveSection",
    "EditingPlanner",
    "Blueprint", "BlueprintSection", "ReportPlan", "PlanSection",
    "BlueprintLoader", "BlueprintSelector", "AIReportPlanner",
    "BlueprintBuilder", "BlueprintValidator",
    "ReportRules", "SectionRule", "GlobalRules", "RuleValidationResult",
    "RulesLoader", "RulesEngine",
]