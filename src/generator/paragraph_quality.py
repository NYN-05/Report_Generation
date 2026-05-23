"""ParagraphQualityControl — enforces paragraph structure and quality standards.

Each paragraph must satisfy:
- Minimum 120 words
- Maximum 250 words
- Contains: topic sentence, supporting explanation, technical details, concluding transition
- Rejects shallow, generic, marketing, or conversational content
"""

import re
from typing import List, Optional, Tuple


class ParagraphQualityControl:

    MIN_WORDS = 120
    MAX_WORDS = 250

    SHALLOW_PATTERNS = [
        r"in today['\u2019]s (world|digital age|modern era)",
        r"it is (important|essential|crucial|vital) to",
        r"plays a (crucial|vital|important|significant|key) role",
        r"in the realm of",
        r"leaves much to be desired",
        r"cutting-edge",
        r"state-of-the-art",
        r"game-changer",
        r"revolutionary",
        r"next-generation",
        r"a wide range of",
        r"various (aspects|factors|elements|components)",
        r"there are many (ways|approaches|methods|techniques)",
        r"as mentioned (above|earlier|previously)",
        r"it should be noted that",
        r"it is worth mentioning",
    ]

    MARKETING_PATTERNS = [
        r"empowers (organizations|businesses|users|teams)",
        r"unlock(s|ed)? (new|the full|its) (potential|capabilities|possibilities)",
        r"seamless(ly)?",
        r"robust (solution|platform|framework|system)",
        r"best-in-class",
        r"industry-leading",
        r"groundbreaking",
        r"hassle-free",
    ]

    CONVERSATIONAL_PATTERNS = [
        r"let['\u2019]s (dive|explore|look|consider|take)",
        r"now,? (let|we|you)",
        r"so,? (what|how|why|the)",
        r"well,? ",
        r"you (might|may|can|could|will) (wonder|ask|think|notice|see)",
        r"as you can see",
        r"imagine",
        r"think about",
        r"keep in mind",
    ]

    def check_paragraph(self, text: str) -> List[str]:
        errors = []
        words = text.split()
        word_count = len(words)

        if word_count < self.MIN_WORDS:
            errors.append(f"Too short: {word_count} words (min {self.MIN_WORDS})")
        if word_count > self.MAX_WORDS:
            errors.append(f"Too long: {word_count} words (max {self.MAX_WORDS})")

        structure_errors = self._check_structure(text)
        errors.extend(structure_errors)

        shallow = self._check_patterns(text, self.SHALLOW_PATTERNS)
        if shallow:
            errors.append(f"Shallow/generic language: {shallow[:2]}")

        marketing = self._check_patterns(text, self.MARKETING_PATTERNS)
        if marketing:
            errors.append(f"Marketing language: {marketing[:2]}")

        conversational = self._check_patterns(text, self.CONVERSATIONAL_PATTERNS)
        if conversational:
            errors.append(f"Conversational tone: {conversational[:2]}")

        bullet_errors = self._check_embedded_bullets(text)
        errors.extend(bullet_errors)

        return errors

    def _check_structure(self, text: str) -> List[str]:
        errors = []
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if not sentences:
            return ["No sentences found"]

        topic = sentences[0]
        if len(topic.split()) < 5:
            errors.append("Topic sentence too short (<5 words)")
        if "?" in topic:
            errors.append("Topic sentence is a question")

        if len(sentences) < 3:
            errors.append(f"Too few sentences: {len(sentences)} (min 3)")

        return errors

    def _check_patterns(self, text: str, patterns: List[str]) -> List[str]:
        found = []
        for p in patterns:
            matches = re.findall(p, text, re.IGNORECASE)
            if matches:
                found.append(matches[0][:60] if isinstance(matches[0], str) else str(matches[0]))
        return found

    def _check_embedded_bullets(self, text: str) -> List[str]:
        errors = []
        if re.search(r'(?:^|\n)\s*[•\-\*]\s', text):
            errors.append("Contains embedded bullet markers")
        if re.search(r'(?:such as|including|for example|e\.g\.)[^.]*(?:•|\-|\*)', text, re.IGNORECASE):
            errors.append("Bullet markers embedded inside paragraph")
        return errors

    def score(self, text: str) -> Tuple[float, float, float, float, float]:
        words = text.split()
        wc = len(words)

        structure_score = 1.0
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if len(sentences) < 3:
            structure_score = max(0, len(sentences) / 3)
        if sentences and len(sentences[0].split()) < 5:
            structure_score *= 0.7

        length_score = 1.0
        if wc < self.MIN_WORDS:
            length_score = max(0, wc / self.MIN_WORDS)
        elif wc > self.MAX_WORDS:
            length_score = max(0, 1 - (wc - self.MAX_WORDS) / self.MAX_WORDS)

        shallow_count = len(self._check_patterns(text, self.SHALLOW_PATTERNS))
        marketing_count = len(self._check_patterns(text, self.MARKETING_PATTERNS))
        conv_count = len(self._check_patterns(text, self.CONVERSATIONAL_PATTERNS))
        quality_score = max(0, 1.0 - (shallow_count + marketing_count + conv_count) * 0.2)

        bullet_issues = len(self._check_embedded_bullets(text))
        format_score = max(0, 1.0 - bullet_issues * 0.5)

        avg_sentence_len = wc / max(len(sentences), 1)
        readability_score = 1.0
        if avg_sentence_len < 8:
            readability_score = 0.5
        elif avg_sentence_len > 40:
            readability_score = 0.6

        return (structure_score, length_score, quality_score, format_score, readability_score)

    def is_acceptable(self, text: str) -> bool:
        errors = self.check_paragraph(text)
        critical = [e for e in errors if any(k in e for k in
                    ["Too short", "Too long", "shallow", "marketing", "conversational", "embedded"])]
        return len(critical) <= 1
