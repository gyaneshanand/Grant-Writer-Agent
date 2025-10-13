from fastapi import APIRouter, HTTPException
from typing import List
from ..models.schemas import (
    GrantDataRequest, GrantDataResponse, 
    OrganizationDataRequest, OrganizationDataResponse,
    URLFinderRequest, URLFinderResponse
)
from ..services.grant_data_service import GrantDataService
from ..services.organization_data_service import OrganizationDataService

# Import the URL finder agent
import sys
from pathlib import Path
# Add agents directory to path
agents_dir = Path(__file__).parent.parent.parent / "agents"
sys.path.insert(0, str(agents_dir))
from organisation_url_finder_agent import find_organization_url

router = APIRouter(prefix="/grant-data-collection", tags=["Data Collection"])

# Initialize services
grant_data_service = GrantDataService()
org_data_service = OrganizationDataService()

@router.post("/grants", response_model=List[GrantDataResponse])
async def collect_grant_data(request: GrantDataRequest):
    """
    Collect grant data from foundation URLs
    
    Args:
        request: Contains foundation URLs and optional parameters
        
    Returns:
        List of grants with extracted data
        
    Raises:
        HTTPException: If grant data collection fails
    """
    try:
        grants = grant_data_service.collect_grants(
            foundation_url=str(request.foundation_url),
            max_grants=request.max_grants
        )
        return grants
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to collect grant data: {str(e)}"
        )

@router.post("/organization", response_model=OrganizationDataResponse)
async def collect_organization_data(request: OrganizationDataRequest):
    """
    Collect organization data from foundation website
    
    Args:
        request: Contains foundation URL
        
    Returns:
        Organization data with mission, values, priorities, etc.
        
    Raises:
        HTTPException: If organization data collection fails
    """
    try:
        org_data = org_data_service.collect_organization_data(
            foundation_url=request.foundation_url
        )
        return org_data
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to collect organization data: {str(e)}"
        )

@router.post("/find-url", response_model=URLFinderResponse)
async def find_organization_url_endpoint(request: URLFinderRequest):
    """
    Find official website URL for an organization using AI agent
    
    Args:
        request: Contains organization name and optional foundation data
        
    Returns:
        URLFinderResponse with found URL and metadata
        
    Raises:
        HTTPException: If URL finding fails
    """
    try:
        result = find_organization_url(
            organization_name=request.organization_name,
            foundation_data=request.foundation_data,
            model=request.model
        )
        
        return URLFinderResponse(
            success=result["success"],
            url=result.get("url"),
            attempts=result["attempts"],
            error=result.get("error"),
            organization_name=request.organization_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to find organization URL: {str(e)}"
        )