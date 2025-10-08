from bs4 import BeautifulSoup
import requests
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel
import re
import json
import trafilatura

# Step 1: Schema
class Organization(BaseModel):
    org_name: str = "Not specified"
    mission: str = "Not specified"
    background: str = "Not specified"
    about: str = "Not specified"
    contact: dict = {
        "phone": "Not specified", 
        "email": "Not specified", 
        "address": "Not specified",
        "other_info": "Not specified"
    }

# Step 2: Scrape pages
def scrape_site(url):
    print(f"🔍 Starting to scrape site: {url}")
    r = requests.get(url)
    print(f"✅ Successfully fetched main page, status code: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    links = [a['href'] for a in soup.find_all('a', href=True)]
    print(f"📄 Found {len(links)} total links on the page")
    
    # Filter and fix relative URLs for organization-relevant pages
    org_links = []
    for l in links:
        if any(x in l.lower() for x in ["home", "about", "faq", "contact", "reach", "mission", "vision", "history", "background", "team", "staff", "board", "leadership", "who-we-are", "our-story", "get-in-touch", "reach-us", "contact-us", "about-us", "mission", "our-vision", "what-we-do", "help", "support"]):
            original_link = l
            # Fix relative URLs
            if l.startswith('/'):
                l = url.rstrip('/') + l
            elif not l.startswith('http'):
                l = url.rstrip('/') + '/' + l
            org_links.append(l)
            print(f"🎯 Found potential organization link: {original_link} -> {l}")

    # Always include the main URL
    if url not in org_links:
        org_links.append(url)
        print(f"🎯 Added main URL to organization links: {url}")

    # remove duplicates
    org_links = list(set(org_links))

    print(f"✨ Total organization-related links found: {len(org_links)}")
    # print the list of links
    print("📋 Organization-related links:")
    for ol in org_links:
        print(f"   - {ol}")

    return org_links

# Step 2.5: Extract HTML content and main article text
def get_html_content_and_extract_text(url):
    """
    Fetch HTML content from URL and extract main article text using trafilatura.
    Returns both raw HTML and cleaned text content.
    """
    print(f"🌐 Fetching content from: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"✅ Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch page, status: {response.status_code}")
            return None, None
            
        html_content = response.text
        print(f"📝 Raw HTML content length: {len(html_content)} characters")
        
        # Extract main article text using trafilatura
        print("🔧 Extracting main article text with trafilatura...")
        extracted_text = trafilatura.extract(html_content)
        
        if extracted_text:
            print(f"✨ Extracted clean text length: {len(extracted_text)} characters")
        else:
            print("⚠️ Trafilatura extraction failed, falling back to raw HTML")
            extracted_text = html_content
            
        return html_content, extracted_text
        
    except requests.exceptions.Timeout:
        print("⏰ Request timed out")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {str(e)}")
        return None, None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None, None

# Step 3: Extract info with LLM
def extract_organization_info(page_texts):
    print("🤖 Starting LLM extraction process...")
    OPEN_AI_API_KEY = "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"
    llm = ChatOpenAI(temperature=0.3, 
                     model_name="gpt-4o-mini", 
                     openai_api_key=OPEN_AI_API_KEY)
    print("🔗 Connected to OpenAI API")
    
    # Combine all page texts for comprehensive analysis
    combined_text = "\n\n--- NEW PAGE ---\n\n".join(page_texts)
    
    prompt = ChatPromptTemplate.from_template("""
    You are an expert researcher analyzing organization websites providing grants. Extract information about the organization from the provided web page text.

    Extract the following fields about the organization:

    1. Organization Name - the official name of the organization/foundation
    2. Mission - organization's mission statement, focus areas, funding priorities and interests. What kind of grants do they provide?
    3. Background - historical background, when it was founded, key milestones
    4. About - comprehensive about section describing what the organization does, their programs, initiatives
    5. Contact Information:
       - Phone number(s)
       - Email address(es) 
       - Physical address
       - Other contact info (social media, website forms, etc.)

    Include as much detail as possible in each field. Be comprehensive and thorough.
    Avoid making up information if not available on the pages.
    If multiple pages contain similar information, consolidate and provide the most complete version.

    Here is the combined text from all organization pages: {text}

    Return ONLY valid JSON in this exact format:
    {{
        "org_name": "string",
        "mission": "string", 
        "background": "string",
        "about": "string",
        "contact": {{
            "phone": "string",
            "email": "string", 
            "address": "string",
            "other_info": "json object with any other contact details or empty json if none"
        }}
    }}
    """)
    
    print(f"📝 Processing combined text of length: {len(combined_text)} characters")
    result = llm.predict(prompt.format(text=combined_text))
    print("✅ Received response from LLM")
    print(f"📤 Raw LLM response: {result[:200]}...")
    
    # Clean JSON from markdown code blocks if present
    if result.startswith('```json'):
        result = result.strip('```json').strip('```').strip()
        print("🧹 Cleaned JSON markdown formatting")
    elif result.startswith('```'):
        result = result.strip('```').strip()
        print("🧹 Cleaned markdown formatting")
    
    try:
        print("🔍 Attempting to parse JSON...")
        organization = Organization.model_validate_json(result)
        print("✅ Successfully parsed organization information")
        
        # Check if this contains meaningful organization information
        if not organization.org_name or organization.org_name == "Not specified" or organization.org_name.strip() == "":
            print("⚠️ No valid organization information found - creating minimal object")
            
        return organization
    except Exception as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"📄 Raw result: {result}")
        
        # Try to create a default Organization object if JSON is problematic
        try:
            print("🔄 Attempting to create default Organization object...")
            return Organization()
        except Exception as fallback_error:
            print(f"❌ Fallback creation failed: {fallback_error}")
            return Organization()

# Step 4: Run pipeline
def run_pipeline(foundation_url):
    print(f"🚀 Starting pipeline for Foundation URL: {foundation_url}")
    pages = scrape_site(foundation_url)
    print(f"📊 Processing {len(pages)} pages for organization information...")
    
    page_texts = []
    for i, p in enumerate(pages, 1):
        print(f"\n📄 Processing page {i}/{len(pages)}: {p}")
        try:
            # Skip if URL is not properly formed
            if not p.startswith('http'):
                print(f"⚠️ Skipping invalid URL: {p}")
                continue
            
            # Use the HTML extraction function
            html_content, extracted_text = get_html_content_and_extract_text(p)
            
            if not extracted_text:
                print(f"❌ Failed to extract content from: {p}")
                continue
            
            page_texts.append(extracted_text)
            print(f"✅ Successfully extracted text from page {i}")
                
        except Exception as e:
            print(f"❌ Error processing {p}: {str(e)}")
    
    if not page_texts:
        print("❌ No page content was successfully extracted")
        return None
    
    print(f"\n🔍 Analyzing content from {len(page_texts)} pages...")
    organization = extract_organization_info(page_texts)
    
    if organization:
        org_data = organization.model_dump()
        print(f"\n🎉 Pipeline completed! Organization information extracted")
        print("\n📋 Organization data in JSON format:")
        print(json.dumps(org_data, indent=4))
        return org_data
    else:
        print("❌ Failed to extract organization information")
        return None

# main execution
def collect_organization_data(foundation_url):
    """
    Main function to collect organization data from a foundation URL
    
    Args:
        foundation_url (str): The URL of the foundation/organization website
        
    Returns:
        dict: Organization data in JSON format or None if failed
    """
    print("🎬 Starting Organization Data Collector...")
    print(f"🌍 Target foundation website: {foundation_url}")
    
    org_data = run_pipeline(foundation_url)
    
    if org_data:
        print(f"\n📋 FINAL RESULTS:")
        print(f"🏢 Organization: {org_data.get('org_name', 'N/A')}")
        print(f"📧 Contact Email: {org_data.get('contact', {}).get('email', 'N/A')}")
        print(f"📞 Contact Phone: {org_data.get('contact', {}).get('phone', 'N/A')}")
        print(f"📍 Address: {org_data.get('contact', {}).get('address', 'N/A')}")
    else:
        print("❌ No organization data could be extracted")
    
    print("\n✨ Organization Data Collector completed!")
    return org_data

if __name__ == "__main__":
    # Example usage
    foundation_url = "https://reckoning.press"
    organization_data = collect_organization_data(foundation_url)
    
    if organization_data:
        print(f"\n🎯 Successfully collected data for: {organization_data.get('org_name', 'Unknown Organization')}")
    else:
        print("❌ Failed to collect organization data")

# Example URLs to test:
# https://www.voiceswithimpact.com/
# https://www.1for2edu.com/
# https://vikingfoundation.godaddysites.com/
# https://mathersfoundation.org/
# https://www.templeton.org/