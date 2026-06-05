from typing import Dict, List, Optional
from src.core.logger import get_logger
from src.facts.models import Fact

logger = get_logger(__name__)


def evidence_fidelity(section_text: str, facts: List[Fact]) -> Dict:
    paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
    if not paragraphs or not facts:
        return {"fidelity": 0.0, "traced_paragraphs": 0, "total_paragraphs": len(paragraphs), "sources_used": []}

    traced = 0
    sources_used = set()
    for para in paragraphs:
        text_lower = para.lower()
        for f in facts:
            if f.normalized_value[:40] in text_lower:
                traced += 1
                sources_used.add(f.source.file_name)
                break

    return {
        "fidelity": round(traced / len(paragraphs), 3),
        "traced_paragraphs": traced,
        "total_paragraphs": len(paragraphs),
        "sources_used": list(sources_used),
    }


def hallucination_risk(section_text: str, facts: List[Fact]) -> Dict:
    import re
    paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
    if not paragraphs:
        return {"risk": 0.0, "unsupported_claims": 0, "total_claims": 0}

    metrics_pattern = re.compile(
        r"(?:accuracy|precision|recall|f1[-\s]?score|AUC|BLEU|ROUGE|perplexity)"
        r"\s+(?:of|:|=|reached|achieved)\s+\d+\.?\d*\%?"
    )
    datasets_pattern = re.compile(
        r"\b(?:using|on|with)\s+(?:the\s+)?([A-Z][a-zA-Z0-9_-]{2,})\s*(?:dataset|corpus|benchmark)"
    )

    unsupported = 0
    total_claims = 0
    fact_texts = [f.normalized_value[:40] for f in facts]

    for para in paragraphs:
        text_lower = para.lower()
        for match in metrics_pattern.finditer(para):
            total_claims += 1
            if not any(ft in text_lower for ft in fact_texts):
                unsupported += 1
        for match in datasets_pattern.finditer(para):
            total_claims += 1
            if not any(ft in text_lower for ft in fact_texts):
                unsupported += 1
        if "Insufficient source material" in para:
            unsupported += 1

    risk = min(1.0, unsupported / max(total_claims, 1)) if total_claims > 0 else 0.0
    return {"risk": round(risk, 3), "unsupported_claims": unsupported, "total_claims": total_claims}
