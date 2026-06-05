import os
import time
import re
from typing import List, Dict, Optional, Set
from datetime import datetime
from pathlib import Path
from src.core.logger import get_logger

logger = get_logger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_HEADERS = {
    "User-Agent": "ReportGenerator/1.0 (Academic research project; jhashank@example.com)"
}


class KnowledgeCollector:
    """Downloads free knowledge from the web for a given topic.

    Sources (all free, no API key required):
      - Wikipedia API (primary) — multi-phase collection
      - DuckDuckGo + direct page fetch (secondary fallback)

    Multi-phase Wikipedia strategy:
      1. Opensearch (direct matches, up to 25)
      2. Text search (related pages, up to 50)
      3. Multi-query expansion (subtopic searches)
      4. Links from main article (linked pages)

    Saved as markdown files into the knowledge directory before ingestion.
    """

    def __init__(self, knowledge_dir: str = "knowledge"):
        self._knowledge_dir = Path(knowledge_dir)
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)

    def collect(self, topic: str, max_pages: int = 25) -> int:
        logger.info(f"Collecting knowledge for: {topic}")
        saved = 0
        seen = set()
        existing = {f.stem.lower() for f in self._knowledge_dir.glob("*.md")}

        try:
            import requests as req
        except ImportError:
            logger.warning("requests not available, skipping collection")
            return 0

        saved += self._phase_opensearch(topic, req, max_pages, seen, existing)
        if saved < max_pages:
            saved += self._phase_text_search(topic, req, max_pages, seen, existing)
        if saved < max_pages:
            saved += self._phase_multi_query(topic, req, max_pages, seen, existing)
        if saved < max_pages:
            saved += self._phase_linked_pages(topic, req, max_pages, seen, existing)
        if saved < max_pages:
            saved += self._phase_web_fallback(topic, req, max_pages, seen)

        total = sum(1 for _ in self._knowledge_dir.glob("*.md"))
        logger.info(
            f"Knowledge collection complete: {saved} new files "
            f"({total} total in {self._knowledge_dir})"
        )
        return saved

    # ── Phase 1: OpenSearch ──────────────────────────────────────────────

    def _phase_opensearch(
        self, topic: str, req, max_pages: int,
        seen: Set[str], existing: Set[str]
    ) -> int:
        saved = 0
        titles = self._wiki_opensearch(topic, req, limit=25)
        for title in titles:
            if saved >= max_pages:
                break
            if self._already_have(title, seen, existing):
                continue
            if self._save_page(title, req, seen):
                saved += 1
        logger.info(f"  Phase 1 (opensearch): {saved} pages saved")
        return saved

    def _phase_text_search(
        self, topic: str, req, max_pages: int,
        seen: Set[str], existing: Set[str]
    ) -> int:
        saved = 0
        titles = self._wiki_text_search(topic, req, limit=50)
        for title in titles:
            if saved >= max_pages:
                break
            if self._already_have(title, seen, existing):
                continue
            if self._save_page(title, req, seen):
                saved += 1
        logger.info(f"  Phase 2 (text search): {saved} pages saved")
        return saved

    def _phase_multi_query(
        self, topic: str, req, max_pages: int,
        seen: Set[str], existing: Set[str]
    ) -> int:
        saved = 0
        words = topic.split()
        base = words[0] if words else topic
        suffixes = [
            "", "anatomy", "function", "development", "research",
            "history", "classification", "types", "evolution",
            "pathology", "biology", "structure", "mechanism",
            "applications", "diseases", "disorders", "treatment",
            "physiology", "genetics", "biochemistry",
        ]
        queries = [f"{base} {s}" for s in suffixes]
        if len(words) > 1:
            queries += [f"{topic} {s}" for s in suffixes[:10]]

        for q in queries:
            if saved >= max_pages:
                break
            titles = self._wiki_opensearch(q, req, limit=5)
            for title in titles:
                if saved >= max_pages:
                    break
                if self._already_have(title, seen, existing):
                    continue
                if self._save_page(title, req, seen):
                    saved += 1

        logger.info(f"  Phase 3 (multi-query): {saved} pages saved")
        return saved

    def _phase_linked_pages(
        self, topic: str, req, max_pages: int,
        seen: Set[str], existing: Set[str]
    ) -> int:
        saved = 0
        main_title = self._resolve_title(topic, req)
        if not main_title:
            return 0
        titles = self._wiki_get_links(main_title, req, limit=50)
        for title in titles:
            if saved >= max_pages:
                break
            if self._already_have(title, seen, existing):
                continue
            if self._save_page(title, req, seen):
                saved += 1
        logger.info(f"  Phase 4 (linked pages): {saved} pages saved")
        return saved

    def _phase_web_fallback(
        self, topic: str, req, max_pages: int, seen: Set[str]
    ) -> int:
        saved = 0
        try:
            from src.retrieval.web import DuckDuckGoSearch
        except ImportError:
            return 0
        if saved >= max_pages:
            return 0
        ddg = DuckDuckGoSearch(max_results=10)
        results = ddg.search(topic, max_results=10)
        if not results:
            return 0
        for r in results:
            if saved >= max_pages:
                break
            url = r.get("metadata", {}).get("url", "")
            if not url:
                continue
            text = r.get("text", "")
            if not text or len(text) < 500:
                continue
            heading = r.get("metadata", {}).get("heading", url.split("/")[-1])
            slug = self._sanitize_filename(heading)
            if slug.lower() in seen:
                continue
            seen.add(slug.lower())
            filepath = self._knowledge_dir / f"{slug}.md"
            lines = [
                f"# {heading}",
                f"*Source: [{url}]({url})*",
                f"*Collected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
                "",
                text,
            ]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            saved += 1
            logger.info(f"  Saved web fallback: {slug}.md")
        return saved

    # ── Helpers ──────────────────────────────────────────────────────────

    def _already_have(self, title: str, seen: Set[str], existing: Set[str]) -> bool:
        slug = title.lower().replace(" ", "_")
        return slug in seen or slug in existing

    def _save_page(self, title: str, req, seen: Set[str]) -> bool:
        content = self._wiki_get_content(title, req)
        if not content:
            return False
        if len(content) < 300:
            logger.info(f"    Skipped {title} (too short)")
            return False
        filename = self._sanitize_filename(title) + ".md"
        filepath = self._knowledge_dir / filename
        slug = title.lower().replace(" ", "_")
        seen.add(slug)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"  [OK] Saved: {filename}")
        return True

    def _resolve_title(self, query: str, req) -> Optional[str]:
        try:
            params = {
                "action": "query",
                "titles": query,
                "redirects": 1,
                "format": "json",
            }
            resp = req.get(WIKI_API, params=params, headers=WIKI_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                if pid != "-1":
                    return pdata.get("title", query)
            # Follow redirect
            redirects = data.get("query", {}).get("redirects", [])
            if redirects:
                return redirects[0].get("to", query)
            return None
        except Exception as e:
            logger.warning(f"Title resolution failed for '{query}': {e}")
            return None

    def _wiki_opensearch(self, query: str, req, limit: int = 25) -> List[str]:
        try:
            params = {
                "action": "opensearch",
                "search": query,
                "limit": min(limit, 25),
                "namespace": 0,
                "format": "json",
            }
            resp = req.get(WIKI_API, params=params, headers=WIKI_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data[1] if len(data) > 1 else []
        except Exception as e:
            logger.warning(f"OpenSearch failed: {e}")
            return []

    def _wiki_text_search(self, query: str, req, limit: int = 50) -> List[str]:
        try:
            titles = []
            offset = 0
            while len(titles) < limit:
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": min(50, limit - len(titles)),
                    "sroffset": offset,
                    "srwhat": "text",
                    "format": "json",
                }
                resp = req.get(WIKI_API, params=params, headers=WIKI_HEADERS, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                hits = data.get("query", {}).get("search", [])
                if not hits:
                    break
                for h in hits:
                    titles.append(h.get("title", ""))
                cont = data.get("continue", {})
                offset = cont.get("sroffset", 0)
                if not cont or "sroffset" not in cont:
                    break
                time.sleep(0.3)
            return titles[:limit]
        except Exception as e:
            logger.warning(f"Text search failed: {e}")
            return []

    def _wiki_get_content(self, title: str, req) -> Optional[str]:
        try:
            params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "exlimit": 1,
                "titles": title,
                "format": "json",
            }
            resp = req.get(WIKI_API, params=params, headers=WIKI_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    continue
                extract = page_data.get("extract", "")
                if not extract:
                    continue
                url_title = page_data.get("title", title).replace(" ", "_")
                url = f"https://en.wikipedia.org/wiki/{url_title}"
                lines = [
                    f"# {page_data.get('title', title)}",
                    "",
                    f"*Source: [Wikipedia]({url})*",
                    f"*Collected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
                    "",
                    extract,
                ]
                return "\n".join(lines)
            return None
        except Exception as e:
            logger.warning(f"Content fetch failed for '{title}': {e}")
            return None

    def _wiki_get_links(self, title: str, req, limit: int = 50) -> List[str]:
        try:
            params = {
                "action": "query",
                "generator": "links",
                "titles": title,
                "gpllimit": min(limit, 50),
                "gplnamespace": 0,
                "format": "json",
            }
            resp = req.get(WIKI_API, params=params, headers=WIKI_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            result = []
            for pid, pdata in pages.items():
                if pid == "-1":
                    continue
                result.append(pdata.get("title", ""))
            return result[:limit]
        except Exception as e:
            logger.warning(f"Links fetch failed for '{title}': {e}")
            return []

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        name = re.sub(r'\s+', "_", name.strip())
        return name[:100]
