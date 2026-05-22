"""
Skill Loader Module
====================
Dynamic skill discovery and loading.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from .base import Skill
from src.core.logger import get_logger
from src.core.config import get_config

logger = get_logger(__name__)


class SkillLoader:
    """Dynamic skill discovery and loading system."""

    _instance = None

    def __init__(self, skills_dir: str = None):
        config = get_config()
        self.skills_dir = Path(skills_dir or config.skills.directory)
        self.skills: Dict[str, Skill] = {}
        self._initialized = False
        self._last_scan: Optional[datetime] = None

    def initialize(self, force: bool = False) -> int:
        """Scan and index all skills in the skills directory."""
        if self._initialized and not force:
            return len(self.skills)

        logger.info("Initializing skill discovery...")

        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return 0

        skill_files = list(self.skills_dir.glob("*/SKILL.md"))
        logger.info(f"Found {len(skill_files)} skill definitions")

        self.skills.clear()

        for skill_file in skill_files:
            try:
                skill = self._parse_skill_file(skill_file)
                if skill:
                    self.skills[skill.name] = skill
                    logger.debug(f"  Loaded: {skill.name}")
            except Exception as e:
                logger.error(f"  Failed to load {skill_file}: {e}")

        self._initialized = True
        self._last_scan = datetime.now()

        logger.info(f"Skills indexed: {len(self.skills)}")
        return len(self.skills)

    def _parse_skill_file(self, skill_file: Path) -> Optional[Skill]:
        """Parse a SKILL.md file and extract metadata."""
        try:
            content = skill_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Cannot read {skill_file}: {e}")
            return None

        frontmatter = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        frontmatter[key.strip()] = value.strip().strip('"')

        name = frontmatter.get('name', skill_file.parent.name)
        description = frontmatter.get('description', '')
        license_info = frontmatter.get('license', '')

        triggers = []
        extensions = re.findall(r'\.\w+', description)
        triggers.extend([ext.replace('.', '') for ext in extensions])

        keywords = re.findall(r'\b[A-Z][a-z]+\b', description)[:20]

        folder = skill_file.parent.name
        tags = [t.lower() for t in re.split(r'[-_]', folder) if len(t) > 2]

        return Skill(
            name=name,
            description=description,
            folder_path=str(skill_file.parent),
            triggers=list(set(triggers))[:20],
            keywords=[k.lower() for k in keywords],
            tags=list(set(tags))[:15],
            license=license_info,
            content=content,
            loaded_at=datetime.now()
        )

    def reload(self) -> int:
        """Force reload of skills."""
        return self.initialize(force=True)

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a specific skill by name."""
        if not self._initialized:
            self.initialize()
        return self.skills.get(name)

    def get_all_skills(self) -> Dict[str, Skill]:
        """Get all registered skills."""
        if not self._initialized:
            self.initialize()
        return self.skills.copy()

    def search(self, query: str, min_score: float = 0.5) -> List[tuple]:
        """Search skills by relevance score."""
        if not self._initialized:
            self.initialize()

        results = []
        for name, skill in self.skills.items():
            score = skill.relevance_score_for(query)
            if score >= min_score:
                skill.relevance_score = score
                results.append((skill, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_skill_names(self) -> List[str]:
        """Get list of all skill names."""
        if not self._initialized:
            self.initialize()
        return list(self.skills.keys())

    def get_skills_by_tag(self, tag: str) -> List[Skill]:
        """Get all skills with a specific tag."""
        if not self._initialized:
            self.initialize()
        return [s for s in self.skills.values() if tag in s.tags]

    def find_by_keyword(self, keyword: str) -> List[Skill]:
        """Find skills by keyword in description."""
        if not self._initialized:
            self.initialize()
        keyword_lower = keyword.lower()
        return [
            s for s in self.skills.values()
            if keyword_lower in s.description.lower() or keyword_lower in s.name.lower()
        ]


def load_skills(skills_dir: str = None) -> Dict[str, Skill]:
    """Convenience function to load all skills."""
    loader = SkillLoader(skills_dir)
    loader.initialize()
    return loader.get_all_skills()