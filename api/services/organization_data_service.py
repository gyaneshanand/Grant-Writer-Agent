from typing import Dict, Any, Optional
from agents import organisation_data_collector

class OrganizationDataService:
    def collect_organization_data(self, foundation_url: str) -> Optional[Dict[str, Any]]:
        """
        Collect organization data from foundation URL
        
        Args:
            foundation_url: URL of the foundation website
            
        Returns:
            Organization data dictionary or None if not found
            
        Raises:
            Exception: If organization data collection fails
        """
        try:
            return organisation_data_collector.collect_organization_data(foundation_url)
        except Exception as e:
            raise Exception(f"Failed to collect organization data from {foundation_url}: {str(e)}")