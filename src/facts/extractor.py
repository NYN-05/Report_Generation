from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import re
import uuid
from src.core.logger import get_logger
from .models import (
    Fact, FactType, EvidenceSpan, SourceReference,
    ObjectiveFact, DatasetFact, MetricFact, AlgorithmFact,
    ResultFact, CitationFact, TechnologyFact, ArchitectureFact,
    RequirementFact,
)

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    facts: List[Fact] = field(default_factory=list)
    extraction_time_ms: float = 0.0
    total_chunks_processed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "fact_count": len(self.facts),
            "by_type": {
                ft.value: sum(1 for f in self.facts if f.fact_type == ft)
                for ft in FactType
            },
            "extraction_time_ms": self.extraction_time_ms,
            "total_chunks_processed": self.total_chunks_processed,
            "errors": self.errors[:5],
        }


FACT_TYPE_PATTERNS: Dict[FactType, List[str]] = {
    FactType.OBJECTIVE: [
        r"(?:objective|goal|aim|purpose|target)\s*(?:is|of|:)\s*.{10,200}?[.!\n]",
        r"the\s+(?:objective|goal|aim)\s+(?:of|is)\s+.{10,200}?[.!\n]",
    ],
    FactType.DATASET: [
        r"\b(?:[A-Z][a-zA-Z0-9_-]{2,})\s*(?:dataset|corpus|benchmark)\b",
        r"\b(?:dataset|corpus|benchmark)\s+(?:called|named|known\s+as)\s+[A-Z][a-zA-Z0-9_-]+",
        r"\b\d+[.,]?\d*\s*(?:GB|MB|TB|samples|images|records|instances)\b",
    ],
    FactType.METRIC: [
        r"\b(?:accuracy|precision|recall|f1[-\s]?score|AUC|ROC|BLEU|ROUGE|perplexity)\s*(?:of|:|=|reached|achieved)\s*\d+\.?\d*\%?",
        r"\d+\.?\d*\s*\%?\s*(?:accuracy|precision|recall|f1[-\s]?score)",
    ],
    FactType.ALGORITHM: [
        r"\b(?:Random Forest|Support Vector Machine|SVM|K-Means|KNN|CNN|RNN|LSTM|GRU|Transformer|BERT|GPT|ResNet|DenseNet|YOLO|U-Net|GAN)\b",
        r"\b(?:algorithm|model|method|classifier|regressor)\s+(?:called|named|known\s+as)\s+[A-Z][a-zA-Z0-9_-]+",
    ],
    FactType.TECHNOLOGY: [
        r"\b(Python|PyTorch|TensorFlow|Keras|scikit-learn|JAX|NumPy|Pandas|Docker|Kubernetes|CUDA|OpenMP|MPI|Spark|Hadoop)\b",
        r"\b(?:implemented|developed|built|created)\s+(?:using|with|in)\s+[A-Z][a-zA-Z0-9_.+-]+",
    ],
    FactType.ARCHITECTURE: [
        r"\b(?:architecture|system\s+design|pipeline|framework)\s*(?:of|for|using|based)\s*.{20,200}?[.!\n]",
    ],
    FactType.RESULT: [
        r"(?:achieved|reached|obtained|yielded|produced|attained)\s+(?:an?\s+)?"
        r"\w+\s+(?:of\s+)?\d+\.?\d*\s*\%?",
        r"(?:improvement|gain|increase|reduction)\s+(?:of|by)\s+\d+\.?\d*\s*\%?",
    ],
    FactType.CITATION: [
        r"\[(\d+)\]\s*.{30,200}?(?=\[|\n|$)",
        r"\([A-Z][a-zA-Z]*\s+et\s+al\.?\s*,\s*\d{4}\)",
    ],
    FactType.REQUIREMENT: [
        r"(?:require|requirement|needs?|must|shall|should)\s+\w+.{10,200}?[.!\n]",
    ],
}


class FactExtractor:
    def __init__(self):
        self._extracted_facts: List[Fact] = []

    def extract(self, text: str, source: SourceReference,
                chunk_meta: Optional[Dict] = None) -> ExtractionResult:
        import time
        start = time.perf_counter()
        facts: List[Fact] = []

        if not text or len(text.strip()) < 20:
            return ExtractionResult()

        text_lower = text.lower()

        for fact_type, patterns in FACT_TYPE_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    value = match.group(0).strip()
                    if len(value) < 10:
                        continue
                    span = EvidenceSpan(
                        text=value,
                        start_char=match.start(),
                        end_char=match.end(),
                        page_number=chunk_meta.get("page_number") if chunk_meta else None,
                        section_name=chunk_meta.get("section_name") if chunk_meta else None,
                    )
                    fact = self._create_fact(
                        fact_type=fact_type,
                        value=value,
                        source=source,
                        span=span,
                        chunk_meta=chunk_meta or {},
                    )
                    facts.append(fact)

        fact_types_detected = set(f.fact_type for f in facts)
        if FactType.GENERAL not in fact_types_detected:
            general_facts = self._extract_general_facts(text, source, chunk_meta)
            facts.extend(general_facts)

        deduplicated = self._deduplicate(facts)
        self._extracted_facts.extend(deduplicated)

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            f"Extracted {len(deduplicated)} facts ({len(facts)} raw) "
            f"in {elapsed:.1f}ms"
        )
        return ExtractionResult(
            facts=deduplicated,
            extraction_time_ms=round(elapsed, 1),
        )

    def _create_fact(self, fact_type: FactType, value: str,
                     source: SourceReference, span: EvidenceSpan,
                     chunk_meta: Dict) -> Fact:
        fact_id = f"fact_{uuid.uuid4().hex[:12]}"
        normalized = self._normalize(value)
        confidence = self._compute_confidence(value, fact_type, chunk_meta)
        concepts = self._extract_concepts(value)

        base_kwargs = {
            "fact_id": fact_id,
            "fact_type": fact_type,
            "value": value,
            "normalized_value": normalized,
            "confidence": confidence,
            "source": source,
            "concepts": concepts,
            "metadata": chunk_meta,
        }

        if fact_type == FactType.METRIC:
            metric_name, metric_value = self._parse_metric(value)
            return MetricFact(
                **base_kwargs,
                metric_name=metric_name,
                metric_value=metric_value,
            )
        elif fact_type == FactType.ALGORITHM:
            algo_name = self._extract_algorithm_name(value)
            return AlgorithmFact(**base_kwargs, algorithm_name=algo_name)
        elif fact_type == FactType.DATASET:
            ds_name = self._extract_dataset_name(value)
            return DatasetFact(**base_kwargs, dataset_name=ds_name)
        elif fact_type == FactType.TECHNOLOGY:
            tech_name = self._extract_tech_name(value)
            return TechnologyFact(**base_kwargs, technology_name=tech_name)
        elif fact_type == FactType.RESULT:
            metric_val = self._extract_numeric_value(value)
            return ResultFact(**base_kwargs, metric_value=metric_val)
        elif fact_type == FactType.CITATION:
            return CitationFact(**base_kwargs, citation_key=fact_id)
        elif fact_type == FactType.ARCHITECTURE:
            arch_name = self._extract_architecture_name(value)
            return ArchitectureFact(**base_kwargs, architecture_name=arch_name)
        elif fact_type == FactType.OBJECTIVE:
            return ObjectiveFact(**base_kwargs)
        elif fact_type == FactType.REQUIREMENT:
            return RequirementFact(**base_kwargs)
        else:
            return Fact(**base_kwargs)

    def _extract_general_facts(self, text: str, source: SourceReference,
                                chunk_meta: Optional[Dict] = None) -> List[Fact]:
        facts = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 30 or len(sent) > 500:
                continue
            span = EvidenceSpan(
                text=sent,
                start_char=text.find(sent),
                end_char=text.find(sent) + len(sent),
            )
            fact = Fact(
                fact_id=f"fact_{uuid.uuid4().hex[:12]}",
                fact_type=FactType.GENERAL,
                value=sent,
                normalized_value=self._normalize(sent),
                confidence=0.5,
                source=source,
                span=span,
            )
            facts.append(fact)
        return facts[:20]

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\d.%-]', '', text)
        return text[:300]

    def _compute_confidence(self, value: str, fact_type: FactType,
                             chunk_meta: Dict) -> float:
        score = 0.6
        if fact_type in (FactType.METRIC, FactType.RESULT):
            if re.search(r'\d+\.?\d*\%?', value):
                score += 0.2
        if fact_type == FactType.ALGORITHM:
            if re.search(r'[A-Z]', value):
                score += 0.15
        if re.search(r'(?:according to|reported|published|shown in)', value.lower()):
            score += 0.15
        if chunk_meta.get("source"):
            score += 0.05
        return round(min(score, 1.0), 2)

    def _extract_concepts(self, text: str) -> List[str]:
        words = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b', text)
        return list(set(w for w in words if len(w) > 3))[:10]

    def _parse_metric(self, text: str) -> Tuple[str, Optional[float]]:
        metric_names = [
            "accuracy", "precision", "recall", "f1", "f1-score", "f1_score",
            "auc", "roc", "bleu", "rouge", "perplexity", "mAP", "iou",
        ]
        text_lower = text.lower()
        for name in metric_names:
            if name in text_lower:
                val = self._extract_numeric_value(text)
                return name, val
        return "unknown", self._extract_numeric_value(text)

    def _extract_numeric_value(self, text: str) -> Optional[float]:
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            return float(match.group(1))
        return None

    def _extract_algorithm_name(self, text: str) -> str:
        known = re.findall(
            r"(?:Random Forest|Support Vector Machine|SVM|K-Means|KNN|CNN|RNN|"
            r"LSTM|GRU|Transformer|BERT|GPT|ResNet|DenseNet|YOLO|U-Net|GAN)",
            text, re.IGNORECASE
        )
        if known:
            return known[0]
        match = re.search(r"(?:algorithm|model|method)\s+(?:called|named)\s+([A-Z][a-zA-Z0-9_-]+)", text)
        if match:
            return match.group(1)
        return text[:50]

    def _extract_dataset_name(self, text: str) -> str:
        match = re.search(r"([A-Z][a-zA-Z0-9_-]{2,})\s*(?:dataset|corpus|benchmark)", text)
        if match:
            return match.group(1)
        match = re.search(r"(?:dataset|corpus|benchmark)\s+(?:called|named)\s+([A-Z][a-zA-Z0-9_-]+)", text)
        if match:
            return match.group(1)
        return text[:50]

    def _extract_tech_name(self, text: str) -> str:
        known = re.findall(
            r"(Python|PyTorch|TensorFlow|Keras|scikit-learn|JAX|NumPy|Pandas|"
            r"Docker|Kubernetes|CUDA|OpenMP|MPI|Spark|Hadoop)",
            text, re.IGNORECASE
        )
        if known:
            return known[0]
        match = re.search(r"(?:using|with|in)\s+([A-Z][a-zA-Z0-9_.+-]+)", text)
        if match:
            return match.group(1)
        return text[:50]

    def _extract_architecture_name(self, text: str) -> str:
        match = re.search(r"(?:architecture|framework|pipeline)\s+(?:of|for|based)\s+(.{10,100})", text)
        if match:
            return match.group(1).strip()[:50]
        return text[:50]

    def _deduplicate(self, facts: List[Fact], iou_threshold: float = 0.7) -> List[Fact]:
        unique: List[Fact] = []
        for fact in facts:
            is_dup = False
            for existing in unique:
                if self._texts_overlap(fact.normalized_value, existing.normalized_value, iou_threshold):
                    if fact.confidence > existing.confidence:
                        unique.remove(existing)
                        unique.append(fact)
                    is_dup = True
                    break
            if not is_dup:
                unique.append(fact)
        return unique

    def _texts_overlap(self, a: str, b: str, threshold: float) -> bool:
        a_words = set(a.split())
        b_words = set(b.split())
        if not a_words or not b_words:
            return False
        intersection = a_words & b_words
        union = a_words | b_words
        iou = len(intersection) / len(union)
        return iou >= threshold

    def extract_from_chunks(self, chunks: List[Dict],
                            resource_id: str = "",
                            file_path: str = "",
                            file_name: str = "") -> ExtractionResult:
        import time
        start = time.perf_counter()
        all_facts: List[Fact] = []
        errors: List[str] = []

        for i, chunk in enumerate(chunks):
            try:
                text = chunk.get("text", chunk.get("content", ""))
                if not text:
                    continue
                meta = chunk.get("metadata", {})
                source = SourceReference(
                    resource_id=resource_id or meta.get("resource_id", f"chunk_{i}"),
                    file_path=file_path or meta.get("source", ""),
                    file_name=file_name or meta.get("file_name", ""),
                    page_number=meta.get("page_number"),
                    chunk_id=meta.get("chunk_id", f"chunk_{i}"),
                )
                result = self.extract(text, source, meta)
                all_facts.extend(result.facts)
            except Exception as e:
                errors.append(f"Chunk {i}: {e}")

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            f"Extracted {len(all_facts)} facts from {len(chunks)} chunks "
            f"in {elapsed:.1f}ms"
        )
        return ExtractionResult(
            facts=all_facts,
            extraction_time_ms=round(elapsed, 1),
            total_chunks_processed=len(chunks),
            errors=errors,
        )

    def get_all_facts(self) -> List[Fact]:
        return list(self._extracted_facts)

    def get_facts_by_type(self, fact_type: FactType) -> List[Fact]:
        return [f for f in self._extracted_facts if f.fact_type == fact_type]

    def get_high_confidence_facts(self, threshold: float = 0.7) -> List[Fact]:
        return [f for f in self._extracted_facts if f.confidence >= threshold]

    def reset(self):
        self._extracted_facts.clear()
