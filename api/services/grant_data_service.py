from typing import List, Dict, Any, Optional
from agents import grant_data_collector

class GrantDataService:
    def collect_grants(self, foundation_url: str, max_grants: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Collect grants from foundation URL
        
        Args:
            foundation_url: URL of the foundation website
            max_grants: Maximum number of grants to collect (optional)
            
        Returns:
            List of grant dictionaries
            
        Raises:
            Exception: If grant collection fails
        """
        try:
            grants = grant_data_collector.run_pipeline(foundation_url)
            
            # Ensure we return a list
            if not isinstance(grants, list):
                grants = [grants] if grants else []
            
            # Apply max_grants limit if specified
            if max_grants and len(grants) > max_grants:
                grants = grants[:max_grants]
                
            return grants
            
        except Exception as e:
            raise Exception(f"Failed to collect grants from {foundation_url}: {str(e)}")