"""
LangChain tools for Layer 2 crawl agent.
fetch_page, find_links, extract_pdf — each enforces the per-run caps stored in GraphState.
"""
import base64
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from langchain_core.tools import tool

from agents.grant_writer_v2.core.http import fetch, fetch as http_fetch
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.config import v2_settings

logger = get_logger("layer2.tools")

# Maximum chars of page text fed to the agent per page (rest goes to corpus for L3/L4)
MAX_CHARS_PER_PAGE = 30_000

# Tags that suggest grant-related content
GRANT_LINK_KEYWORDS = {
    "grant", "grants", "funding", "apply", "application",
    "program", "programs", "initiative", "award", "awards",
    "opportunity", "opportunities", "eligib", "rfp", "loi",
    "grantmaking", "for-nonprofits",
}

# Path segments that indicate non-grant content — filtered out even if URL contains a keyword
NON_GRANT_PATH_SEGMENTS = {
    "news", "blog", "article", "articles", "ideas", "press", "media",
    "story", "stories", "event", "events", "annual-report", "newsletter",
    "staff", "team", "board", "leadership", "career", "careers", "job", "jobs",
    "donate", "donation", "give", "contact", "about-us", "history",
    "strategic-plan", "report", "reports",
}


def _strip_html(html: str) -> str:
    """Strip HTML tags, scripts, and styles; return readable text."""
    # Remove script and style blocks entirely
    html = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    html = re.sub(r'<[^>]+>', ' ', html)
    # Collapse whitespace
    html = re.sub(r'\s+', ' ', html).strip()
    return html


def _is_same_domain(url: str, base_url: str) -> bool:
    try:
        def _strip_www(netloc: str) -> str:
            return netloc[4:] if netloc.startswith("www.") else netloc
        base_netloc = _strip_www(urlparse(base_url).netloc)
        url_netloc = _strip_www(urlparse(url).netloc)
        return url_netloc == base_netloc or url_netloc.endswith("." + base_netloc)
    except Exception:
        return False


def make_tools(state_ref: dict[str, Any]):
    """
    Build the 3 tools bound to a mutable state_ref dict.
    The graph passes state into this function; tools mutate the dict in-place
    so cap counters stay in sync with GraphState after each tool call.
    """

    @tool
    async def fetch_page(url: str) -> str:
        """Fetch a single web page and return its text content.
        Returns an error string if the page cannot be fetched or caps are hit."""
        if state_ref.get("pages_fetched", 0) >= v2_settings.V2_L2_MAX_PAGES:
            return f"[CAP_HIT] max_pages ({v2_settings.V2_L2_MAX_PAGES}) reached; skipping {url}"
        if state_ref.get("bytes_fetched", 0) >= v2_settings.V2_L2_MAX_BYTES:
            return f"[CAP_HIT] max_bytes ({v2_settings.V2_L2_MAX_BYTES}) reached; skipping {url}"
        if not _is_same_domain(url, state_ref.get("base_url", "")):
            return f"[BLOCKED] {url} is outside foundation domain; skipping"

        visited = state_ref.get("visited_urls", [])
        if url in visited:
            return f"[ALREADY_FETCHED] {url}"

        result = await http_fetch(url)

        if result.get("error"):
            return f"[ERROR] {url}: {result['error']}"

        status_code = result.get("status_code", 0)
        if status_code == 403:
            visited.append(url)
            state_ref["visited_urls"] = visited
            base = state_ref.get("base_url", "")
            return (
                f"[BLOCKED_403] {url} returned 403 (bot protection). "
                f"Try fetching grant subpages directly: "
                f"{base}grants/, {base}funding/, {base}apply/, {base}programs/, {base}grantmaking/"
            )
        if status_code not in (200, 0):
            visited.append(url)
            state_ref["visited_urls"] = visited
            return f"[HTTP_{status_code}] {url} returned {status_code}; skipping"

        content_type = result.get("content_type", "")
        if "pdf" in content_type:
            return f"[PDF] Use extract_pdf tool for {url}"

        text = result.get("text", "")
        bytes_len = result.get("bytes_fetched", len(text.encode()))

        state_ref["pages_fetched"] = state_ref.get("pages_fetched", 0) + 1
        state_ref["bytes_fetched"] = state_ref.get("bytes_fetched", 0) + bytes_len
        visited.append(url)
        state_ref["visited_urls"] = visited

        corpus = state_ref.get("corpus", [])
        corpus.append({"url": url, "text": text, "content_type": content_type, "source": "fetch_page"})
        state_ref["corpus"] = corpus

        # Strip HTML tags before returning to agent so LLM sees readable text, not raw HTML
        clean = _strip_html(text)
        return clean[:MAX_CHARS_PER_PAGE]

    @tool
    def find_links(page_url: str = "") -> str:
        """Extract grant-relevant links from the most recently fetched page (or a specific page URL if provided).
        Returns newline-separated absolute URLs of grant-relevant pages to visit next."""
        effective_base = state_ref.get("base_url", "")
        if not effective_base:
            return "[ERROR] base_url not set"

        # Get text from the most recently fetched page (or the specific page if page_url given)
        corpus = state_ref.get("corpus", [])
        if not corpus:
            return "[NO_PAGES_FETCHED] fetch a page first"

        if page_url:
            pages = [p for p in corpus if p.get("url") == page_url]
            text = pages[-1]["text"] if pages else corpus[-1]["text"]
        else:
            text = corpus[-1]["text"]

        href_pattern = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)
        raw_links = href_pattern.findall(text)

        seen: set[str] = set()
        results: list[str] = []
        visited = set(state_ref.get("visited_urls", []))

        for href in raw_links:
            href = href.strip()
            if not href or href.startswith("#") or href.startswith("mailto:"):
                continue
            absolute = urljoin(effective_base, href)
            if absolute in seen or absolute in visited:
                continue
            if not _is_same_domain(absolute, effective_base):
                continue
            path_lower = urlparse(absolute).path.lower()
            href_lower = href.lower()
            combined = path_lower + " " + href_lower
            # Skip URLs whose path contains a non-grant segment (news, blog, articles, etc.)
            path_segments = set(path_lower.strip("/").split("/"))
            if path_segments & NON_GRANT_PATH_SEGMENTS:
                continue
            if any(kw in combined for kw in GRANT_LINK_KEYWORDS):
                seen.add(absolute)
                results.append(absolute)

        if results:
            return "\n".join(results)

        # No grant links found in static HTML (common on JS-heavy sites).
        # Suggest standard grant subpaths the agent should try directly.
        base = effective_base.rstrip("/")
        visited_set = set(state_ref.get("visited_urls", []))
        fallback_paths = [
            "/grants/", "/work/our-grants/", "/funding/", "/apply/",
            "/programs/", "/grantmaking/", "/grant-opportunities/",
            "/for-nonprofits/", "/initiatives/", "/our-work/",
        ]
        suggestions = [
            f"{base}{p}" for p in fallback_paths
            if f"{base}{p}" not in visited_set
        ]
        if suggestions:
            return (
                "[NO_GRANT_LINKS_FOUND_IN_HTML] This site likely uses JavaScript navigation. "
                "Try these paths directly:\n" + "\n".join(suggestions[:6])
            )
        return "[NO_GRANT_LINKS_FOUND]"

    @tool
    async def extract_pdf(url: str) -> str:
        """Download a PDF and extract its text. Returns the extracted text or an error."""
        if state_ref.get("pdfs_processed", 0) >= v2_settings.V2_L2_MAX_PDFS:
            return f"[CAP_HIT] max_pdfs ({v2_settings.V2_L2_MAX_PDFS}) reached; skipping {url}"
        if state_ref.get("bytes_fetched", 0) >= v2_settings.V2_L2_MAX_BYTES:
            return f"[CAP_HIT] max_bytes reached; skipping {url}"
        if not _is_same_domain(url, state_ref.get("base_url", "")):
            return f"[BLOCKED] {url} is outside foundation domain; skipping"

        visited = state_ref.get("visited_urls", [])
        if url in visited:
            return f"[ALREADY_FETCHED] {url}"

        result = await http_fetch(url, use_cache=True)

        if result.get("error"):
            return f"[ERROR] {url}: {result['error']}"

        raw_bytes = result.get("_raw_bytes")
        if not raw_bytes:
            encoded = result.get("pdf_b64", result.get("text", ""))
            try:
                raw_bytes = base64.b64decode(encoded)
            except Exception:
                return f"[ERROR] Could not decode PDF bytes from {url}"

        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages_text = []
            for page in reader.pages[:50]:
                pages_text.append(page.extract_text() or "")
            text = "\n".join(pages_text)
        except Exception as e:
            return f"[ERROR] PDF extraction failed for {url}: {e}"

        bytes_len = len(raw_bytes)
        state_ref["pdfs_processed"] = state_ref.get("pdfs_processed", 0) + 1
        state_ref["bytes_fetched"] = state_ref.get("bytes_fetched", 0) + bytes_len
        visited.append(url)
        state_ref["visited_urls"] = visited

        corpus = state_ref.get("corpus", [])
        corpus.append({"url": url, "text": text, "content_type": "application/pdf", "source": "extract_pdf"})
        state_ref["corpus"] = corpus

        return text[:MAX_CHARS_PER_PAGE]

    return [fetch_page, find_links, extract_pdf]
