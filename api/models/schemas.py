from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any, Optional
from datetime import datetime

# Individual Grant Model
class Grant(BaseModel):
    title: str
    description: str
    amount: Optional[str] = None
    deadline: Optional[str] = None
    eligibility: Optional[str] = None
    source_url: Optional[str] = None

# Organization Model
class Organization(BaseModel):
    org_name: str
    mission: Optional[str] = None
    background: Optional[str] = None
    about: Optional[str] = None
    contact: Optional[Dict[str, Any]] = None

# Data Collection Request Models
class GrantDataRequest(BaseModel):
    foundation_url: HttpUrl
    max_grants: Optional[int] = 10

class OrganizationDataRequest(BaseModel):
    foundation_url: HttpUrl

# Content Generation Request Models
class GrantWriterRequest(BaseModel):
    grants_data: List[Dict[str, Any]]
    org_data: Optional[Dict[str, Any]] = None

class MetadataWriterRequest(BaseModel):
    consolidated_description: str

# Pipeline Request Model
class PipelineRequest(BaseModel):
    foundation_url: HttpUrl
    max_grants: Optional[int] = 10
    include_org_data: Optional[bool] = True

# Data Collection Response Models
class GrantDataResponse(BaseModel):
    grant_name: str = "Not specified"
    funding_priorities: str = "Not specified"
    types_of_grant: str = "Not specified"
    eligibility_criteria: str = "Not specified"
    eligible_applicants: List[str] = []
    eligible_locations: str = "Not specified"
    grant_amount_range: str = "Not specified"
    grant_amount: str = "Not specified"
    proposal_deadline: str = "Not specified"
    recurrence: str = "Not specified"
    contact_info: Dict[str, str] = {"email": "Not specified", "phone": "Not specified", "address": "Not specified"}
    organization_info: str = "Not specified"
    grant_summary: str = "Not specified"
    grant_url: str = "Not specified"

class OrganizationDataResponse(BaseModel):
    org_name: str
    mission: Optional[str] = None
    background: Optional[str] = None
    about: Optional[str] = None
    contact: Optional[Dict[str, Any]] = None

# Content Generation Response Models
class GrantWriterResponse(BaseModel):
    consolidated_description: str

class MetadataWriterResponse(BaseModel):
    opportunity_title: str
    h1_tag: str
    meta_title: str
    meta_description: str
    opportunity_teaser: str
    opportunity_title_for_subscriber: str

# Pipeline Response Model
class PipelineResponse(BaseModel):
    grants_data: List[Dict[str, Any]]
    organization_data: Optional[Dict[str, Any]] = None
    consolidated_description: str
    metadata: Dict[str, Any]

# Health Check Model
class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]

# Error Response
class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_type: str
    details: Optional[str] = None