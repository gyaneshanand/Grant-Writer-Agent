"""
Node: evaluate the 7 rules for each identified program.
"""
import json
import uuid
from typing import Optional

from agents.grant_writer_v2.core.llm import chat, BudgetExceeded
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer2_grant_detection.prompts import (
    RULE_EVALUATOR_SYSTEM,
    RULE_EVALUATOR_USER,
    PROMPT_VERSION,
)
from agents.grant_writer_v2.schemas.common import RuleEvaluation
from agents.grant_writer_v2.schemas.grant_program import SixRuleResult, GrantProgramVerdict

logger = get_logger("layer2.rule_evaluator")

MAX_PAGE_CONTENT_CHARS = 12_000
# Total chars of multi-page content fed to the rule evaluator. Larger than single-page
# limit because we concatenate evidence_url page + application/how-to-apply/grants pages.
MAX_MULTIPAGE_CONTENT_CHARS = 24_000
_RULE_KEYS = [
    "has_grants", "accepts_applications", "not_invitation_only",
    "not_donation_only", "allows_unsolicited", "geography_valid", "active_or_recurring",
]

# Path keywords that indicate rule-evidence pages worth concatenating.
_RULE_EVIDENCE_PATH_KEYWORDS = (
    "apply", "how-to-apply", "application", "grant", "grants", "funding",
    "eligib", "guidelines", "program", "programs", "rfp", "loi",
)


def _strip_html_for_eval(html: str) -> str:
    """Strip HTML for the rule-evaluator prompt. Keeps it readable in the LLM context."""
    import re
    s = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _build_page_content(evidence_url: str, corpus: list[dict]) -> str:
    """
    Build the content string fed to the rule evaluator.

    Concatenate the evidence_url page first (most relevant), then any other crawled pages
    whose path looks like an apply/grants/funding/eligibility page. This ensures the LLM
    sees the actual application instructions, eligibility text, etc. — not just the
    homepage where the program was first identified.
    """
    if not corpus:
        return ""

    from urllib.parse import urlparse

    seen_urls: set[str] = set()
    sections: list[str] = []
    remaining = MAX_MULTIPAGE_CONTENT_CHARS

    def _add(page: dict, budget: int) -> int:
        url = page.get("url", "")
        if not url or url in seen_urls or budget <= 0:
            return budget
        text = _strip_html_for_eval(page.get("text", ""))
        if not text:
            return budget
        chunk = text[:budget]
        sections.append(f"--- PAGE: {url} ---\n{chunk}")
        seen_urls.add(url)
        return budget - len(chunk)

    # 1. evidence_url page (first priority)
    if evidence_url:
        for p in corpus:
            if p.get("url") == evidence_url:
                remaining = _add(p, remaining)
                break

    # 2. other pages whose path looks rule-relevant
    for p in corpus:
        url = p.get("url", "")
        if url in seen_urls or not url:
            continue
        path_lower = urlparse(url).path.lower()
        if any(kw in path_lower for kw in _RULE_EVIDENCE_PATH_KEYWORDS):
            remaining = _add(p, remaining)
            if remaining <= 0:
                break

    # 3. fallback — if nothing was added (no evidence_url match, no apply-like pages),
    # use the first page in the corpus
    if not sections:
        remaining = _add(corpus[0], MAX_MULTIPAGE_CONTENT_CHARS)

    return "\n\n".join(sections)


def _find_page_content(evidence_url: str, corpus: list[dict]) -> str:
    """Backward-compatible wrapper — now multi-page aware."""
    return _build_page_content(evidence_url, corpus)


def _parse_rule(raw: dict) -> RuleEvaluation:
    return RuleEvaluation(
        value=bool(raw.get("value", False)),
        confidence=float(raw.get("confidence", 0.5)),
        evidence_quote=str(raw.get("evidence_quote", ""))[:200],
        source_url=str(raw.get("source_url", "")),
    )


def _default_rules() -> SixRuleResult:
    default = RuleEvaluation(value=False, confidence=0.0, evidence_quote="evaluation failed", source_url="")
    return SixRuleResult(
        has_grants=default,
        accepts_applications=default,
        not_invitation_only=default,
        not_donation_only=default,
        allows_unsolicited=default,
        geography_valid=default,
        active_or_recurring=default,
    )


async def evaluate_program(
    program: dict,
    corpus: list[dict],
    org_name: str,
    ein: str,
    run_id: str,
    budget_usd: float,
) -> GrantProgramVerdict:
    program_name = program.get("program_name", "Unknown Program")
    evidence_url = program.get("evidence_url", "")
    page_content = _find_page_content(evidence_url, corpus)

    program_id = f"{ein}_{uuid.uuid4().hex[:8]}"

    user_msg = RULE_EVALUATOR_USER.format(
        org_name=org_name,
        program_name=program_name,
        evidence_url=evidence_url,
        page_content=page_content,
    )

    try:
        resp = await chat(
            "layer2_rule_evaluator",
            messages=[
                {"role": "system", "content": RULE_EVALUATOR_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            ein=ein,
            layer="layer2",
            run_id=run_id,
            budget_usd=budget_usd,
            max_tokens=1500,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
        rules = SixRuleResult(
            has_grants=_parse_rule(raw.get("has_grants", {})),
            accepts_applications=_parse_rule(raw.get("accepts_applications", {})),
            not_invitation_only=_parse_rule(raw.get("not_invitation_only", {})),
            not_donation_only=_parse_rule(raw.get("not_donation_only", {})),
            allows_unsolicited=_parse_rule(raw.get("allows_unsolicited", {})),
            geography_valid=_parse_rule(raw.get("geography_valid", {})),
            active_or_recurring=_parse_rule(raw.get("active_or_recurring", {})),
        )
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning(f"[L2] rule_evaluator failed for {program_name} ({ein}): {e}")
        rules = _default_rules()

    # Determine verdict
    # all_pass threshold raised to 0.7 — requires explicit page evidence, not inference
    if rules.all_pass(confidence_threshold=0.7):
        verdict = "VALID"
    elif rules.any_fail_hard(confidence_threshold=0.8):
        verdict = "INVALID"
    else:
        verdict = "NEEDS_REVIEW"

    return GrantProgramVerdict(
        program_id=program_id,
        ein=ein,
        program_name=program_name,
        verdict=verdict,
        rules=rules,
    )


async def evaluate_all_programs(
    programs: list[dict],
    corpus: list[dict],
    org_name: str,
    ein: str,
    run_id: str,
    budget_usd: float,
) -> list[GrantProgramVerdict]:
    verdicts = []
    for program in programs:
        try:
            verdict = await evaluate_program(program, corpus, org_name, ein, run_id, budget_usd)
            verdicts.append(verdict)
        except BudgetExceeded:
            logger.warning(f"[L2] BudgetExceeded while evaluating programs for {ein} — stopping at {len(verdicts)}")
            break
        except Exception as e:
            logger.error(f"[L2] Unexpected error evaluating {program.get('program_name')} for {ein}: {e}")
    return verdicts
