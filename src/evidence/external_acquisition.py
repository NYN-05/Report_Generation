from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from src.core.logger import get_logger
from src.facts.models import Fact, FactType, SourceReference
from src.facts.store import FactStore
from src.retrieval.web import search_web

logger = get_logger(__name__)


class SourceTier(Enum):
    USER_RESOURCES = 1
    RESEARCH_PAPERS = 2
    OFFICIAL_DOCS = 3
    WIKIPEDIA = 4
    GENERAL_WEB = 5


TIER_WEIGHTS = {
    SourceTier.USER_RESOURCES: 1.0,
    SourceTier.RESEARCH_PAPERS: 0.85,
    SourceTier.OFFICIAL_DOCS: 0.75,
    SourceTier.WIKIPEDIA: 0.5,
    SourceTier.GENERAL_WEB: 0.35,
}

TIER_NAMES = {
    SourceTier.USER_RESOURCES: "User Resources",
    SourceTier.RESEARCH_PAPERS: "Research Papers",
    SourceTier.OFFICIAL_DOCS: "Official Documentation",
    SourceTier.WIKIPEDIA: "Wikipedia",
    SourceTier.GENERAL_WEB: "General Web",
}

TIER_REQUIRES_VERIFICATION = {SourceTier.WIKIPEDIA, SourceTier.GENERAL_WEB}


FACT_TYPE_TIER_MAP: Dict[FactType, List[SourceTier]] = {
    FactType.OBJECTIVE: [SourceTier.USER_RESOURCES, SourceTier.OFFICIAL_DOCS, SourceTier.WIKIPEDIA],
    FactType.DATASET: [SourceTier.USER_RESOURCES, SourceTier.RESEARCH_PAPERS, SourceTier.WIKIPEDIA, SourceTier.GENERAL_WEB],
    FactType.ALGORITHM: [SourceTier.USER_RESOURCES, SourceTier.RESEARCH_PAPERS, SourceTier.OFFICIAL_DOCS, SourceTier.WIKIPEDIA, SourceTier.GENERAL_WEB],
    FactType.METRIC: [SourceTier.USER_RESOURCES, SourceTier.RESEARCH_PAPERS, SourceTier.WIKIPEDIA, SourceTier.GENERAL_WEB],
    FactType.RESULT: [SourceTier.USER_RESOURCES, SourceTier.RESEARCH_PAPERS, SourceTier.GENERAL_WEB],
    FactType.TECHNOLOGY: [SourceTier.USER_RESOURCES, SourceTier.OFFICIAL_DOCS, SourceTier.WIKIPEDIA, SourceTier.GENERAL_WEB],
    FactType.ARCHITECTURE: [SourceTier.USER_RESOURCES, SourceTier.RESEARCH_PAPERS, SourceTier.OFFICIAL_DOCS, SourceTier.WIKIPEDIA],
    FactType.CITATION: [SourceTier.USER_RESOURCES, SourceTier.RESEARCH_PAPERS],
    FactType.REQUIREMENT: [SourceTier.USER_RESOURCES, SourceTier.OFFICIAL_DOCS],
    FactType.METHODOLOGY: [SourceTier.USER_RESOURCES, SourceTier.RESEARCH_PAPERS, SourceTier.OFFICIAL_DOCS, SourceTier.WIKIPEDIA],
    FactType.GENERAL: [SourceTier.GENERAL_WEB],
}


DOMAIN_QUERY_TEMPLATES = {
    "image classification": [
        "{topic} image classification CNN architecture",
        "{topic} dataset benchmark accuracy",
        "{topic} PyTorch implementation",
    ],
    "natural language processing": [
        "{topic} NLP transformer BERT",
        "{topic} dataset metrics evaluation",
        "{topic} implementation code",
    ],
    "default": [
        "{topic} overview",
        "{topic} implementation guide",
        "{topic} technical documentation",
    ],
}


def _detect_domain(topic: str) -> str:
    t = topic.lower()
    if any(k in t for k in ["image", "cnn", "convolutional", "vision", "classification"]):
        return "image classification"
    if any(k in t for k in ["nlp", "language", "text", "bert", "transformer", "sentiment"]):
        return "natural language processing"
    return "default"


def _source_type_from_url(url: str) -> SourceTier:
    url_lower = url.lower()
    if "wikipedia.org" in url_lower:
        return SourceTier.WIKIPEDIA
    if any(d in url_lower for d in [".edu", "scholar.", "arxiv.org", "researchgate", "ieee", "acm.org", "springer"]):
        return SourceTier.RESEARCH_PAPERS
    if any(d in url_lower for d in [".org", "docs.", "github.com", ".gov", "microsoft.com", "google.com", "pytorch.org", "tensorflow.org"]):
        return SourceTier.OFFICIAL_DOCS
    return SourceTier.GENERAL_WEB


def _estimate_source_tier(source: str) -> SourceTier:
    if source.startswith("web:"):
        url_part = source[4:]
        return _source_type_from_url(url_part)
    if source.startswith("web:duckduckgo:"):
        url_part = source[14:]
        return _source_type_from_url(url_part)
    return SourceTier.GENERAL_WEB


@dataclass
class ExternalFact:
    value: str
    fact_type: FactType
    source_tier: SourceTier
    source_url: str
    source_name: str
    confidence: float
    retrieval_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    verification_count: int = 0
    verification_sources: List[str] = field(default_factory=list)
    is_verified: bool = False
    normalized_value: str = ""

    def __post_init__(self):
        if not self.normalized_value:
            self.normalized_value = self.value.lower().strip()


@dataclass
class VerifiedFact:
    external: ExternalFact
    supporting_sources: List[str] = field(default_factory=list)
    final_confidence: float = 0.0

    def to_fact(self, fact_id: str, source_ref: SourceReference) -> Fact:
        return Fact(
            fact_id=fact_id,
            fact_type=self.external.fact_type,
            value=self.external.value,
            normalized_value=self.external.normalized_value,
            confidence=self.final_confidence,
            source=source_ref,
            concepts=[self.external.fact_type.value],
            metadata={
                "source_tier": self.external.source_tier.value,
                "source_url": self.external.source_url,
                "source_tier_name": TIER_NAMES.get(self.external.source_tier, ""),
                "retrieval_timestamp": self.external.retrieval_timestamp,
                "verification_count": self.external.verification_count,
                "verification_sources": self.external.verification_sources,
                "is_verified": self.external.is_verified,
                "supporting_sources": self.supporting_sources,
            },
            is_active=True,
        )


class FactVotingSystem:
    def __init__(self, min_independent_sources: int = 2):
        self._min_sources = min_independent_sources
        self._votes: Dict[str, List[ExternalFact]] = {}

    def add_fact(self, fact: ExternalFact):
        key = fact.normalized_value[:100]
        if key not in self._votes:
            self._votes[key] = []
        existing_sources = {v.source_url for v in self._votes[key]}
        if fact.source_url not in existing_sources:
            self._votes[key].append(fact)

    def add_facts(self, facts: List[ExternalFact]):
        for f in facts:
            self.add_fact(f)

    def get_accepted(self) -> List[VerifiedFact]:
        accepted = []
        for key, votes in self._votes.items():
            independent_sources = set(v.source_url for v in votes)
            source_count = len(independent_sources)
            tiers = {v.source_tier for v in votes}
            is_high_tier = any(t.value <= 3 for t in tiers)

            if is_high_tier:
                needs = 1
            else:
                needs = self._min_sources

            if source_count >= needs:
                best = max(votes, key=lambda v: v.confidence)
                best.verification_count = source_count
                best.verification_sources = list(independent_sources)
                best.is_verified = source_count >= self._min_sources
                accepted.append(VerifiedFact(
                    external=best,
                    supporting_sources=list(independent_sources),
                    final_confidence=min(1.0, best.confidence * (1.0 + 0.1 * source_count)),
                ))
        return accepted

    def get_pending(self) -> List[ExternalFact]:
        pending = []
        for votes in self._votes.values():
            tiers = {v.source_tier for v in votes}
            if any(t.value <= 3 for t in tiers):
                continue
            independent_sources = set(v.source_url for v in votes)
            if len(independent_sources) < self._min_sources:
                pending.extend(votes)
        return pending

    def get_all_facts(self) -> List[ExternalFact]:
        result = []
        for votes in self._votes.values():
            result.extend(votes)
        return result


class EvidenceConfidenceScorer:
    def score_tier(self, tier: SourceTier) -> float:
        return TIER_WEIGHTS.get(tier, 0.3)

    def score_source_diversity(self, verification_count: int) -> float:
        return min(1.0, verification_count / 3.0)

    def score_recency(self, timestamp_str: str) -> float:
        try:
            ts = datetime.fromisoformat(timestamp_str)
            hours_ago = (datetime.now() - ts).total_seconds() / 3600
            if hours_ago < 1:
                return 1.0
            if hours_ago < 24:
                return 0.9
            if hours_ago < 168:
                return 0.7
            return max(0.3, 1.0 - hours_ago / 720.0)
        except Exception:
            return 0.5

    def score(self, verified: VerifiedFact) -> float:
        tier_score = self.score_tier(verified.external.source_tier)
        diversity_score = self.score_source_diversity(verified.external.verification_count)
        recency_score = self.score_recency(verified.external.retrieval_timestamp)
        final = tier_score * 0.4 + diversity_score * 0.4 + recency_score * 0.2
        return round(min(1.0, final), 3)


class ExternalAcquisitionPipeline:
    def __init__(self, fact_store: FactStore, provider=None,
                 coverage_threshold: float = 0.3,
                 min_voting_sources: int = 2):
        self._fact_store = fact_store
        self._provider = provider
        self._threshold = coverage_threshold
        self._voting = FactVotingSystem(min_independent_sources=min_voting_sources)
        self._scorer = EvidenceConfidenceScorer()
        self._acquisition_log: List[Dict] = []

    def check_coverage(self, blueprint: List) -> Tuple[bool, List[str]]:
        if not blueprint:
            return True, []
        low_coverage_sections = []
        for section in blueprint:
            if hasattr(section, "meets_threshold"):
                if not section.meets_threshold:
                    low_coverage_sections.append(section.section_type)
            else:
                facts = section.get("facts", [])
                req_types = section.get("required_types", [])
                if not req_types:
                    continue
                matched_types = set(f.fact_type.value if hasattr(f, 'fact_type') else "" for f in facts)
                coverage = len(matched_types & set(req_types)) / len(req_types)
                if coverage < self._threshold:
                    low_coverage_sections.append(section["section_type"])
        needs_acquisition = len(low_coverage_sections) > 0
        return needs_acquisition, low_coverage_sections

    def acquire(self, topic: str, blueprint: List[Dict],
                max_results_per_source: int = 3) -> int:
        needs_acq, low_coverage = self.check_coverage(blueprint)
        if not needs_acq:
            logger.info(f"Coverage sufficient ({self._threshold}) — skipping external acquisition")
            return 0

        logger.info(f"Coverage below threshold — acquiring external evidence for: {low_coverage}")
        domain = _detect_domain(topic)
        user_fact_sources = self._get_user_source_urls()
        queries = self._build_queries(topic, domain, low_coverage)

        all_external: List[ExternalFact] = []
        for query in queries:
            raw_results = search_web(query, max_results_per_source)
            for r in raw_results:
                ext = self._raw_to_external(r, query)
                if ext and ext.source_url not in user_fact_sources:
                    all_external.append(ext)

        self._voting.add_facts(all_external)
        accepted = self._voting.get_accepted()
        pending = self._voting.get_pending()

        added_count = 0
        for verified in accepted:
            confidence = self._scorer.score(verified)
            if verified.external.source_tier in TIER_REQUIRES_VERIFICATION and not verified.external.is_verified:
                logger.info(f"Skipping unverified Tier 4-5 fact: {verified.external.value[:60]}...")
                continue
            fact = self._external_to_store_fact(verified, topic, confidence)
            if self._fact_store.add_fact(fact):
                added_count += 1

        self._log_acquisition(topic, len(all_external), len(accepted),
                              len(pending), added_count, low_coverage)
        return added_count

    def get_acquisition_report(self) -> Dict:
        return {
            "acquisitions": list(self._acquisition_log),
            "total_acquisitions": len(self._acquisition_log),
            "pending_verification": [f.to_fact(
                f"pending_{i}",
                SourceReference(resource_id="pending", file_path="", file_name="web")
            ).to_dict() for i, f in enumerate(self._voting.get_pending())],
        }

    def _get_user_source_urls(self) -> Set[str]:
        sources = set()
        for fact in self._fact_store.get_all_facts():
            if fact.source.file_path:
                sources.add(fact.source.file_path)
            if fact.metadata.get("source_url"):
                sources.add(fact.metadata["source_url"])
        return sources

    def _build_queries(self, topic: str, domain: str,
                       low_coverage: List[str]) -> List[str]:
        templates = DOMAIN_QUERY_TEMPLATES.get(domain, DOMAIN_QUERY_TEMPLATES["default"])
        queries = []
        for t in templates[:2]:
            queries.append(t.format(topic=topic))
        for section_type in low_coverage:
            queries.append(f"{topic} {section_type.replace('_', ' ')}")
        return queries[:5]

    def _raw_to_external(self, raw: Dict, query: str) -> Optional[ExternalFact]:
        text = raw.get("text", "")
        if not text:
            return None
        content = text.split("\n", 1)[-1].strip() if "\n" in text else text
        if len(content) < 20:
            return None
        meta = raw.get("metadata", {})
        source_str = meta.get("source", "web:unknown")
        url = meta.get("url", "")
        score = meta.get("score", 0.5)
        tier = _estimate_source_tier(source_str)
        ft = self._classify_content(content, query)
        return ExternalFact(
            value=content[:500],
            fact_type=ft,
            source_tier=tier,
            source_url=url or source_str,
            source_name=meta.get("heading", "") or url or source_str,
            confidence=score * TIER_WEIGHTS.get(tier, 0.5),
        )

    def _classify_content(self, content: str, query: str) -> FactType:
        c = content.lower() + " " + query.lower()
        if any(k in c for k in ["objective", "goal", "aim", "purpose"]):
            return FactType.OBJECTIVE
        if any(k in c for k in ["dataset", "corpus", "data collection"]):
            return FactType.DATASET
        if any(k in c for k in ["algorithm", "method", "approach"]):
            return FactType.ALGORITHM
        if any(k in c for k in ["accuracy", "precision", "recall", "f1", "metric", "bleu", "score"]):
            return FactType.METRIC
        if any(k in c for k in ["result", "performance", "achieved", "outperform"]):
            return FactType.RESULT
        if any(k in c for k in ["architecture", "framework", "system design"]):
            return FactType.ARCHITECTURE
        if any(k in c for k in ["library", "framework", "pytorch", "tensorflow", "implementation"]):
            return FactType.TECHNOLOGY
        return FactType.GENERAL

    def _external_to_store_fact(self, verified: VerifiedFact,
                                 topic: str, confidence: float) -> Fact:
        src = SourceReference(
            resource_id=f"web:{verified.external.source_tier.value}",
            file_path=verified.external.source_url,
            file_name=verified.external.source_name or verified.external.source_url.split("/")[-1],
        )
        return verified.to_fact(
            fact_id=f"ext_{datetime.now().timestamp():.0f}_{abs(hash(verified.external.normalized_value)) % 100000}",
            source_ref=src,
        )

    def _log_acquisition(self, topic: str, total: int,
                          accepted: int, pending: int,
                          added: int, low_coverage: List[str]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "raw_results": total,
            "accepted_after_voting": accepted,
            "pending_verification": pending,
            "added_to_store": added,
            "low_coverage_sections": low_coverage,
        }
        self._acquisition_log.append(entry)
        logger.info(
            f"External acquisition: {total} raw → {accepted} accepted "
            f"→ {added} added to store ({pending} pending verification)"
        )
