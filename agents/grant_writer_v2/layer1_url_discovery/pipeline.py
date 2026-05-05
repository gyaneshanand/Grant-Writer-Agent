"""
Layer 1 — URL Discovery.
async def run(foundation: FoundationInput) -> Layer1Output

Flow:
  1. Build SerpAPI query from org_name + state
  2. Call SerpAPI, parse candidates, run blocklist filter
  3. Score each non-blocked candidate with deterministic verifier
  4. If best confidence in gray band → LLM reranker
  5. Select winner or reject
  6. Persist to foundations.v2_layer1_* and v2_layer1_candidates
  7. Write audit row to v2_pipeline_runs
"""
import json
import time
import uuid

from agents.grant_writer_v2.core.audit import write_pipeline_run
from agents.grant_writer_v2.core.db import sql_exec, sql_exec_many
from agents.grant_writer_v2.core.logger import get_logger
from agents.grant_writer_v2.layer1_url_discovery import classifier, verifier
from agents.grant_writer_v2.layer1_url_discovery.llm_reranker import needs_rerank, rerank
from agents.grant_writer_v2.layer1_url_discovery.schemas import Layer1Output
from agents.grant_writer_v2.layer1_url_discovery.serpapi_client import build_query, build_fallback_query, search
from agents.grant_writer_v2.schemas.common import CandidateRecord, FoundationInput

logger = get_logger("layer1")

HIGH_CONFIDENCE = 0.65
MIN_CONFIDENCE = 0.35


async def run(foundation: FoundationInput) -> Layer1Output:
    start = time.monotonic()
    ein = foundation.ein

    query = build_query(foundation.org_name, foundation.state, foundation.city)
    logger.info(f"[L1] {ein} — query: {query}")

    # 1. SerpAPI call
    try:
        serp = await search(query)
    except Exception as e:
        logger.error(f"[L1] {ein} — SerpAPI error: {e}")
        output = Layer1Output(ein=ein, status="error_serpapi", serpapi_query=query,
                              processing_ms=_ms(start))
        await _persist(foundation, output, query)
        return output

    # 2. Extract + blocklist filter
    candidates = classifier.extract_candidates(serp)
    valid = [c for c in candidates if not c.blocklisted]

    # Fallback: if primary query yields no valid candidates, try a broader query
    if not valid:
        fallback_query = build_fallback_query(foundation.org_name, foundation.state)
        logger.info(f"[L1] {ein} — no valid candidates, trying fallback query: {fallback_query}")
        try:
            serp2 = await search(fallback_query)
            fallback_candidates = classifier.extract_candidates(serp2)
            fallback_valid = [c for c in fallback_candidates if not c.blocklisted]
            if fallback_valid:
                candidates = fallback_candidates
                valid = fallback_valid
                query = fallback_query
            else:
                candidates = candidates + fallback_candidates
        except Exception as e:
            logger.warning(f"[L1] {ein} — fallback SerpAPI error: {e}")

    if not valid:
        output = Layer1Output(ein=ein, status="rejected_no_candidates", serpapi_query=query,
                              candidates_seen=candidates, processing_ms=_ms(start))
        await _persist(foundation, output, query)
        return output

    # 3. Score each valid candidate
    scored: list[tuple[CandidateRecord, float, dict]] = []
    for c in valid:
        conf, signals = verifier.score(c, foundation)
        c.verifier_score = conf
        c.verifier_signals = signals
        scored.append((c, conf, signals))
    scored.sort(key=lambda x: x[1], reverse=True)

    best_candidate, best_conf, best_signals = scored[0]

    # Fallback when primary candidates are noise (all score below the rerank gray band).
    # Common case: SerpAPI's primary query returns only aggregators and they get blocklisted,
    # leaving 1–2 low-quality stragglers (radaris, etc.) that score < 0.35.
    if best_conf < MIN_CONFIDENCE:
        fallback_query = build_fallback_query(foundation.org_name, foundation.state)
        logger.info(f"[L1] {ein} — best primary candidate conf {best_conf:.2f} below threshold, trying fallback: {fallback_query}")
        try:
            serp2 = await search(fallback_query)
            fb_cands = classifier.extract_candidates(serp2)
            fb_valid = [c for c in fb_cands if not c.blocklisted]
            if fb_valid:
                fb_scored = []
                for c in fb_valid:
                    cc, ss = verifier.score(c, foundation)
                    c.verifier_score = cc
                    c.verifier_signals = ss
                    fb_scored.append((c, cc, ss))
                fb_scored.sort(key=lambda x: x[1], reverse=True)
                if fb_scored[0][1] > best_conf:
                    candidates = candidates + fb_cands  # keep both audits
                    valid = fb_valid
                    scored = fb_scored
                    best_candidate, best_conf, best_signals = scored[0]
                    query = fallback_query
        except Exception as e:
            logger.warning(f"[L1] {ein} — fallback SerpAPI error: {e}")

    # 4. LLM reranker for gray band
    llm_used = False
    llm_reasoning = None
    llm_model = None

    if needs_rerank(best_conf):
        # Normalize PDF/deep URLs to root domain for reranker so LLM sees the domain, not a PDF path
        rerank_candidates = _normalize_for_rerank(valid)
        idx, reasoning, model = await rerank(rerank_candidates, foundation, ein=ein)
        llm_used = True
        llm_reasoning = reasoning
        llm_model = model
        if idx is not None:
            best_candidate = rerank_candidates[idx]  # use normalized URL (root domain, not PDF path)
            best_conf, best_signals = verifier.score(best_candidate, foundation)
            # Accept LLM pick with slightly boosted confidence
            best_conf = max(best_conf, 0.55)
        else:
            # LLM explicitly said none of the candidates are the official site — force reject
            best_conf = 0.0

    # 5. Select or reject
    if best_conf < MIN_CONFIDENCE:
        for c, _, _ in scored:
            c.rejection_reason = "low_confidence"
        output = Layer1Output(
            ein=ein, status="rejected_low_confidence", serpapi_query=query,
            candidates_seen=candidates, confidence=best_conf,
            llm_rerank_used=llm_used, llm_rerank_reasoning=llm_reasoning,
            processing_ms=_ms(start),
        )
        await _persist(foundation, output, query)
        return output

    # Mark winner
    best_candidate.selected = True
    status = "accepted_kg" if best_candidate.snippet == "Knowledge Graph result" else \
             "accepted_llm" if llm_used else "accepted_verifier"

    # Normalize final URL to root domain — L2 should crawl from homepage, not a deep page
    # (SerpAPI sometimes returns /privacy-policy/, /contact/, etc. as top result)
    from urllib.parse import urlparse
    parsed_final = urlparse(best_candidate.url)
    final_url = f"{parsed_final.scheme}://{parsed_final.netloc}/"

    kg = serp.get("knowledge_graph", {})
    output = Layer1Output(
        ein=ein,
        status=status,
        url=final_url,
        confidence=best_conf,
        method=status,
        evidence=best_candidate.snippet[:300],
        evidence_signals=best_signals,
        google_place_id=kg.get("place_id"),
        knowledge_graph_present=bool(kg),
        serpapi_query=query,
        serpapi_total_results=serp.get("search_information", {}).get("total_results"),
        candidates_seen=candidates,
        verifier_score=best_conf,
        verifier_signals=best_signals,
        llm_rerank_used=llm_used,
        llm_rerank_model=llm_model,
        llm_rerank_reasoning=llm_reasoning,
        processing_ms=_ms(start),
    )
    await _persist(foundation, output, query)
    return output


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _normalize_for_rerank(candidates: list) -> list:
    """
    Return a copy of candidates with PDF/deep paths normalized to root domain URL.
    Preserves original list order and object identity (index mapping stays valid).
    """
    from urllib.parse import urlparse
    import copy
    normalized = []
    for c in candidates:
        parsed = urlparse(c.url)
        if parsed.path.lower().endswith(".pdf") or len(parsed.path) > 60:
            c2 = copy.copy(c)
            c2.url = f"{parsed.scheme}://{parsed.netloc}/"
            normalized.append(c2)
        else:
            normalized.append(c)
    return normalized


async def _persist(foundation: FoundationInput, output: Layer1Output, query: str) -> None:
    """Write Layer1Output to foundations table + v2_layer1_candidates + audit row."""
    ein = foundation.ein
    try:
        # Upsert foundations row (create if not exists)
        await sql_exec(
            """
            INSERT INTO foundations
              (ein, name, city, state,
               v2_layer1_status, v2_layer1_url, v2_layer1_confidence,
               v2_layer1_evidence, v2_layer1_place_id, v2_layer1_method,
               v2_layer1_metadata, v2_layer1_processed_at, v2_pipeline_status)
            VALUES
              (:ein, :name, :city, :state,
               :status, :url, :confidence,
               :evidence, :place_id, :method,
               :metadata, NOW(), :pipeline_status)
            ON DUPLICATE KEY UPDATE
              v2_layer1_status       = :status,
              v2_layer1_url          = :url,
              v2_layer1_confidence   = :confidence,
              v2_layer1_evidence     = :evidence,
              v2_layer1_place_id     = :place_id,
              v2_layer1_method       = :method,
              v2_layer1_metadata     = :metadata,
              v2_layer1_processed_at = NOW(),
              v2_pipeline_status     = :pipeline_status
            """,
            {
                "ein": ein,
                "name": foundation.org_name,
                "city": foundation.city or "",
                "state": foundation.state,
                "status": output.status,
                "url": output.url,
                "confidence": output.confidence,
                "evidence": output.evidence,
                "place_id": output.google_place_id,
                "method": output.method,
                "metadata": json.dumps({"signals": output.evidence_signals}),
                "pipeline_status": "layer1_done" if output.url else "layer1_rejected",
            },
        )
    except Exception as e:
        logger.error(f"[L1] persist foundations failed for {ein}: {e}")

    # Persist candidate audit rows
    if output.candidates_seen:
        rows = [
            {
                "ein": ein,
                "candidate_url": c.url,
                "position": c.position,
                "title": c.title[:500],
                "snippet": (c.snippet or "")[:1000],
                "blocklisted": c.blocklisted,
                "blocklist_category": c.blocklist_category,
                "blocklist_domain": c.blocklist_domain,
                "verifier_score": c.verifier_score,
                "verifier_signals": json.dumps(c.verifier_signals) if c.verifier_signals else None,
                "selected": c.selected,
                "rejection_reason": c.rejection_reason,
                "serpapi_query": query,
            }
            for c in output.candidates_seen
        ]
        try:
            await sql_exec_many(
                """
                INSERT INTO v2_layer1_candidates
                  (ein, candidate_url, position, title, snippet, blocklisted,
                   blocklist_category, blocklist_domain, verifier_score, verifier_signals,
                   selected, rejection_reason, serpapi_query)
                VALUES
                  (:ein, :candidate_url, :position, :title, :snippet, :blocklisted,
                   :blocklist_category, :blocklist_domain, :verifier_score, :verifier_signals,
                   :selected, :rejection_reason, :serpapi_query)
                """,
                rows,
            )
        except Exception as e:
            logger.error(f"[L1] persist candidates failed for {ein}: {e}")

    await write_pipeline_run(
        ein=ein,
        layer="layer1",
        status=output.status,
        output_snapshot={"url": output.url, "confidence": output.confidence,
                         "method": output.method},
        cost_usd=output.cost_usd,
        duration_ms=output.processing_ms,
    )
