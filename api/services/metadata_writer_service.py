from typing import Dict, Any
from ..config.settings import settings
from agents.grant_metadata_writer import GrantMetadataWriter

class MetadataWriterService:
    def generate_metadata(self, consolidated_description: str, source_text: str = None) -> Dict[str, Any]:
        """
        Generate all 6 metadata fields from consolidated description

        Args:
            consolidated_description: Consolidated grant description text
            source_text: Optional raw page corpus, used only to make the teaser
                accurate; exclusion rules still strip names/amounts/dates/URLs

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
            return writer.generate_all_metadata_single_call(consolidated_description, source_text=source_text)
        except Exception as e:
            raise Exception(f"Failed to generate metadata: {str(e)}")