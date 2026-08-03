import asyncio

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

        # Step 3: Generate consolidated description
        consolidated_result = grant_writer_service.generate_consolidated_description(
            grants_data=grants_data,
            org_data=org_data
        )
        
        # Step 4: Generate metadata
        metadata = metadata_writer_service.generate_metadata(
            consolidated_description=consolidated_result
        )
        
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