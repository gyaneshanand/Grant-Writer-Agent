from bs4 import BeautifulSoup
import requests
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from urllib.parse import urljoin, urlparse
from langchain.prompts import ChatPromptTemplate
from agents.llm_factory import create_pipeline_llm, log_llm_usage, DEFAULT_EXTRACT_MODEL
from pydantic import BaseModel
import re
import json
import trafilatura
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Speed knobs. The pipeline's purpose is scrape -> extract -> store; each page
# costs one LLM call, so the page cap is the single biggest latency lever.
MAX_GRANT_PAGES = int(os.getenv("MAX_GRANT_PAGES", 10))
PAGE_WORKERS = int(os.getenv("PIPELINE_PAGE_WORKERS", 8))
# Second crawl wave: program sub-pages linked from wave-1 pages, not the
# homepage (e.g. /capacity-building-grant-program/ linked from /grantmaking/).
# These carry the specific award caps and deadlines. 0 disables the wave.
WAVE2_PAGES = int(os.getenv("PIPELINE_WAVE2_PAGES", 8))

# Honest crawler identity. Spoofed browser UAs trip WAF TLS-fingerprint checks,
# and the python-requests default UA is blocked outright by some hosts (403).
REQUEST_HEADERS = {
    "User-Agent": os.getenv("BOT_USER_AGENT", "TheGrantPortalBot/1.0 (+https://www.thegrantportal.com)"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Keywords that mark a link as grant-related. Shared by static (BeautifulSoup)
# and Jina (markdown) link discovery so both paths select the same pages.
GRANT_LINK_KEYWORDS = [
    "grant", "apply", "fund", "fellowship", "opportunity", "scholarship",
    "award", "funding", "faq", "eligibility", "criteria", "how-to-apply",
    "guidelines", "about", "programs", "opportunities",
    # foundation program pages that don't say "grant" in the URL
    # (e.g. /strategic-restructuring-initiative/, /management-assistance/)
    "initiative", "assistance", "support", "contact",
    # staff/team pages carry the email addresses that contact pages only link to
    "staff", "team",
]

# Per-page cap on the raw text handed to the writers. Gives them the real page
# instead of only the 13-field extraction, while keeping the prompt bounded.
PAGE_TEXT_CHARS = int(os.getenv("PIPELINE_PAGE_TEXT_CHARS", 12000))

# Pages with less readable text than this skip the LLM extraction call entirely
# (nav shells, cookie walls, stub pages). Their contact signals and sub-links
# are still harvested — only the paid model call is skipped.
MIN_PAGE_CHARS = int(os.getenv("PIPELINE_MIN_PAGE_CHARS", 500))

# Cap on text sent into one extraction call. Jina can return 40k+ chars for
# link-farm pages; a grant page's substance fits well inside this cap, and
# input past it mostly bought tokens, not fields.
EXTRACT_INPUT_CHARS = int(os.getenv("PIPELINE_EXTRACT_INPUT_CHARS", 20000))

# Jina Reader (JS-render fallback). Same key/env the v2 pipeline uses. When set,
# JS-rendered SPA pages that static fetching can't read are recovered as markdown.
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_TIMEOUT = int(os.getenv("JINA_TIMEOUT", 60))


def _strip_html_to_text(html: str) -> str:
    """Crude readable-text estimate: drop script/style blocks and tags."""
    stripped = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html,
                      flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r'<[^>]+>', ' ', stripped)
    return re.sub(r'\s+', ' ', stripped).strip()


def _is_js_rendered(html: str, extracted_text=None) -> bool:
    """Heuristic: does this page look like a JS-rendered SPA shell whose real
    content never arrived in the static HTML? Only consulted when the static
    extraction is already thin, to avoid spending a Jina call on real pages."""
    if not html:
        return False
    # When the caller has no trafilatura text (link-discovery path), estimate
    # readable text from the raw HTML — otherwise every large static page would
    # be misclassified as an SPA and burn a Jina call.
    text_len = len(extracted_text) if extracted_text is not None else len(_strip_html_to_text(html))
    # Enough readable text already — treat it as a real, fully-static page.
    if text_len >= 1000:
        return False
    # Thin/empty extraction — decide whether the raw HTML is an SPA shell.
    if html.count("href=") <= 5:  # classic SPA: almost no static anchors
        return True
    if len(html) > 50_000:  # big JS bundle, little readable text
        return True
    return False


def fetch_via_jina(url: str):
    """Fetch a URL through Jina Reader (r.jina.ai), which renders JS and returns
    clean markdown. Returns the text, or None on any failure. Kept sync so it
    runs inside this pipeline's existing thread pool."""
    if not JINA_API_KEY:
        return None
    try:
        resp = requests.get(
            f"https://r.jina.ai/{url}",
            timeout=JINA_TIMEOUT,
            headers={
                "Authorization": f"Bearer {JINA_API_KEY}",
                "Accept": "text/plain",
                "X-Return-Format": "markdown",
                "X-No-Cache": "true",
            },
        )
        if resp.status_code == 200 and resp.text.strip():
            return resp.text
        print(f"⚠️ Jina Reader returned {resp.status_code} for {url}")
    except Exception as e:
        print(f"❌ Jina Reader error for {url}: {e}")
    return None


_EMAIL_RE = re.compile(r"[A-Za-z0-9][\w.+-]*@[A-Za-z0-9][\w-]*(?:\.[A-Za-z]{2,})+")
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
# Cloudflare email obfuscation: emails are XOR-encoded hex in data-cfemail
# attributes / email-protection#... links and only decoded by client-side JS,
# so a plain fetch never sees them as text.
_CFEMAIL_RE = re.compile(r'(?:data-cfemail="|/cdn-cgi/l/email-protection#)([a-fA-F0-9]{8,})')


def _decode_cfemail(hexstr: str):
    """Decode a Cloudflare-obfuscated email (first byte = XOR key)."""
    try:
        data = bytes.fromhex(hexstr)
        return bytes(b ^ data[0] for b in data[1:]).decode("utf-8")
    except Exception:
        return None


# Placeholder emails baked into site templates and form builders — never real.
_JUNK_EMAIL_PARTS = (
    "example.", "@domain.", "@email.", "@yourdomain", "@test.", "@sentry",
    "user@", "name@", "someone@", "email@", "your@", "@2x",
)


def _extract_contact_signals(html: str) -> str:
    """Harvest emails, phone numbers and addresses from raw HTML.

    Contact details usually live where text extraction never looks: mailto:/tel:
    hrefs, Cloudflare-obfuscated spans, and JSON-LD/site metadata blocks inside
    <script> tags (Squarespace, Wix and WordPress all publish the org's address
    and phone there). Harvest them and append them to the page text as plain
    facts so the writers always see them.
    """
    if not html:
        return ""
    emails = {
        e.rstrip(".")
        for e in _EMAIL_RE.findall(html)
        if not e.lower().endswith(_IMAGE_SUFFIXES)
        and not any(j in e.lower() for j in _JUNK_EMAIL_PARTS)
    }
    # Cloudflare-obfuscated emails (JS-decoded in a real browser, invisible to a
    # plain fetch) — decode them server-side.
    for hexstr in _CFEMAIL_RE.findall(html):
        decoded = _decode_cfemail(hexstr)
        if decoded and _EMAIL_RE.fullmatch(decoded) and not any(j in decoded.lower() for j in _JUNK_EMAIL_PARTS):
            emails.add(decoded)

    phones = set(re.findall(r'href=["\']tel:([+\d][\d\s().-]{6,})["\']', html, re.IGNORECASE))
    # Structured-data phone: "telephone":"(203) 493-1088"
    for m in re.findall(r'"telephone"\s*:\s*"([^"]{7,25})"', html):
        if re.search(r"\d{3}", m):
            phones.add(m)

    # Structured-data postal address: "address":"P.O. Box 7266\nWilton, Ct. 06897..."
    addresses = set()
    for m in re.findall(r'"address"\s*:\s*"([^"]{10,200})"', html):
        cleaned = m.replace("\\n", ", ").strip()
        if re.search(r"\d", cleaned):  # real addresses carry a number
            addresses.add(cleaned)

    parts = []
    if emails:
        parts.append("Email addresses found on this page: " + ", ".join(sorted(emails)))
    if phones:
        parts.append("Telephone numbers found on this page: " + ", ".join(sorted(p.strip() for p in phones)))
    if addresses:
        parts.append("Mailing/physical address found in this page's metadata: " + " | ".join(sorted(addresses)))
    return "\n".join(parts)


def _mine_grant_links(html: str, page_url: str):
    """Keyword-matched, same-domain links from a fetched page's HTML.

    Feeds the second crawl wave: program detail pages are usually linked from a
    grantmaking overview page rather than the homepage, and they hold the award
    caps and deadlines the homepage never mentions.
    """
    if not html:
        return []
    base_host = urlparse(page_url).netloc.lower().removeprefix("www.")
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        l = urljoin(page_url, a["href"]).split("#")[0]
        if not l.startswith("http") or l in seen:
            continue
        host = urlparse(l).netloc.lower().removeprefix("www.")
        if host != base_host and not host.endswith("." + base_host):
            continue
        if any(k in l.lower() for k in GRANT_LINK_KEYWORDS):
            seen.add(l)
            out.append(l)
    return out


def _extract_grant_links_from_markdown(markdown: str, base_url: str = None):
    """Pull absolute grant-related links out of Jina markdown output.

    Restricted to the foundation's own host (subdomains allowed) — Jina links are
    all absolute, so without this filter keyword-matching links to social media
    or other foundations would enter the crawl.
    """
    base_host = urlparse(base_url).netloc.lower().removeprefix("www.") if base_url else None
    links = re.findall(r'\]\((https?://[^)\s]+)\)', markdown or "")
    seen, out = set(), []
    for l in links:
        if base_host:
            host = urlparse(l).netloc.lower().removeprefix("www.")
            if host != base_host and not host.endswith("." + base_host):
                continue
        if any(k in l.lower() for k in GRANT_LINK_KEYWORDS) and l not in seen:
            seen.add(l)
            out.append(l)
    return out

# Step 1: Schema
class Grant(BaseModel):
    grant_name: str = "Not specified"
    funding_priorities: str = "Not specified"
    types_of_grant: str = "Not specified"
    eligibility_criteria: str = "Not specified"
    eligible_applicants: list = []
    eligible_locations: str = "Not specified"
    grant_amount_range: str = "Not specified"
    grant_amount: str = "Not specified"
    proposal_deadline: str = "Not specified"
    # Full application window as prose (open/close dates, times, cycles,
    # cutoffs). proposal_deadline stays a single machine-parseable date —
    # TGP runs Carbon::parse() on it for the deadline column.
    deadline_details: str = "Not specified"
    recurrence: str = "Not specified"
    contact_info: dict = {"email": "Not specified", "phone": "Not specified", "address": "Not specified"}
    organization_info: str = "Not specified"
    grant_summary: str = "Not specified"
    grant_url: str = "Not specified"

# Step 2: Scrape pages
def scrape_site(url):
    print(f"🔍 Starting to scrape site: {url}")
    r = requests.get(url, timeout=15, headers=REQUEST_HEADERS)
    print(f"✅ Successfully fetched main page, status code: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    links = [a['href'] for a in soup.find_all('a', href=True)]
    print(f"📄 Found {len(links)} total links on the page")
    
    # Filter and fix relative URLs
    grant_links = []
    for l in links:
        if any(x in l.lower() for x in GRANT_LINK_KEYWORDS):
            original_link = l
            # Resolve relative URLs against the page URL. String concatenation
            # here built broken paths whenever the base URL had a path segment
            # (e.g. /how-to-apply + /grants -> /how-to-apply/grants -> 404).
            # Fragments are stripped: "#scholarships-grants" is the same page,
            # and anchor "links" were burning crawl slots on duplicate fetches.
            l = urljoin(url, l).split('#')[0]
            if not l.startswith('http') or not l.rstrip('/'):
                continue  # mailto:, tel:, javascript:, bare-fragment etc.
            grant_links.append(l)
            print(f"🎯 Found potential grant link: {original_link} -> {l}")

    # remove duplicates
    grant_links = list(set(grant_links))

    # Restrict page count to keep latency bounded — every page costs one LLM call.
    # Smart selection to prioritize likely grant pages like "grants", "apply", "funding". Always include main URL.
    prioritized_links = []
    keywords = ["grant", "apply", "fund", "fellowship", "opportunity", "scholarship", "award", "funding"]
    for kw in keywords:
        for gl in grant_links:
            if kw in gl.lower() and gl not in prioritized_links:
                prioritized_links.append(gl)
    # Remaining keyword-matched links (about, contact, initiative, assistance,
    # eligibility, faq...) fill the leftover slots. These were silently dropped
    # before, which lost program pages (e.g. /strategic-restructuring-initiative/)
    # and the contact page that carries the foundation's email and phone.
    for gl in grant_links:
        if gl not in prioritized_links:
            prioritized_links.append(gl)
    grant_links = prioritized_links[:MAX_GRANT_PAGES]

    # SPA fallback: if static HTML yielded almost no grant links, or the page
    # looks JS-rendered, ask Jina Reader for the rendered page and mine its
    # markdown links. Without this, single-page-app foundation sites collapse to
    # just the main URL and the whole pipeline sees one near-empty page.
    if JINA_API_KEY and (len(grant_links) <= 1 or _is_js_rendered(r.text, None)):
        print(f"🔁 Sparse/JS-rendered links at {url}, trying Jina Reader for link discovery...")
        jina_md = fetch_via_jina(url)
        if jina_md:
            added = 0
            for jl in _extract_grant_links_from_markdown(jina_md, base_url=url):
                if jl not in grant_links:
                    grant_links.append(jl)
                    added += 1
            grant_links = grant_links[:MAX_GRANT_PAGES]
            print(f"✨ Jina link discovery added {added} links, total now {len(grant_links)}")

    # Always include the main URL
    if url not in grant_links:
        grant_links.append(url)
        print(f"🎯 Added main URL to grant links: {url}")

    print(f"✨ Total grant-related links found: {len(grant_links)}")
    # print the list of links
    print("📋 Grant-related links:")
    for gl in grant_links:
        print(f"   - {gl}")

    return grant_links

def go_one_level_deeper(grant_links, main_url):
    new_links = []
    for gl in grant_links:
        if gl != main_url:
            sub_links = scrape_site(gl)
            new_links.extend(sub_links)
    return grant_links + new_links

# Step 2.5: Extract HTML content and main article text
def get_html_content_and_extract_text(url):
    """
    Fetch HTML content from URL and extract main article text using trafilatura.
    Returns both raw HTML and cleaned text content.
    """
    print(f"🌐 Fetching content from: {url}")
    
    try:
        response = requests.get(url, timeout=10, headers=REQUEST_HEADERS)
        print(f"✅ Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch page, status: {response.status_code}")
            return None, None
            
        html_content = response.text
        print(f"📝 Raw HTML content length: {len(html_content)} characters")
        
        # Extract main article text using trafilatura
        print("🔧 Extracting main article text with trafilatura...")
        extracted_text = trafilatura.extract(html_content)

        if extracted_text:
            print(f"✨ Extracted clean text length: {len(extracted_text)} characters")
        else:
            print("⚠️ Trafilatura extraction returned nothing")

        # JS-render fallback: an SPA shell yields little/no trafilatura text.
        # Jina Reader renders the page server-side and returns clean markdown.
        if JINA_API_KEY and _is_js_rendered(html_content, extracted_text):
            print(f"🔁 JS-rendered page detected at {url}, falling back to Jina Reader...")
            jina_text = fetch_via_jina(url)
            if jina_text and len(jina_text) > len(extracted_text or ""):
                print(f"✨ Jina Reader returned {len(jina_text)} chars (was {len(extracted_text or '')})")
                extracted_text = jina_text

        # Last resort so downstream never receives None. Tag-stripped, never
        # raw HTML — markup noise wastes the extraction call's input budget.
        if not extracted_text:
            print("⚠️ No clean text available, falling back to tag-stripped HTML")
            extracted_text = _strip_html_to_text(html_content)

        # Re-attach contact details that live only in mailto:/tel: hrefs, which
        # text extraction otherwise drops.
        contact_signals = _extract_contact_signals(html_content)
        if contact_signals and contact_signals not in extracted_text:
            print(f"📇 Harvested contact signals from markup: {contact_signals[:120]}")
            extracted_text = f"{extracted_text}\n\n{contact_signals}"

        return html_content, extracted_text
        
    except requests.exceptions.Timeout:
        print("⏰ Request timed out")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {str(e)}")
        return None, None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None, None

# Step 3: Extract info with LLM
def extract_grant_info(page_text):
    print("🤖 Starting LLM extraction process...")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")
    
    # Extraction is high-volume field-pulling — it runs on the cheap tier.
    # The two writer calls stay on PIPELINE_MODEL.
    llm = create_pipeline_llm(
        temperature=0.3,
        openai_api_key=openai_api_key,
        model=os.getenv("PIPELINE_EXTRACT_MODEL", DEFAULT_EXTRACT_MODEL),
    )
    print("🔗 Connected to OpenAI API")

    prompt = ChatPromptTemplate.from_template("""
    You are an expert grant writer and researcher. You will help extract detailed information about grants from web page text.

    Extract the following fields about ACTIVE grants only from this page. Please think and reason that this is a actual grant/scholarship opportunity.

    ACTIVE means any of: currently accepting applications; awarded annually or on a recurring cycle; or a future/announced application window (e.g. "applications will open February 1"). A grant whose next window has not opened yet IS active — include it. Only exclude a grant when it is permanently closed, discontinued, by invitation only, or all of its deadlines are in the past with no recurrence.

    1. Grant Name - the grant or funding opportunity name if available elase try to create a suitable name based on the content if not explicitly mentioned.
    2. Funding priorities and interests
    3. Types of grant
    4. Eligibility criteria - include every stated requirement: GPA minimums, citizenship, gender, age, enrollment status, residency, accreditation requirements
    5. Eligible applicants ( nonprofits / individuals / small businesses). Identify if nonprofit organizations or small businesses or individuals are eligible for the grant.
    6. Eligible funding locations
    7. Range of grant amount - format STRICTLY as "$MIN - $MAX" with a hyphen (e.g. "$750 - $10,000"); this string is machine-parsed. If only a single amount or cap exists, leave this as "Not specified" and use field 8.
    8. Specific grant funding amount - a single dollar figure as written (e.g. "$5,000" or "$80,000"); machine-parsed. If the page states only a range, leave "Not specified".
    9. Proposal deadline - the SINGLE next upcoming due date, machine-parseable: "Month DD, YYYY" (e.g. "September 30, 2026"), or "Month DD" when the page gives a recurring date without a year. Never write sentences here. If no dated deadline exists, "Not specified".
    9b. Deadline details - the FULL application window as written on the page: opening date, due date and time, every cycle's dates, and any cutoff conditions (e.g. "closes after the first 250 applications"). Sentences allowed here.
    10. Annual or recurring
    11. Contact info (telephone, email, physical address)
    12. Organization information about the grant provider. Include the organization’s name, about us, organization’s mission or focus, background information, types of grants if available.
    13. 300 words summary of the grant which should be comprehensive and cover all important aspects of the grant. Keep this to the point and avoid fluff.

    Include as much detail as possible in each field. Please be very sure that the grant is ACTIVE and accepting applications. If the grant is closed or not currently accepting applications do not include it.
    Avoid making up information if not available on the page.

    Here is the Text from the page: {text}

    Return ONLY valid JSON in this exact format:
    {{
        "grant_name": "string",
        "funding_priorities": "string", 
        "types_of_grant": "string",
        "eligibility_criteria": "string",
        "eligible_applicants": ["string1", "string2"],
        "eligible_locations": "string",
        "grant_amount_range": "string",
        "grant_amount": "string",
        "proposal_deadline": "string",
        "deadline_details": "string",
        "recurrence": "string",
        "contact_info": {{"email": "string", "phone": "string", "address": "string"}},
        "organization_info": "string",
        "grant_summary": "string",

    }}
    """)
    
    if len(page_text) > EXTRACT_INPUT_CHARS:
        print(f"✂️ Extraction input truncated {len(page_text)} -> {EXTRACT_INPUT_CHARS} chars")
        page_text = page_text[:EXTRACT_INPUT_CHARS]
    print(f"📝 Processing text of length: {len(page_text)} characters")
    response = llm.invoke(prompt.format(text=page_text))
    log_llm_usage("extract", response)
    result = response.content
    print("✅ Received response from LLM")
    print(f"📤 Raw LLM response: {result[:200]}...")
    
    # Clean JSON from markdown code blocks if present
    if result.startswith('```json'):
        result = result.strip('```json').strip('```').strip()
        print("🧹 Cleaned JSON markdown formatting")
    elif result.startswith('```'):
        result = result.strip('```').strip()
        print("🧹 Cleaned markdown formatting")
    
    try:
        print("🔍 Attempting to parse JSON...")
        grant = Grant.model_validate_json(result)
        print("✅ Successfully parsed grant information")
        
        # Check if this is a valid grant (has meaningful content). The model
        # sometimes "names" a non-grant page instead of returning empty
        # ("No active grant opportunity identified") — treat those as no-grant.
        name = (grant.grant_name or "").strip()
        if not name or name.lower().startswith(("not specified", "no active", "no grant", "none", "unknown", "n/a")):
            print("⚠️ No valid grant information found on this page - skipping")
            return None
            
        return grant
    except Exception as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"📄 Raw result: {result}")
        
        # Try to create a default Grant object if JSON is completely empty
        try:
            if result.strip() in ['{}', '']:
                print("📝 Empty response detected - no grant information on this page")
                return None
            else:
                print("🔄 Attempting to create default Grant object...")
                return Grant()
        except Exception as fallback_error:
            print(f"❌ Fallback creation failed: {fallback_error}")
            return None

def _process_page(p, seen_text_hashes=None, hash_lock=None):
    """Fetch one page and run LLM extraction.

    Returns {"grant": dict|None, "contact": str, "links": [str]} — contact
    signals and sub-links are kept even when the page yields no grant, so a
    contact page's email or an overview page's program links are never lost.

    seen_text_hashes/hash_lock (shared per run) dedupe by CONTENT: aliased URLs
    (www vs bare, /index.html vs /) serve identical text, and each duplicate
    extraction is a paid LLM call.

    Runs inside the thread pool — both the HTTP fetch and the LLM call are
    I/O-bound, so threads overlap them across pages.
    """
    result = {"grant": None, "contact": "", "links": []}
    try:
        if not p.startswith('http'):
            print(f"⚠️ Skipping invalid URL: {p}")
            return result

        html_content, extracted_text = get_html_content_and_extract_text(p)
        result["contact"] = _extract_contact_signals(html_content or "")
        result["links"] = _mine_grant_links(html_content or "", p)

        if not extracted_text:
            print(f"❌ Failed to extract content from: {p}")
            return result

        if len(extracted_text.strip()) < MIN_PAGE_CHARS:
            print(f"⏭️ Page too thin ({len(extracted_text.strip())} chars) — skipping LLM extraction: {p}")
            return result

        if seen_text_hashes is not None:
            text_hash = hashlib.sha1(extracted_text.strip().encode("utf-8", "ignore")).hexdigest()
            with hash_lock:
                if text_hash in seen_text_hashes:
                    print(f"♻️ Identical content already extracted this run — skipping LLM call: {p}")
                    return result
                seen_text_hashes.add(text_hash)

        grant = extract_grant_info(extracted_text)

        if grant is None:
            print(f"⏭️ No grant information found on {p} - skipping")
            return result

        grant.grant_url = p  # Add the URL to the grant data
        print(f"🎯 Grant extracted: {grant.grant_name}")

        if "closed" in grant.proposal_deadline.lower():
            print(f"❌ Skipped closed grant (deadline: {grant.proposal_deadline})")
            return result

        grant_dict = grant.model_dump()
        # Carry the real page text so the writers work from the source, not just
        # the 13-field extraction. Stripped from the API response later; capped so
        # the downstream writer prompts stay bounded.
        grant_dict["source_page_text"] = (extracted_text or "")[:PAGE_TEXT_CHARS]
        print(f"✅ Added grant to results (deadline: {grant.proposal_deadline})")
        result["grant"] = grant_dict
        return result

    except Exception as e:
        print(f"❌ Error processing {p}: {str(e)}")
        return result


def _norm_url(u: str) -> str:
    """Normalize for URL dedup: case, scheme, www. prefix, trailing slash."""
    u = u.strip().lower().rstrip("/")
    u = re.sub(r"^https?://", "", u)
    return u.removeprefix("www.")


CONTACT_BLOCK_HEADER = "CONTACT DETAILS COLLECTED ACROSS THIS FOUNDATION'S WEBSITE:"


# Step 4: Run pipeline
def run_pipeline(url):
    print(f"🚀 Starting pipeline for URL: {url}")
    run_start = time.monotonic()
    pages = scrape_site(url)
    print(f"📊 Processing {len(pages)} pages for grant information ({PAGE_WORKERS} workers)...")

    root_host = urlparse(url).netloc.lower().removeprefix("www.")
    seen_hashes, hash_lock = set(), threading.Lock()
    seen_urls = {_norm_url(p) for p in pages}
    results = []
    wave2_count = 0

    # Pages are independent: fetch + extract them concurrently. The waves also
    # overlap — a wave-2 sub-page (program detail page found on a wave-1 page)
    # is submitted the moment its parent completes instead of after the whole
    # first wave, so wave 2 costs no extra wall-clock batch.
    with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as pool:
        pending = {pool.submit(_process_page, p, seen_hashes, hash_lock) for p in pages}
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                r = fut.result()
                results.append(r)
                for l in r["links"]:
                    if wave2_count >= WAVE2_PAGES:
                        break
                    # Wave 2 never leaves the foundation's own site: links mined
                    # from an external wave-1 page (another org's site) would
                    # otherwise pull in that org's unrelated pages.
                    host = urlparse(l).netloc.lower().removeprefix("www.")
                    if host != root_host and not host.endswith("." + root_host):
                        continue
                    if _norm_url(l) in seen_urls:
                        continue
                    seen_urls.add(_norm_url(l))
                    wave2_count += 1
                    print(f"🌊 Wave 2 ({wave2_count}/{WAVE2_PAGES}): {l}")
                    pending.add(pool.submit(_process_page, l, seen_hashes, hash_lock))

    grants = [r["grant"] for r in results if r["grant"]]

    # Site-wide contact details: pages that yield no grant (contact/about pages)
    # still carry the foundation's email and phone. Merge every page's harvested
    # signals and append them to each grant's source text so the description
    # writer always has real contact facts to work with.
    contact_lines = []
    for r in results:
        for line in (r["contact"] or "").splitlines():
            if line and line not in contact_lines:
                contact_lines.append(line)
    if contact_lines and grants:
        contact_block = CONTACT_BLOCK_HEADER + "\n" + "\n".join(contact_lines)
        print(f"📇 Site-wide contact block: {contact_block[:200]}")
        for g in grants:
            if contact_block not in g.get("source_page_text", ""):
                g["source_page_text"] = f"{g.get('source_page_text', '')}\n\n{contact_block}"

    print(f"⏱ Grant collection finished in {time.monotonic() - run_start:.1f}s ({len(results)} pages)")
    print(f"\n🎉 Pipeline completed! Found {len(grants)} active grants")
    # PRINT GRANTS IN JSON FORMAT
    print("\n📋 Grants in JSON format:")
    print(json.dumps(grants, indent=4))
    return grants

# main execution
if __name__ == "__main__":
    print("🎬 Starting Grant Writer Agent...")
    url = "https://www.voiceswithimpact.com/"
    print(f"🌍 Target website: {url}")
    
    grants = run_pipeline(url)
    
    print(f"\n📋 FINAL RESULTS:")
    print(f"🏆 Total active grants found: {len(grants)}")
    
    for i, g in enumerate(grants, 1):
        print(f"\n🎯 Grant #{i}:")
        print(f"   Name: {g.get('grant_name', 'N/A')}")
        print(f"   Deadline: {g.get('proposal_deadline', 'N/A')}")
        print(f"   Amount: {g.get('grant_amount', 'N/A')}")
        print(f"   Full details: {g}")

    print("\n✨ Grant Data Collector Agent completed!")


# https://www.1for2edu.com/
# https://vikingfoundation.godaddysites.com/
# https://mathersfoundation.org/how-to-apply/
# https://www.acceleratefortworth.org/sbag/
# https://www.templeton.org/