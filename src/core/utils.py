"""Shared utility functions for the report generation framework."""

import json
import re
from typing import Any, Dict, Optional


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from text, handling common LLM output issues.
    
    Handles:
    - Markdown code fences (```json ... ```)
    - Single quotes instead of double quotes
    - Trailing commas
    - JavaScript-style comments
    """
    if not text:
        return None
    
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)

    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if not json_match:
        return None

    raw = json_match.group()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fixed = re.sub(r"(?<!\\)'(.*?)'(?=\s*:)", r'"\1"', raw)
    fixed = re.sub(r":\s*'(.*?)'(?=[\s,}])", r': "\1"', fixed)
    fixed = re.sub(r",\s*}", "}", fixed)
    fixed = re.sub(r",\s*]", "]", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    fixed2 = re.sub(r'//[^\n]*', '', fixed)
    try:
        return json.loads(fixed2)
    except json.JSONDecodeError:
        return None
