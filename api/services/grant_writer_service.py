from typing import List, Dict, Any, Optional
from ..config.settings import settings
from agents.grant_writer import GrantWriter

class GrantWriterService:
    def generate_consolidated_description(
        self, 
        grants_data: List[Dict[str, Any]], 
        org_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate consolidated grant description from grants and optional org data
        
        Args:
            grants_data: List of grant dictionaries
            org_data: Optional organization data dictionary
            
        Returns:
            Consolidated description string
            
        Raises:
            Exception: If description generation fails
        """
        try:
            # Check if API key is available
            api_key = settings.OPENAI_API_KEY
            if not api_key or api_key.strip() == "":
                # Try to get from environment directly
                import os
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise Exception("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
            
            writer = GrantWriter(api_key)
            result = writer.process_grants_consolidated(grants_data, org_data)
            
            # Extract the description string from the result dictionary
            return result.get('description', '')
            
        except Exception as e:
            raise Exception(f"Failed to generate consolidated description: {str(e)}")