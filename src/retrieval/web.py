"""WebSearchRetriever — internet search via Tavily with rate limiting.

Conforms to BaseRetriever interface. Injects web search results into
the existing evidence pipeline so they reach the Ollama LLM prompt.

Rate limits (Tavily):
  Search:  Dev 100 RPM / Prod 1,000 RPM
  Crawl:   100 RPM
  Research: 20 RPM
On 429, automatically respects retry-after header and retries.
"""

import os
import time
import threading
from collections import deque
from typing import Dict, List, Optional, Tuple
from src.core.logger import get_logger
from .base import BaseRetriever

logger = get_logger(__name__)


def _try_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


class RateLimiter:
    """Sliding-window rate limiter with 429 retry support.

    Tracks request timestamps in a deque and blocks if the window is full.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def acquire(self, retry_after: Optional[float] = None):
        """Block until a request slot is available.

        If retry_after is given (from a 429 response), wait that long
        regardless of the sliding window.
        """
        if retry_after:
            logger.warning(f"Rate limited — waiting {retry_after:.0f}s")
            time.sleep(retry_after)
            return

        while True:
            self._lock.acquire()
            now = time.time()
            cutoff = now - self._window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self._max:
                self._timestamps.append(now)
                self._lock.release()
                return

            sleep_until = self._timestamps[0] + self._window
            wait = sleep_until - now
            self._lock.release()
            if wait > 0:
                logger.info(
                    f"Rate limit reached ({self._max}/{self._window}s) "
                    f"— waiting {wait:.1f}s"
                )
                time.sleep(wait)

    @property
    def available(self) -> int:
        self._lock.acquire()
        try:
            now = time.time()
            cutoff = now - self._window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return max(0, self._max - len(self._timestamps))
        finally:
            self._lock.release()

    @property
    def stats(self) -> Dict:
        self._lock.acquire()
        try:
            now = time.time()
            cutoff = now - self._window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return {
                "used": len(self._timestamps),
                "max": self._max,
                "window_seconds": self._window,
                "available": max(0, self._max - len(self._timestamps)),
            }
        finally:
            self._lock.release()


def _validate_https_url(url: str) -> str:
    """Validate URL uses HTTPS, raising ValueError if not."""
    if not url.startswith("https://"):
        raise ValueError(f"URL must use HTTPS scheme: {url}")
    return url


class WebSearchRetriever(BaseRetriever):
    """Retrieves evidence from internet search results (Tavily).

    Requires TAVILY_API_KEY environment variable.

    Rate-limited to 100 RPM (development tier) by default.
    On 429 response, automatically reads retry-after header and waits.
    """

    def __init__(self, api_key: Optional[str] = None,
                 api_url: Optional[str] = None,
                 top_k: int = 5,
                 max_results_per_query: int = 5,
                 max_rpm: int = 100):
        self._api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        raw_url = api_url or os.environ.get(
            "SEARCH_API_URL",
            "https://api.tavily.com/search",
        )
        self._api_url = _validate_https_url(raw_url)
        self._top_k = top_k
        self._max_results = max_results_per_query
        self._ready = bool(self._api_key)
        self._cache: Dict[str, List[Dict]] = {}
        self._limiter = RateLimiter(max_requests=max_rpm, window_seconds=60)
        self._session: Optional[Any] = None

        if self._ready:
            logger.info(
                f"WebSearchRetriever ready — Tavily (max {self._max_results} results, "
                f"{max_rpm} RPM)"
            )
        else:
            logger.info(
                "WebSearchRetriever: no API key found. "
                "Set TAVILY_API_KEY env var to enable. Skipping."
            )

    def _get_session(self):
        """Get or create a requests Session for connection pooling."""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({"Content-Type": "application/json"})
        return self._session

    def index_chunks(self, chunks: List[Dict]):
        pass

    def is_ready(self) -> bool:
        return self._ready

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        if not self._ready:
            return []
        k = top_k or self._top_k

        cache_key = f"{query}:{k}"
        if cache_key in self._cache:
            logger.info(f"Web search cache hit for: {query[:60]}")
            return self._cache[cache_key]

        results = self._search_with_retry(query, k)
        self._cache[cache_key] = results
        return results

    def _search_with_retry(self, query: str, top_k: int,
                            max_retries: int = 3) -> List[Dict]:
        """Search with rate-limit acquisition and 429 retry logic."""
        import requests as _req
        if not _try_import("requests"):
            logger.warning("requests not installed — cannot perform web search")
            return []

        last_error = ""
        for attempt in range(1, max_retries + 1):
            self._limiter.acquire()

            try:
                payload = {
                    "api_key": self._api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": min(top_k, self._max_results),
                    "include_answer": False,
                    "include_raw_content": False,
                }
                session = self._get_session()
                resp = session.post(
                    self._api_url,
                    json=payload,
                    timeout=15,
                )

                if resp.status_code == 401:
                    logger.warning("Tavily API key rejected (401) — skipping")
                    return []

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("retry-after", 60))
                    logger.warning(
                        f"429 rate limited (attempt {attempt}/{max_retries}) — "
                        f"retry-after: {retry_after:.0f}s"
                    )
                    if attempt < max_retries:
                        self._limiter.acquire(retry_after=retry_after)
                        continue
                    logger.error("Max retries exceeded for rate limit")
                    return []

                resp.raise_for_status()
                data = resp.json()
                raw_results = data.get("results", [])
                chunks = []
                for i, r in enumerate(raw_results):
                    title = r.get("title", "")
                    content = r.get("content", "")
                    url = r.get("url", "")
                    score = r.get("score", 1.0 - (i * 0.1))
                    if not content:
                        continue
                    chunks.append({
                        "text": f"[Web: {title}]\n{content}",
                        "metadata": {
                            "source": f"web:{url}",
                            "heading": title,
                            "url": url,
                            "score": max(score, 0.1),
                        },
                        "score": max(score, 0.1),
                        "rerank_score": max(score, 0.1),
                    })
                logger.info(
                    f"Web search '{query[:60]}' → {len(chunks)} results "
                    f"(attempt {attempt})"
                )
                return chunks

            except _req.exceptions.Timeout:
                last_error = "timeout"
                logger.warning(
                    f"Web search timeout (attempt {attempt}/{max_retries})"
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue

            except _req.exceptions.RequestException as e:
                last_error = str(e)
                logger.warning(
                    f"Web search failed (attempt {attempt}/{max_retries}): {e}"
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue

        logger.error(f"Web search failed after {max_retries} retries: {last_error}")
        return []

    def get_rate_stats(self) -> Dict:
        return self._limiter.stats


class DuckDuckGoSearch:
    """DuckDuckGo web search — no API key required.

    Uses the public HTML endpoint and parses results with BeautifulSoup.
    Rate-limited with a 1-second delay between queries.
    """

    def __init__(self, max_results: int = 5):
        self._max_results = max_results
        self._cache: Dict[str, List[Dict]] = {}
        self._last_request = 0.0

    def is_ready(self) -> bool:
        return True

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        k = max_results or self._max_results
        cache_key = f"ddg:{query}:{k}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        results = self._fetch(query, k)
        self._cache[cache_key] = results
        return results

    def _fetch(self, query: str, max_results: int) -> List[Dict]:
        import requests as _req
        now = time.time()
        since_last = now - self._last_request
        if since_last < 1.0:
            time.sleep(1.0 - since_last)

        try:
            from bs4 import BeautifulSoup
            session = _req.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            resp = session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                timeout=15,
            )
            resp.raise_for_status()
            self._last_request = time.time()

            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for result in soup.select(".result")[:max_results]:
                link_el = result.select_one(".result__a")
                snippet_el = result.select_one(".result__snippet")
                if not link_el:
                    continue
                title = link_el.get_text(strip=True)
                href_el = link_el.get("href", "")
                url = ""
                if "uddg=" in str(href_el):
                    from urllib.parse import parse_qs, urlparse
                    parsed = urlparse(str(href_el))
                    qs = parse_qs(parsed.query)
                    url = qs.get("uddg", [""])[0]
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                text = f"[Web: {title}]\n{snippet}" if snippet else f"[Web: {title}]"
                if not title and not snippet:
                    continue
                results.append({
                    "text": text,
                    "metadata": {
                        "source": f"web:duckduckgo:{url or title}",
                        "heading": title,
                        "url": url,
                        "score": max(1.0 - (len(results) * 0.15), 0.1),
                    },
                    "score": max(1.0 - (len(results) * 0.15), 0.1),
                    "rerank_score": max(1.0 - (len(results) * 0.15), 0.1),
                })

            logger.info(f"DuckDuckGo '{query[:60]}' → {len(results)} results")
            return results

        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []


def search_web(topic: str, max_results_per_source: int = 5,
               use_tavily: bool = False) -> List[Dict]:
    """Multi-backend web search.

    DuckDuckGo is always used (free, no API key required).
    Tavily is only used when explicitly opted in via use_tavily=True
    (costs API credits).

    Returns merged, deduplicated chunks ready for fact extraction.
    """
    all_chunks: List[Dict] = []

    if use_tavily:
        tavily = WebSearchRetriever(max_results_per_query=max_results_per_source)
        if tavily.is_ready():
            try:
                tavily_chunks = tavily.retrieve(topic, max_results_per_source)
                all_chunks.extend(tavily_chunks)
                logger.info(f"Tavily returned {len(tavily_chunks)} results")
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")
    else:
        logger.info("Tavily disabled (use --tavily to enable)")

    ddg = DuckDuckGoSearch(max_results=max_results_per_source)
    ddg_results = ddg.search(topic, max_results_per_source)
    all_chunks.extend(ddg_results)
    logger.info(f"DuckDuckGo returned {len(ddg_results)} results")

    seen = set()
    deduped = []
    for ch in all_chunks:
        text = ch.get("text", "")[:200]
        if text and text not in seen:
            seen.add(text)
            deduped.append(ch)

    deduped.sort(key=lambda x: x.get("rerank_score", x.get("score", 0)), reverse=True)
    logger.info(f"Web search total: {len(all_chunks)} raw → {len(deduped)} deduplicated")
    return deduped


class MultiSourceRetriever(BaseRetriever):
    """Combines local + web retrieval into a single retriever.

    Queries both the local HybridRetriever and WebSearchRetriever,
    merges results with deduplication, and returns the combined set.
    """

    def __init__(self, local_retriever: BaseRetriever,
                 web_retriever: Optional[WebSearchRetriever] = None):
        self._local = local_retriever
        self._web = web_retriever or WebSearchRetriever()
        self._ready = local_retriever.is_ready() or self._web.is_ready()

    def index_chunks(self, chunks: List[Dict]):
        self._local.index_chunks(chunks)

    def is_ready(self) -> bool:
        return self._ready

    def retrieve(self, query: str, top_k: int = 8) -> List[Dict]:
        local_results = self._local.retrieve(query, top_k) if self._local.is_ready() else []

        web_results = []
        if self._web.is_ready():
            web_k = max(3, top_k // 3)
            web_results = self._web.retrieve(query, web_k)

        seen_texts = set()
        merged = []
        for r in local_results + web_results:
            text = r.get("text", "")[:200]
            if text and text not in seen_texts:
                seen_texts.add(text)
                merged.append(r)

        merged.sort(key=lambda x: x.get("rerank_score", x.get("score", 0)), reverse=True)
        merged = merged[:top_k]

        if web_results:
            logger.info(
                f"MultiSource: {len(local_results)} local + {len(web_results)} web "
                f"→ {len(merged)} merged"
            )
        return merged
