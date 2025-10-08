from fastapi import APIRouter, HTTPException
from ..models.schemas import (
    GrantWriterRequest, GrantWriterResponse,
    MetadataWriterRequest, MetadataWriterResponse
)
from ..services.grant_writer_service import GrantWriterService
from ..services.metadata_writer_service import MetadataWriterService

router = APIRouter(prefix="/grant-content-generation", tags=["Grant Content Generation"])

# Initialize services
grant_writer_service = GrantWriterService()
metadata_writer_service = MetadataWriterService()

@router.post("/grant-description", response_model=GrantWriterResponse)
async def generate_grant_description(request: GrantWriterRequest):
    """
    Generate consolidated grant description from multiple grants
    
    Args:
        request: Contains grants data and optional organization data
        
    Returns:
        Consolidated grant description
        
    Raises:
        HTTPException: If grant description generation fails
    """
    try:
        result = grant_writer_service.generate_consolidated_description(
            grants_data=request.grants_data,
            org_data=request.org_data
        )
        return GrantWriterResponse(consolidated_description=result)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate grant description: {str(e)}"
        )

@router.post("/metadata", response_model=MetadataWriterResponse)
async def generate_grant_metadata(request: MetadataWriterRequest):
    """
    Generate grant metadata fields from consolidated description
    
    Args:
        request: Contains consolidated grant description
        
    Returns:
        All 6 metadata fields (deadline, amount, etc.)
        
    Raises:
        HTTPException: If metadata generation fails
    """
    try:
        metadata = metadata_writer_service.generate_metadata(
            consolidated_description=request.consolidated_description
        )
        return MetadataWriterResponse(**metadata)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate metadata: {str(e)}"
        )