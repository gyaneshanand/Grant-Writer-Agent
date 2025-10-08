from typing import Dict, Any
from ..config.settings import settings
from agents.grant_metadata_writer import GrantMetadataWriter

class MetadataWriterService:
    def generate_metadata(self, consolidated_description: str) -> Dict[str, Any]:
        """
        Generate all 6 metadata fields from consolidated description
        
        Args:
            consolidated_description: Consolidated grant description text
            
        Returns:
            Dictionary with all metadata fields (deadline, amount, etc.)
            
        Raises:
            Exception: If metadata generation fails
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
            
            writer = GrantMetadataWriter(api_key)
            return writer.generate_all_metadata_single_call(consolidated_description)
        except Exception as e:
            raise Exception(f"Failed to generate metadata: {str(e)}")