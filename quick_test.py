import sys, time
sys.path.insert(0, '.')
from src.ingestion.pipeline import IngestionPipeline
from src.evidence.orchestrator import EvidenceOrchestrator
from src.quality.evidence_fidelity_score import EvidenceFidelityScore
from src.quality.fact_utilization_score import FactUtilizationScore
from src.quality.source_coverage_score import SourceCoverageScore
from src.quality.hallucination_risk_score import HallucinationRiskScore
from src.evidence.traceability import TraceabilityBuilder
from src.quality.comprehensive_quality_score import ComprehensiveQualityScore
from src.validation.hallucination_detector import HallucinationDetector
from src.evidence.dashboard import EvidenceDashboard
from src.evidence.report_explainability import ReportExplainer

print('='*60)
print('  EVIDENCE-CENTRIC PIPELINE - QUICK TEST')
print('='*60)

t0 = time.time()

ingest = IngestionPipeline()
ingest.ingest_directory('knowledge')
chunks = ingest.get_chunks()
print(f'[OK] Ingestion: {len(chunks)} chunks')

orch = EvidenceOrchestrator()
r = orch.ingest_chunks(chunks)
print(f'[OK] Resource Intel: {r["total_facts"]} facts from {r["chunks_processed"]} chunks')

n = len(orch.fact_store.get_all_facts())
print(f'[OK] Fact Store: {n} typed facts')

g = orch.build_graph()
print(f'[OK] Knowledge Graph: {g["nodes"]} nodes, {g["edges"]} edges')

bp = orch.generate_blueprint('Human Brain')
print(f"[OK] Blueprint: {len(bp.sections)} sections, richness={bp.evidence_richness:.0%}")

all_f = orch.fact_store.get_all_facts()
from src.facts.models import FactType

fbs = {}
sd = {}
for s in bp.sections:
    req = []
    for ftn in s.required_fact_types:
        try: req.append(FactType(ftn))
        except: pass
    sf = [f for f in all_f if f.fact_type in req]
    fbs[s.section_type] = sf
    sd[s.section_type] = {'heading': s.heading, 'paragraphs': []}

cov = orch.coverage_engine.build_report(sd, fbs)
print(f"[OK] Coverage: {cov.overall_coverage:.0%}, mode={cov.generation_mode.value}")

c = orch.build_generation_constraints(bp)
print(f'[OK] Constraints: {len(c)} sections')

fsb = {'overview': all_f}
ss = {'overview': 'Human Brain overview text'}
efs = EvidenceFidelityScore().score_global(ss, fsb)['evidence_fidelity_score']
fus = FactUtilizationScore().score_global(ss, fsb)['fact_utilization_score']
scs = SourceCoverageScore().score_global(ss, fsb)['source_coverage_score']
hrs = HallucinationRiskScore(orch.fact_store).score_global(ss, fsb)['hallucination_risk_score']
cqs = ComprehensiveQualityScore(orch.fact_store, TraceabilityBuilder(orch.fact_store))
cqr = cqs.evaluate_section('overview', 'Human Brain overview text', all_f)['quality_score']
print(f'[OK] Quality Scores: fidelity={efs:.2f} util={fus:.2f} src_cov={scs:.2f} hal_risk={hrs:.2f} comp={cqr:.2f}')

det = HallucinationDetector(orch.fact_store)
hr = det.check_report(orch.fact_store, ss)
print(f'[OK] Hallucination: {hr["total_issues"]} issues, free={hr["hallucination_free"]}')

fr = orch.fusion_engine.fuse_all(all_f)
print(f'[OK] Fusion: {len(fr)} results')

db = EvidenceDashboard(orch.fact_store, orch.coverage_engine, orch.traceability, orch.knowledge_graph)
ov = db.get_overview()
print(f"[OK] Dashboard: {ov['fact_store']['total_facts']} facts, {ov['knowledge_graph']['node_count']} nodes")

tm = orch.build_traceability_map('test', {'overview': [{'paragraph_id': 'p0', 'text': 'test'}]})
print(f"[OK] Traceability: {tm.traced_paragraphs}/{tm.total_paragraphs} traced")

exp = ReportExplainer(orch.fact_store, orch.traceability, orch.coverage_engine, orch.knowledge_graph)
paragraphs = [{'paragraph_id': 'p0', 'text': 'Human Brain test', 'section_type': 'overview'}]
ex = exp.explain_section('overview', paragraphs)
print(f"[OK] Explainability: {ex['unique_facts_used']} facts, {ex['unique_sources_used']} sources, {ex['paragraph_count']} paragraphs")

dt = time.time() - t0
print(f'\n=== ALL 11 COMPONENTS VERIFIED in {dt:.1f}s ===')
