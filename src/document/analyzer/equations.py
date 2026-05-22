from typing import List
from docx import Document as DocxDocument
from docx.oxml.ns import qn

from .models import EquationInfo

OMML_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'


class EquationDetector:
    """Detects OMML equations in document paragraphs."""

    def __init__(self, doc: DocxDocument):
        self.doc = doc

    def detect(self) -> List[EquationInfo]:
        results: List[EquationInfo] = []
        eq_idx = 0
        for pi, para in enumerate(self.doc.paragraphs):
            elem = para._element
            oMaths = elem.findall(f'{{{OMML_NS}}}oMath')
            for om in oMaths:
                plain_text = self._extract_math_text(om)
                is_inline = om.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}inline', 'false').lower() != 'true'
                results.append(EquationInfo(
                    index=eq_idx,
                    paragraph_index=pi,
                    math_type="omml",
                    inline=is_inline,
                    plain_text_approx=plain_text,
                ))
                eq_idx += 1
            oMathParas = elem.findall(f'{{{OMML_NS}}}oMathPara')
            for omp in oMathParas:
                plain_text = self._extract_math_text(omp)
                results.append(EquationInfo(
                    index=eq_idx,
                    paragraph_index=pi,
                    math_type="omml",
                    inline=False,
                    plain_text_approx=plain_text,
                ))
                eq_idx += 1
        return results

    def _extract_math_text(self, math_elem) -> str:
        texts = math_elem.findall(f'{{{OMML_NS}}}t')
        if not texts:
            texts = math_elem.findall(f'.//{qn("m:t")}')
        parts = [t.text or "" for t in texts]
        return " ".join(parts).strip()
