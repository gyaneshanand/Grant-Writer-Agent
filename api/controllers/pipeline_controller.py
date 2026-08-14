import asyncio
import os
import time

from fastapi import APIRouter, HTTPException
from typing import List
from ..models.schemas import (
    PipelineRequest, PipelineResponse,
    GrantDataResponse, OrganizationDataResponse
)
from ..services.grant_data_service import GrantDataService
from ..services.organization_data_service import OrganizationDataService
from ..services.grant_writer_service import GrantWriterService
from ..services.metadata_writer_service import MetadataWriterService
from urllib.parse import urlparse

from agents.grant_writer import is_deadline_expired, is_invitation_only
from agents.grant_data_collector import CONTACT_BLOCK_HEADER
from agents.organisation_data_collector import backfill_contact

router = APIRouter(prefix="/pipeline", tags=["Full Pipeline"])

# Initialize all services
grant_data_service = GrantDataService()
org_data_service = OrganizationDataService()
grant_writer_service = GrantWriterService()
metadata_writer_service = MetadataWriterService()

@router.post("/complete", response_model=PipelineResponse)
async def run_complete_pipeline(request: PipelineRequest):
    """
    Run the complete 4-step grant processing pipeline
    
    Steps:
    1. Collect grant data from foundation URLs
    2. Collect organization data (if requested)
    3. Generate consolidated grant description
    4. Generate metadata fields
    
    Args:
        request: Contains foundation URLs and pipeline options
        
    Returns:
        Complete pipeline results with all generated content
        
    Raises:
        HTTPException: If any pipeline step fails
    """
    try:
        started = time.monotonic()
        # Steps 1 + 2 are independent (both need only the URL), so they run
        # concurrently. Each was a full scrape-plus-LLM pass over the same
        # site; running them back to back doubled the scraping wall-clock.
        grants_task = asyncio.to_thread(
            grant_data_service.collect_grants,
            foundation_url=str(request.foundation_url),
            max_grants=request.max_grants,
        )

        if request.include_org_data:
            org_task = asyncio.to_thread(
                org_data_service.collect_organization_data,
                foundation_url=str(request.foundation_url),
            )
            grants_data, org_data = await asyncio.gather(grants_task, org_task)
        else:
            grants_data = await grants_task
            org_data = None

        # Second-chance contact backfill: the best applicant-facing email often
        # lives on grant pages the org pipeline never fetches (grants@... on an
        # application page). Grant pages can belong to other orgs' sites, so
        # email candidates are hard-filtered to foundation-related domains.
        if org_data and isinstance(org_data.get("contact"), dict):
            # Candidates come only from grants whose page lives on the
            # foundation's OWN site (provenance, not email-domain: a gmail
            # contact on the foundation's page is legit; another org's page —
            # e.g. an external funder linked from the homepage — never feeds
            # this foundation's card). contact_info fields are included because
            # the extractor reads the full page while source_page_text is
            # capped, so footer phones/addresses often survive only there.
            foundation_host = urlparse(str(request.foundation_url)).netloc.lower().removeprefix("www.")

            def _own_site(g):
                host = urlparse(str(g.get("grant_url") or "")).netloc.lower().removeprefix("www.")
                return host == foundation_host or host.endswith("." + foundation_host)

            signal_parts = []
            for g in grants_data:
                if not isinstance(g, dict) or not _own_site(g):
                    continue
                if g.get("source_page_text"):
                    signal_parts.append(g["source_page_text"])
                ci = g.get("contact_info")
                if isinstance(ci, dict):
                    if ci.get("email"):
                        signal_parts.append(f"Email addresses found on this page: {ci['email']}")
                    if ci.get("phone"):
                        signal_parts.append(f"Telephone numbers found on this page: {ci['phone']}")
                    if ci.get("address"):
                        signal_parts.append(f"Mailing/physical address found in this page's metadata: {ci['address']}")
            org_data["contact"] = backfill_contact(
                org_data["contact"],
                "\n\n".join(signal_parts),
                foundation_host=foundation_host,
                allow_email_upgrade=True,
            )

        # No grants -> stop here. Running the writers on empty data makes the
        # teaser hallucinate generic filler, which must never reach subscribers.
        active_exists = any(
            not is_deadline_expired(g.get("proposal_deadline", "")) and not is_invitation_only(g)
            for g in grants_data
        )
        if not active_exists:
            for g in grants_data:
                if isinstance(g, dict):
                    g.pop("source_page_text", None)
            print(f"⏱ /pipeline/complete finished in {time.monotonic() - started:.1f}s (no active grants)")
            return PipelineResponse(
                grants_data=grants_data,
                organization_data=org_data,
                consolidated_description="No active grant opportunities are currently available.",
                metadata={},
            )

        # Build a bounded corpus of the raw page text for the teaser/metadata
        # writer, so the teaser is grounded in the source and not in a summary of
        # a summary. Uses the same active-grant filters as the description writer
        # so pages of expired or invitation-only grants never reach the teaser.
        # The description writer reads source_page_text off each grant itself.
        corpus_cap = int(os.getenv("PIPELINE_SOURCE_CORPUS_CHARS", "48000"))
        corpus_chunks, contact_block = [], ""
        for g in grants_data:
            if not g.get("source_page_text"):
                continue
            if is_deadline_expired(g.get("proposal_deadline", "")) or is_invitation_only(g):
                continue
            text = g["source_page_text"]
            # The site-wide contact block rides on every grant — keep one copy
            # so it doesn't crowd real page text out of the capped corpus.
            if CONTACT_BLOCK_HEADER in text:
                text, _, tail = text.partition(CONTACT_BLOCK_HEADER)
                contact_block = CONTACT_BLOCK_HEADER + tail
                text = text.rstrip()
            if text:
                corpus_chunks.append(text)
        if contact_block:
            corpus_chunks.append(contact_block)
        source_corpus = "\n\n".join(corpus_chunks)[:corpus_cap]

        # Step 3: Generate consolidated description
        consolidated_result = grant_writer_service.generate_consolidated_description(
            grants_data=grants_data,
            org_data=org_data
        )

        # Step 4: Generate metadata (teaser grounded in the raw source corpus)
        metadata = metadata_writer_service.generate_metadata(
            consolidated_description=consolidated_result,
            source_text=source_corpus,
        )

        # Keep source_page_text internal: strip it so the API payload stays lean
        # and TGP sees the same grant shape as before this change.
        for g in grants_data:
            if isinstance(g, dict):
                g.pop("source_page_text", None)

        print(f"⏱ /pipeline/complete finished in {time.monotonic() - started:.1f}s "
              f"({len(grants_data)} grants) — sum 📊 lines above for total cost")
        return PipelineResponse(
            grants_data=grants_data,
            organization_data=org_data,
            consolidated_description=consolidated_result,
            metadata=metadata
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Pipeline execution failed: {str(e)}"
        )