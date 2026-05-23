"""ParagraphQualityControl — enforces paragraph structure and quality standards.

Each paragraph must satisfy:
- Minimum 120 words, maximum 250 words
- Core idea, explanation, supporting detail, analysis, transition
- Rejects vague statements, generic observations, marketing language, empty claims, filler phrases

Forbidden phrases:
  "Several important aspects can be observed."
  "This topic has gained significant attention."
  "Research indicates many benefits."
  "Various studies have shown improvements."
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

    VAGUE_STATEMENTS = [
        r"Several (important|key|significant) aspects can be observed",
        r"This (topic|area|field) has gained (significant|considerable|substantial) attention",
        r"Research indicates (many|numerous|several) benefits",
        r"Various studies have shown (improvements|enhancements|benefits)",
        r"It is (widely|generally|commonly) (known|accepted|believed|understood) that",
        r"There has been (growing|increasing|significant) (interest|focus|attention)",
        r"In (recent|the past|the last) (years|decades), there has been",
        r"The (importance|significance|relevance) of .* cannot be (overstated|overemphasized|overlooked)",
        r"This (section|chapter|paper|report) (discusses|examines|explores|investigates)",
        r"The (following|above|aforementioned) (section|chapter) (discussed|described|presented)",
    ]

    EMPTY_CLAIMS = [
        r"results show (that )?(significant|great|excellent|good) (improvement|performance|results)",
        r"the proposed (method|approach|system|framework) (achieves|obtains|yields) (better|superior|excellent)",
        r"experimental results (demonstrate|show|indicate|confirm) the (effectiveness|efficiency|superiority)",
        r"comprehensive (analysis|evaluation|assessment) reveals",
        r"promising (results|outcomes|performance|directions)",
        r"very (good|high|strong|positive|effective) (results|performance|outcomes)",
    ]

    TOPIC_TEMPLATE_PATTERNS = [
        r"the (topic|subject|field|area) of ",
        r"in the context of ",
        r"in (the field|the area|relation) of ",
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

        vague = self._check_patterns(text, self.VAGUE_STATEMENTS)
        if vague:
            errors.append(f"Vague statement: {vague[0][:60]}")

        empty = self._check_patterns(text, self.EMPTY_CLAIMS)
        if empty:
            errors.append(f"Empty claim: {empty[0][:60]}")

        template = self._check_patterns(text, self.TOPIC_TEMPLATE_PATTERNS)
        if template:
            errors.append(f"Topic-replacement-template pattern detected: {template[0]}")

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

        if len(sentences) >= 3:
            has_analysis = any(
                re.search(r'\b(therefore|however|furthermore|consequently|because|since|thus|hence|whereas|although|despite|nevertheless|moreover|specifically|notably)\b', s, re.IGNORECASE)
                for s in sentences
            )
            if not has_analysis:
                errors.append("Missing analytical language (therefore, however, etc.)")

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

    def score(self, text: str) -> Tuple[float, float, float, float, float, float, float]:
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
        vague_count = len(self._check_patterns(text, self.VAGUE_STATEMENTS))
        empty_count = len(self._check_patterns(text, self.EMPTY_CLAIMS))
        template_count = len(self._check_patterns(text, self.TOPIC_TEMPLATE_PATTERNS))
        marketing_count = len(self._check_patterns(text, self.MARKETING_PATTERNS))
        conv_count = len(self._check_patterns(text, self.CONVERSATIONAL_PATTERNS))
        total_violations = shallow_count + vague_count + empty_count + template_count + marketing_count + conv_count
        quality_score = max(0, 1.0 - total_violations * 0.15)

        bullet_issues = len(self._check_embedded_bullets(text))
        format_score = max(0, 1.0 - bullet_issues * 0.5)

        avg_sentence_len = wc / max(len(sentences), 1)
        readability_score = 1.0
        if avg_sentence_len < 8:
            readability_score = 0.5
        elif avg_sentence_len > 40:
            readability_score = 0.6

        has_analysis = bool(re.search(r'\b(therefore|however|furthermore|consequently|because|since|thus|hence|whereas|although|nevertheless|moreover)\b', text, re.IGNORECASE))
        analysis_score = 0.8 if has_analysis else 0.4

        transition_score = 1.0
        if sentences and not re.search(r'\b(this|these|that|those|such|the)\b', sentences[-1], re.IGNORECASE):
            transition_score = 0.7

        return (structure_score, length_score, quality_score, format_score, readability_score, analysis_score, transition_score)

    def is_acceptable(self, text: str) -> bool:
        errors = self.check_paragraph(text)
        critical = [e for e in errors if any(k in e for k in
                    ["Too short", "Too long", "shallow", "vague", "empty", "marketing", "conversational",
                     "embedded", "template", "Topic-replacement"])]
        return len(critical) <= 1
