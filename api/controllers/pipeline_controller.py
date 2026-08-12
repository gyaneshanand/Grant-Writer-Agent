import asyncio
import os

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
from agents.grant_writer import is_deadline_expired, is_invitation_only

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
        source_corpus = "\n\n".join(
            g.get("source_page_text") or ""
            for g in grants_data
            if g.get("source_page_text")
            and not is_deadline_expired(g.get("proposal_deadline", ""))
            and not is_invitation_only(g)
        )[:corpus_cap]

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