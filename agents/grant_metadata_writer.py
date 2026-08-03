from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel
import json
from typing import Dict, Any
import os
from dotenv import load_dotenv

from agents.llm_factory import create_pipeline_llm

# Load environment variables
load_dotenv()

class GrantMetadata(BaseModel):
    opportunity_title: str
    h1_tag: str
    meta_title: str
    meta_description: str
    opportunity_teaser: str
    opportunity_title_for_subscriber: str

class GrantMetadataWriter:
    """
    A class for generating metadata for grant opportunities using LLM.
    """
    
    def __init__(self, openai_api_key: str = None):
        """
        Initialize the Grant Metadata Writer
        Args:
            openai_api_key: Optional API key. If not provided, will use OPENAI_API_KEY from environment
        """
        if not openai_api_key:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")
        
        self.llm = create_pipeline_llm(temperature=0.3, openai_api_key=openai_api_key)

    def generate_all_metadata_single_call(self, grant_data: str) -> Dict[str, str]:
        """
        Generate all 6 metadata fields from grant data in a single OpenAI call
        
        Args:
            grant_data (str): Markdown text with collected grant opportunity data
            
        Returns:
            Dict[str, str]: Dictionary containing all 6 metadata fields
        """
        print("🚀 Starting Grant Metadata Generation with Single OpenAI Call...")
        print(f"📝 Processing grant data of length: {len(grant_data)} characters")
        
        prompt = ChatPromptTemplate.from_template("""
        You are an expert grant writer and SEO specialist. Generate 6 metadata fields for a grant opportunity based on the provided grant data.
                                                  
        Remember to follow the word and character limits exactly. Ensure that Opportunity Teaser is about 200 words and never exceeds 300 words, and contains no dollar amounts and no deadline dates.

        Generate the following 6 fields:

        1. **Opportunity Title** (around 60 characters): Clean title for grant opportunity; make it vague; include grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly. Make sure Opportunity Title is not more than 70 characters

        2. **H1 Tag** (around 50 characters): Clean H1 tag for grant opportunity; make it vague; include grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly. Make sure H1 Tag is not more than 60 characters.

        3. **Meta Title** (around 50 characters): Clean Meta Title for grant opportunity; make it vague; include grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly. Make sure *Meta Title is not more than 60 characters.

        4. **Meta Description** (approximately 140 characters): Clean Meta Description that is DIFFERENT from the Meta Title for grant opportunity; make it vague; include grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly. Make sure Meta Description is not more than 150 characters.

        5. **Opportunity Teaser** (170 to 240 words, ideally about 200; NEVER exceed 300 words, HARD LIMIT): Write a descriptive, engaging and easy to understand summary with description of grant opportunity. Make the response vague. Do NOT show icons. Do NOT show bullets. Do not include any content source URLs. Provide information such as grants for which states or regions, grants for nonprofits or businesses or individuals. Provide information to describe the intent of use for the funds. Never state a dollar amount, award size, range, match ratio, percentage or deadline date — amounts and deadlines are displayed separately on the page. Do not use vague money language as a substitute ("up to", "as much as", "generous", "substantial award"). Write about the grant opportunity benefits, interests, identify if nonprofit organizations or small businesses or individuals are eligible and locations where available. Do not mention contact information or foundation name or grant name. Make description vague. Do not say it is a 'new grant' opportunity. Remember to EXCLUDE the foundation's name, grant's name or any specific program names, people's names, addresses, or URLs in the summary. No names. No addresses. No URLs. No dollar amounts. No deadlines. We do not want to reveal the foundation and grant identity to users.

        6. **Opportunity Title for Subscriber** (approximately 140 characters): Clean title for grant opportunity; includes the Grant name, grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant source. SEO friendly. Make sure Opportunity Title for Subscriber is not more than 150 characters.

        Here is the grant data to use:

        Grant Data: {grant_data}

        Return ONLY valid JSON in this exact format:
        {{
            "opportunity_title": "string",
            "h1_tag": "string",
            "meta_title": "string", 
            "meta_description": "string",
            "opportunity_teaser": "string",
            "opportunity_title_for_subscriber": "string"
        }}
        """)
        
        try:
            print("🤖 Making single OpenAI API call for all metadata...")
            result = self.llm.invoke(prompt.format(grant_data=grant_data)).content
            print("✅ Received response from OpenAI")
            print(f"📤 Raw response length: {len(result)} characters")
            
            # Clean JSON from markdown code blocks if present
            if result.startswith('```json'):
                result = result.strip('```json').strip('```').strip()
                print("🧹 Cleaned JSON markdown formatting")
            elif result.startswith('```'):
                result = result.strip('```').strip()
                print("🧹 Cleaned markdown formatting")
            
            # Parse JSON response
            print("🔍 Parsing JSON response...")
            metadata = json.loads(result)
            
            # Validate that all required fields are present
            required_fields = [
                "opportunity_title", "h1_tag", "meta_title", 
                "meta_description", "opportunity_teaser", "opportunity_title_for_subscriber"
            ]
            
            for field in required_fields:
                if field not in metadata:
                    raise ValueError(f"Missing required field: {field}")
            
            print("✅ All metadata fields generated successfully in single call!")
            print(f"📊 Fields generated: {', '.join(metadata.keys())}")
            
            return metadata
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {str(e)}")
            print(f"📄 Raw result: {result}")
            return {}
        except Exception as e:
            print(f"❌ Error generating metadata: {str(e)}")
            return {}

    def process_grant_opportunity_metadata(self, grant_description: str) -> Dict[str, str]:
        """
        Main function to process grant opportunity and generate metadata
        
        Args:
            grant_description (str): The consolidated grant description from grant-writer
            
        Returns:
            Dict[str, str]: Dictionary containing all 6 metadata fields in JSON format
        """
        print("🎬 Starting Grant Metadata Writer...")
        print(f"🌍 Processing grant opportunity data...")
        
        # Use single OpenAI call instead of multiple calls
        metadata = self.generate_all_metadata_single_call(grant_description)
        
        if metadata:
            print(f"\n📋 METADATA GENERATION RESULTS:")
            print(f"📊 Opportunity Title ({len(metadata.get('opportunity_title', ''))} chars): {metadata.get('opportunity_title', 'N/A')}")
            print(f"🏷️ H1 Tag ({len(metadata.get('h1_tag', ''))} chars): {metadata.get('h1_tag', 'N/A')}")
            print(f"🔖 Meta Title ({len(metadata.get('meta_title', ''))} chars): {metadata.get('meta_title', 'N/A')}")
            print(f"📄 Meta Description ({len(metadata.get('meta_description', ''))} chars): {metadata.get('meta_description', 'N/A')}")
            print(f"👥 Subscriber Title ({len(metadata.get('opportunity_title_for_subscriber', ''))} chars): {metadata.get('opportunity_title_for_subscriber', 'N/A')}")
            print(f"📋 Teaser ({len(metadata.get('opportunity_teaser', '').split())} words): Available")
            
            print("\n📋 Complete Metadata in JSON format:")
            print(json.dumps(metadata, indent=4))
        else:
            print("❌ No metadata could be generated")
        
        print("\n✨ Grant Metadata Writer completed!")
        return metadata

    def save_metadata_to_file(self, metadata: Dict[str, str], filename: str = "grant_metadata.json"):
        """
        Save metadata to a JSON file
        
        Args:
            metadata (Dict[str, str]): The generated metadata
            filename (str): Output filename
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)
            print(f"💾 Metadata saved to {filename}")
        except Exception as e:
            print(f"❌ Error saving metadata: {str(e)}")

# Function to work with existing grant-writer.py workflow
def generate_grant_metadata(grant_description: str, openai_api_key: str = None) -> Dict[str, str]:
    """
    Standalone function to generate grant metadata from grant description
    
    Args:
        grant_description (str): The consolidated grant description from grant-writer
        openai_api_key (str): OpenAI API key (optional, uses environment variable if not provided)
        
    Returns:
        Dict[str, str]: Dictionary containing all 6 metadata fields
    """
    metadata_writer = GrantMetadataWriter(openai_api_key)
    return metadata_writer.process_grant_opportunity_metadata(grant_description)

def main():
    """
    Main function to demonstrate the Grant Metadata Writer functionality
    """
    # Sample grant description (this would come from grant-writer.py output)
    sample_grant_description = """
🏢 **Organization Name**  
The Barbara Deming Memorial Fund & Money for Women

🎯 **Mission / Purpose**  
The Barbara Deming Memorial Fund and Money for Women aim to provide financial support and encouragement to feminist writers and visual artists, fostering creativity that embodies feminist values and promotes social justice.

📖 **Background Information**  
Founded in 1975 by feminist activist Barbara Deming, these organizations represent the oldest ongoing feminist granting agencies in the US and Canada. They are dedicated to supporting individual women and nonbinary artists through financial grants, ensuring that their work receives the recognition it deserves. Both funds are managed by volunteer Boards of Directors and judges who carefully evaluate applications.

🌍 **Geographic Focus**  
- **Eligible Locations:**  
  - The Barbara Deming Memorial Fund: Not specified  
  - Money for Women: United States and Canada  
  - Money for Women Support Grants: United States and Canada  

🗂 **Funding Areas & Interests**  
- Support for individual women writers and visual artists whose work exhibits feminist values.
- Encouragement for feminist writers and artists who identify as women, cis-women, trans-women, and/or nonbinary.
- Focus on high quality, originality, and an inclusive vision of social justice in artistic projects.

✅ **Eligibility Criteria**  
- **Barbara Deming Memorial Fund:** Individual women writers and visual artists whose work aligns with feminist values.  
- **Money for Women:** Feminist writers and visual artists identifying as women, cis-women, trans-women, and/or nonbinary, including nonprofits.  
- **Money for Women Support Grants:** Feminist writers and visual artists (cis, transgender, or nonbinary) with substantial work to show, residing in the US or Canada.

💰 **Funding Amounts / Grant Amounts**  
- **Barbara Deming Memorial Fund:** $500 - $2000  
- **Money for Women:** Not specified  
- **Money for Women Support Grants:** $500 - $2000  

📅 **Proposal Deadlines / Grant Cycles**  
- **Barbara Deming Memorial Fund:** Applications accepted annually from January 1 to January 31.  
- **Money for Women:** Specific deadlines not provided, but grants are awarded annually.  
- **Money for Women Support Grants:**  
  - January 1 - January 31, 2026 for Visual Art & Fiction  
  - January 1 - January 31, 2027 for Poetry & Nonfiction  

🔁 **Grant Frequency / Reapplication Rules**  
- **Barbara Deming Memorial Fund:** Annual  
- **Money for Women:** Annual  
- **Money for Women Support Grants:** Biennial; former grantees must wait three years before reapplying, and applicants may submit in only one genre each year.

💡 **Grant Programs & Awards**  
- **Barbara Deming Memorial Fund:** Financial grants for creative projects in writing and visual arts, focusing on feminist values.  
- **Money for Women:** Monetary support for feminist writers and visual artists, encouraging diverse artistic expressions.  
- **Money for Women Support Grants:** Financial assistance for individual feminist women in the arts, emphasizing originality and social justice.

📞 **Contact Information**  
- **Email:** Not specified  
- **Phone:** Not specified  
- **Address:** Not specified  

This comprehensive funding opportunity encompasses multiple grants aimed at empowering feminist artists and writers, encouraging applications from eligible individuals and organizations dedicated to feminist values.
    """
    
    # Initialize with OpenAI API key from environment
    metadata_writer = GrantMetadataWriter()  # Will automatically use OPENAI_API_KEY from .env
    
    print("🎯 GRANT METADATA WRITER")
    print("=" * 50)
    print("Generates 6 metadata fields for Grant Details Page")
    
    # Generate all metadata fields
    metadata = metadata_writer.process_grant_opportunity_metadata(sample_grant_description)
    
    # Save metadata to file
    if metadata:
        metadata_writer.save_metadata_to_file(metadata)
        print("\n" + "=" * 60)
        print("✅ Grant metadata generated successfully!")
        print("📄 Output: 6 fields ready for Grant Details Page")
    else:
        print("❌ Failed to generate metadata")

if __name__ == "__main__":
    main()

# Queries 

# Query #1:  ChatGPT query creates a title for the Opportunity Title

# Write a clean 70 characters Title for a grant opportunity; make the title vague; include the grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly.

# Query #2:  ChatGPT query creates text for the H1 Tag

# Write a clean 70 characters H1 tag for a grant opportunity; make the title vague; include the grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly.

# Query #3:  ChatGPT query creates text for the Meta Title

# Write a clean 70 characters Meta Title for a grant opportunity; make the title vague; include the grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly.

# Query #4:  ChatGPT query creates text for the Meta Description

# Write a clean 70 characters Meta Description that is different from the Meta Title for a grant opportunity; make the title vague; include the grant intent, grant amount that describes who the grant helps and specific causes. Do not mention grant sources. SEO friendly.

# Query #5: ChatGPT query creates content for the Opportunity Teaser:

# Write a clean, easy to understand 300-word summary with a description of the grant opportunity. Make the response vague. Do Not show icons. Do Not show bullets. Do not include any content source URLs for this summary.  Provide information such as grants for which states or regions, grants for nonprofits or businesses or individuals. Provide information to describe the intent of use for the funds.  Show the dollar amount of the grant or grants. Write about the grant opportunity for the specific grant, the grant benefits, the grant interests, identify if nonprofit organizations or small businesses or individuals are eligible for the grant and locations where the grant is available. Do not mention contact information or the name of the foundation or grant name. Make the description vague. Do not say it is a ‘new grant’ opportunity. 

# Query #6:  ChatGPT query creates text for the Opportunity Title for Subscriber

# Write a clean 120 characters Title for a grant opportunity; includes the Grant name include the grant intent, grant amount that describes who the grant helps and specific causes. Do not mentioned grant source. SEO friendly.

# Input = Mardown text with the collected data about the grant opportunity.
# Output = 6 fields of data in JSON format.

# Json format:
# {
#   "opportunity_title": "string",
#   "h1_tag": "string",
#   "meta_title": "string",
#   "meta_description": "string",
#   "opportunity_teaser": "string",
#   "opportunity_title_for_subscriber": "string"
# }

