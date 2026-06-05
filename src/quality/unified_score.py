from typing import Dict, List, Optional, Any
from collections import Counter
from src.core.logger import get_logger
from src.facts.models import Fact
from src.quality.fidelity import evidence_fidelity, hallucination_risk

logger = get_logger(__name__)


def compute_pre_generation_score(facts: List[Fact]) -> float:
    if not facts:
        return 0.0

    type_counts = Counter(f.fact_type for f in facts if f.fact_type)
    type_diversity = min(len(type_counts) / 3.0, 1.0)

    avg_confidence = sum(f.confidence for f in facts) / len(facts)

    unique_sources = len(set(
        f.source.file_name for f in facts
        if f.source and f.source.file_name
    ))
    source_diversity = min(unique_sources / 2.0, 1.0)

    verified_ratio = sum(1 for f in facts if f.is_verified) / len(facts)

    fact_sufficiency = min(len(facts) / 8.0, 1.0)

    score = (
        type_diversity * 0.25 +
        avg_confidence * 0.25 +
        source_diversity * 0.20 +
        verified_ratio * 0.20 +
        fact_sufficiency * 0.10
    )
    return round(min(1.0, max(0.0, score)), 3)


def compute_post_generation_score(section_text: str, facts: List[Fact]) -> Dict:
    if not section_text or not facts:
        return {
            "unified_score": 0.0,
            "evidence_fidelity": 0.0,
            "hallucination_risk": 1.0,
            "traceability": 0.0,
            "components": {},
        }

    fid = evidence_fidelity(section_text, facts)
    hal = hallucination_risk(section_text, facts)

    paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
    total = len(paragraphs)
    traced = fid["traced_paragraphs"]
    traceability = traced / max(total, 1)

    pre_score = compute_pre_generation_score(facts)
    fidelity_score = fid["fidelity"]
    risk_inverted = 1.0 - hal["risk"]

    combined = round(
        pre_score * 0.30 +
        fidelity_score * 0.30 +
        traceability * 0.25 +
        risk_inverted * 0.15,
        3,
    )

    return {
        "unified_score": combined,
        "pre_generation_score": pre_score,
        "evidence_fidelity": fidelity_score,
        "hallucination_risk": hal["risk"],
        "traceability": round(traceability, 3),
        "components": {
            "traceability": round(traceability, 3),
            "fidelity": fidelity_score,
            "risk_inverted": round(risk_inverted, 3),
            "pre_score": pre_score,
        },
        "raw": {
            "traced_paragraphs": traced,
            "total_paragraphs": total,
            "unsupported_claims": hal["unsupported_claims"],
            "total_claims": hal["total_claims"],
            "sources_used": fid["sources_used"],
        },
    }
