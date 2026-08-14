from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor
from langchain.prompts import ChatPromptTemplate
from urllib.parse import urljoin, urlparse
from agents.llm_factory import create_pipeline_llm, log_llm_usage, DEFAULT_EXTRACT_MODEL
from agents.grant_data_collector import _extract_contact_signals
from pydantic import BaseModel
import re
import json
import trafilatura
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ORG_PAGE_WORKERS = int(os.getenv("PIPELINE_PAGE_WORKERS", 8))

# Honest crawler identity. Spoofed browser UAs trip WAF TLS-fingerprint checks,
# and the python-requests default UA is blocked outright by some hosts (403).
REQUEST_HEADERS = {
    "User-Agent": os.getenv("BOT_USER_AGENT", "TheGrantPortalBot/1.0 (+https://www.thegrantportal.com)"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Step 1: Schema
class Organization(BaseModel):
    org_name: str = "Not specified"
    mission: str = "Not specified"
    background: str = "Not specified"
    about: str = "Not specified"
    contact: dict = {
        "phone": "Not specified", 
        "email": "Not specified", 
        "address": "Not specified",
        "other_info": "Not specified"
    }

# Step 2: Scrape pages
def scrape_site(url):
    print(f"🔍 Starting to scrape site: {url}")
    r = requests.get(url, timeout=15, headers=REQUEST_HEADERS)
    print(f"✅ Successfully fetched main page, status code: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    links = [a['href'] for a in soup.find_all('a', href=True)]
    print(f"📄 Found {len(links)} total links on the page")
    
    # Filter and fix relative URLs for organization-relevant pages
    org_links = []
    for l in links:
        if any(x in l.lower() for x in ["home", "about", "faq", "contact", "reach", "mission", "vision", "history", "background", "team", "staff", "board", "leadership", "who-we-are", "our-story", "get-in-touch", "reach-us", "contact-us", "about-us", "mission", "our-vision", "what-we-do", "help", "support"]):
            original_link = l
            # Resolve relative URLs against the page URL (string concatenation
            # built broken paths whenever the base URL had a path segment).
            # Fragments stripped — anchors are the same page.
            l = urljoin(url, l).split('#')[0]
            if not l.startswith('http'):
                continue  # mailto:, tel:, javascript: etc.
            org_links.append(l)
            print(f"🎯 Found potential organization link: {original_link} -> {l}")

    # Always include the main URL
    if url not in org_links:
        org_links.append(url)
        print(f"🎯 Added main URL to organization links: {url}")

    # remove duplicates
    org_links = list(set(org_links))

    # Restrict to max 10 links to avoid overload
    org_links = org_links[:10]

    print(f"✨ Total organization-related links found: {len(org_links)}")
    # print the list of links
    print("📋 Organization-related links:")
    for ol in org_links:
        print(f"   - {ol}")

    return org_links

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
            print("⚠️ Trafilatura extraction failed, falling back to raw HTML")
            extracted_text = html_content

        # Re-attach contact details that live only in mailto:/tel: hrefs (and
        # Cloudflare-obfuscated emails), which text extraction otherwise drops —
        # this is where the org's real email addresses usually are.
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
def extract_organization_info(page_texts):
    print("🤖 Starting LLM extraction process...")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")
    
    # Org extraction is field-pulling like grant extraction — cheap tier.
    llm = create_pipeline_llm(
        temperature=0.3,
        openai_api_key=openai_api_key,
        model=os.getenv("PIPELINE_EXTRACT_MODEL", DEFAULT_EXTRACT_MODEL),
    )
    print("🔗 Connected to OpenAI API")
    
    # Combine all page texts for comprehensive analysis
    combined_text = "\n\n--- NEW PAGE ---\n\n".join(page_texts)
    
    prompt = ChatPromptTemplate.from_template("""
    You are an expert researcher analyzing organization websites providing grants. Extract information about the organization from the provided web page text.

    Extract the following fields about the organization:

    1. Organization Name - the official name of the organization/foundation
    2. Mission - organization's mission statement, focus areas, funding priorities and interests. What kind of grants do they provide?
    3. Background - historical background, when it was founded, key milestones
    4. About - comprehensive about section describing what the organization does, their programs, initiatives
    5. Contact Information — this is shown to paying subscribers as the organization's contact card, so it must be clean and act-on-able, never a staff directory. Search every provided page (especially contact pages and "Email addresses found on this page" / "Telephone numbers found on this page" lines) and select:
       - phone: EXACTLY ONE phone number — the organization's main line. Never list per-person phone numbers, staff names with extensions, or more than one number.
       - email: EXACTLY ONE email address — the most relevant for grant applicants (a grants/program/inquiries address beats a general office inbox; a general inbox beats a personal one; if only personal staff emails exist, pick the one belonging to grants/program staff).
       - address: the full physical/mailing address: street, suite, city, state, zip code.
       - other_info: at most the website and fax if published; otherwise an empty object. No social media lists, no staff rosters.
       If a value genuinely appears nowhere in the provided pages, use an empty string "" for that field. NEVER write sentences into contact fields — no explanations, no "not specified", no "emails are behind a link", no descriptions of what the site says. A contact field contains a value or is empty.

    Include as much detail as possible in fields 1-4. Be comprehensive and thorough.
    Avoid making up information if not available on the pages.
    If multiple pages contain similar information, consolidate and provide the most complete version.

    Here is the combined text from all organization pages: {text}

    Return ONLY valid JSON in this exact format:
    {{
        "org_name": "string",
        "mission": "string", 
        "background": "string",
        "about": "string",
        "contact": {{
            "phone": "string",
            "email": "string", 
            "address": "string",
            "other_info": "json object with any other contact details or empty json if none"
        }}
    }}
    """)
    
    print(f"📝 Processing combined text of length: {len(combined_text)} characters")
    response = llm.invoke(prompt.format(text=combined_text))
    log_llm_usage("org-extract", response)
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
        organization = Organization.model_validate_json(result)
        print("✅ Successfully parsed organization information")
        
        # Check if this contains meaningful organization information
        if not organization.org_name or organization.org_name == "Not specified" or organization.org_name.strip() == "":
            print("⚠️ No valid organization information found - creating minimal object")
            
        return organization
    except Exception as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"📄 Raw result: {result}")
        
        # Try to create a default Organization object if JSON is problematic
        try:
            print("🔄 Attempting to create default Organization object...")
            return Organization()
        except Exception as fallback_error:
            print(f"❌ Fallback creation failed: {fallback_error}")
            return Organization()

def _fetch_page_text(p):
    """Fetch one page and return its extracted text, or None. Thread-pool worker."""
    try:
        if not p.startswith('http'):
            print(f"⚠️ Skipping invalid URL: {p}")
            return None

        html_content, extracted_text = get_html_content_and_extract_text(p)

        if not extracted_text:
            print(f"❌ Failed to extract content from: {p}")
            return None

        print(f"✅ Successfully extracted text from {p}")
        return extracted_text

    except Exception as e:
        print(f"❌ Error processing {p}: {str(e)}")
        return None


_PLACEHOLDER_VALUES = {"not specified", "n/a", "none", "unknown", "not available", ""}
_EMAIL_VALUE_RE = re.compile(r"[A-Za-z0-9][\w.+-]*@[A-Za-z0-9][\w-]*(?:\.[A-Za-z]{2,})+")
_PHONE_VALUE_RE = re.compile(r"\+?\(?\d[\d\s().\-]{6,}\d")

# Harvested-fact lines that _extract_contact_signals appends to page text.
_SIGNAL_LINE_RE = re.compile(
    r"^(Email addresses|Telephone numbers|Mailing/physical address)[^:]*:\s*(.+)$",
    re.MULTILINE,
)
# Application-platform / site-builder inboxes — never the foundation's own.
_PLATFORM_EMAIL_DOMAINS = (
    "grantinterface.com", "smartsimple.com", "submittable.com", "formstack.com",
    "fluxx.io", "surveymonkey.com", "wufoo.com", "wixpress.com", "squarespace.com",
)
# Preference order for the applicant-facing inbox local part.
_EMAIL_RANK_PREFIXES = (
    "grants", "grant", "scholarship", "program", "apply", "application",
    "foundation", "giving", "info", "inquiries", "contact", "office", "hello",
)
# Plain-text US phone (footers often carry no tel: link). Strict shape so EINs,
# zips and dollar figures never match.
_TEXT_PHONE_RE = re.compile(r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.])\d{3}[-.]\d{4}(?!\d)")
# Plain-text US street address, anchored on ", ST 12345" so prose never matches.
_TEXT_ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9 .'-]{2,40},\s*[A-Za-z][A-Za-z .'-]{2,30},\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"
)


def _second_level(host_or_email_domain: str) -> str:
    parts = host_or_email_domain.lower().removeprefix("www.").split(".")
    return parts[-2] if len(parts) >= 2 else parts[0]


def _domain_related(email: str, foundation_host: str) -> bool:
    """cummings.com relates to cummingsfoundation.org; weyerhaeuser.com does not."""
    if not foundation_host:
        return True
    e = _second_level(email.split("@")[-1])
    f = _second_level(foundation_host)
    return e in f or f in e


def _email_rank(email: str, foundation_host: str):
    local = email.split("@", 1)[0].lower()
    prefix_rank = len(_EMAIL_RANK_PREFIXES)
    for i, prefix in enumerate(_EMAIL_RANK_PREFIXES):
        if local.startswith(prefix):
            prefix_rank = i
            break
    return (prefix_rank, 0 if _domain_related(email, foundation_host) else 1, email.lower())


def _email_prefix_rank(email: str) -> int:
    local = email.split("@", 1)[0].lower()
    for i, prefix in enumerate(_EMAIL_RANK_PREFIXES):
        if local.startswith(prefix):
            return i
    return len(_EMAIL_RANK_PREFIXES)


def backfill_contact(contact: dict, harvested_text: str, foundation_host: str = "",
                     require_domain_match: bool = False,
                     allow_email_upgrade: bool = False) -> dict:
    """Fill EMPTY contact fields from deterministically harvested facts.

    The extractor model sometimes returns "" even when its input carries real
    signals — with several personal staff emails it cannot tell which one is
    'the grants contact' and gives up (Cummings Foundation reproduced this on
    every run). The model's own pick wins; this guarantees a floor: if a real
    signal was harvested, the card is never blank.

    require_domain_match hard-filters email candidates to domains related to
    the foundation's — set when the text comes from grant pages, which can
    include other organizations' sites.

    allow_email_upgrade additionally replaces a non-empty email when a
    candidate ranks STRICTLY better on the applicant-facing prefix ladder
    (grants@ beats a personal pick) — the same rubric the extraction prompt
    states. Equal ranks never swap.
    """
    contact = dict(contact or {})
    if not harvested_text:
        return contact

    # Regex-extract values from the payloads (never naive splits): payloads may
    # come from model-written fields and can carry placeholders or prose.
    emails, phones, addresses = [], [], []
    for kind, payload in _SIGNAL_LINE_RE.findall(harvested_text):
        if kind.startswith("Email"):
            emails.extend(_EMAIL_VALUE_RE.findall(payload))
        elif kind.startswith("Telephone"):
            phones.extend(p.strip() for p in _PHONE_VALUE_RE.findall(payload))
        else:
            addresses.extend(
                a.strip() for a in payload.split(" | ")
                if a.strip() and re.search(r"\d", a)
                and a.strip().lower() not in _PLACEHOLDER_VALUES
            )

    current_email = str(contact.get("email") or "")
    if not current_email or allow_email_upgrade:
        candidates = {
            e for e in emails
            if e and e.split("@")[-1].lower() not in _PLATFORM_EMAIL_DOMAINS
            and (not require_domain_match or _domain_related(e, foundation_host))
        }
        if candidates:
            best = sorted(candidates, key=lambda e: _email_rank(e, foundation_host))[0]
            if not current_email:
                contact["email"] = best
                print(f"📇 Contact backfill: email <- {best}")
            elif _email_prefix_rank(best) < _email_prefix_rank(current_email):
                contact["email"] = best
                print(f"📇 Contact backfill: email upgraded {current_email} -> {best}")

    if not contact.get("phone"):
        found = [p for p in phones if p] or _TEXT_PHONE_RE.findall(harvested_text)
        if found:
            contact["phone"] = found[0].strip()
            print(f"📇 Contact backfill: phone <- {contact['phone']}")

    if not contact.get("address"):
        found = addresses or _TEXT_ADDRESS_RE.findall(harvested_text)
        if found:
            contact["address"] = found[0].strip()
            print(f"📇 Contact backfill: address <- {contact['address']}")

    return contact


def _sanitize_contact(contact: dict) -> dict:
    """Deterministic guard on the contact card shown to subscribers.

    Whatever the model wrote, the output is: at most one email (a real address,
    not a sentence), at most one phone number, a placeholder-free address.
    The model prompt asks for exactly this — this enforces it.
    """
    contact = dict(contact or {})

    email_raw = str(contact.get("email") or "")
    emails = _EMAIL_VALUE_RE.findall(email_raw)
    contact["email"] = emails[0] if emails else ""

    phone_raw = str(contact.get("phone") or "")
    phones = _PHONE_VALUE_RE.findall(phone_raw)
    contact["phone"] = phones[0].strip() if phones else ""

    address = str(contact.get("address") or "").strip()
    contact["address"] = "" if address.lower() in _PLACEHOLDER_VALUES else address

    other = contact.get("other_info")
    if isinstance(other, str) and other.strip().lower() in _PLACEHOLDER_VALUES:
        contact["other_info"] = {}

    return contact


# Step 4: Run pipeline
def run_pipeline(foundation_url):
    print(f"🚀 Starting pipeline for Foundation URL: {foundation_url}")
    pages = scrape_site(foundation_url)
    print(f"📊 Processing {len(pages)} pages for organization information ({ORG_PAGE_WORKERS} workers)...")

    # Pages are independent — fetch them concurrently, keep page order.
    with ThreadPoolExecutor(max_workers=ORG_PAGE_WORKERS) as pool:
        results = list(pool.map(_fetch_page_text, pages))

    page_texts = [t for t in results if t]

    if not page_texts:
        print("❌ No page content was successfully extracted")
        return None
    
    print(f"\n🔍 Analyzing content from {len(page_texts)} pages...")
    organization = extract_organization_info(page_texts)
    
    if organization:
        org_data = organization.model_dump()
        org_data["contact"] = _sanitize_contact(org_data.get("contact"))
        # Model-empty fields get a deterministic floor from the pages' own
        # harvested signals (mailto:/tel:/JSON-LD/plain-text phone).
        org_data["contact"] = backfill_contact(
            org_data["contact"],
            "\n\n".join(page_texts),
            foundation_host=urlparse(foundation_url).netloc,
        )
        print(f"\n🎉 Pipeline completed! Organization information extracted")
        print("\n📋 Organization data in JSON format:")
        print(json.dumps(org_data, indent=4))
        return org_data
    else:
        print("❌ Failed to extract organization information")
        return None

# main execution
def collect_organization_data(foundation_url):
    """
    Main function to collect organization data from a foundation URL
    
    Args:
        foundation_url (str): The URL of the foundation/organization website
        
    Returns:
        dict: Organization data in JSON format or None if failed
    """
    print("🎬 Starting Organization Data Collector...")
    print(f"🌍 Target foundation website: {foundation_url}")
    
    org_data = run_pipeline(foundation_url)
    
    if org_data:
        print(f"\n📋 FINAL RESULTS:")
        print(f"🏢 Organization: {org_data.get('org_name', 'N/A')}")
        print(f"📧 Contact Email: {org_data.get('contact', {}).get('email', 'N/A')}")
        print(f"📞 Contact Phone: {org_data.get('contact', {}).get('phone', 'N/A')}")
        print(f"📍 Address: {org_data.get('contact', {}).get('address', 'N/A')}")
    else:
        print("❌ No organization data could be extracted")
    
    print("\n✨ Organization Data Collector completed!")
    return org_data

if __name__ == "__main__":
    # Example usage
    foundation_url = "https://reckoning.press"
    organization_data = collect_organization_data(foundation_url)
    
    if organization_data:
        print(f"\n🎯 Successfully collected data for: {organization_data.get('org_name', 'Unknown Organization')}")
    else:
        print("❌ Failed to collect organization data")

# Example URLs to test:
# https://www.voiceswithimpact.com/
# https://www.1for2edu.com/
# https://vikingfoundation.godaddysites.com/
# https://mathersfoundation.org/
# https://www.templeton.org/