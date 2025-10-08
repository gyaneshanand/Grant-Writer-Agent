from bs4 import BeautifulSoup
import requests
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel
import re
import json
import trafilatura

# Step 1: Schema
class Grant(BaseModel):
    grant_name: str = "Not specified"
    funding_priorities: str = "Not specified"
    types_of_grant: str = "Not specified"
    eligibility_criteria: str = "Not specified"
    eligible_applicants: list = []
    eligible_locations: str = "Not specified"
    grant_amount_range: str = "Not specified"
    grant_amount: str = "Not specified"
    proposal_deadline: str = "Not specified"
    recurrence: str = "Not specified"
    contact_info: dict = {"email": "Not specified", "phone": "Not specified", "address": "Not specified"}
    organization_info: str = "Not specified"
    grant_summary: str = "Not specified"
    grant_url: str = "Not specified"

# Step 2: Scrape pages
def scrape_site(url):
    print(f"🔍 Starting to scrape site: {url}")
    r = requests.get(url)
    print(f"✅ Successfully fetched main page, status code: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    links = [a['href'] for a in soup.find_all('a', href=True)]
    print(f"📄 Found {len(links)} total links on the page")
    
    # Filter and fix relative URLs
    grant_links = []
    for l in links:
        if any(x in l.lower() for x in ["grant", "apply", "fund", "fellowship", "opportunity", "scholarship", "award", "funding", "faq", "eligibility", "criteria", "how-to-apply", "guidelines", "about", "programs"]):
            original_link = l
            # Fix relative URLs
            if l.startswith('/'):
                l = url.rstrip('/') + l
            elif not l.startswith('http'):
                l = url.rstrip('/') + '/' + l
            grant_links.append(l)
            print(f"🎯 Found potential grant link: {original_link} -> {l}")

    # Always include the main URL
    if url not in grant_links:
        grant_links.append(url)
        print(f"🎯 Added main URL to grant links: {url}")

    # remove duplicates
    grant_links = list(set(grant_links))

    print(f"✨ Total grant-related links found: {len(grant_links)}")
    # print the list of links
    print("📋 Grant-related links:")
    for gl in grant_links:
        print(f"   - {gl}")

    return grant_links

def go_one_level_deeper(grant_links, main_url):
    new_links = []
    for gl in grant_links:
        if gl != main_url:
            sub_links = scrape_site(gl)
            new_links.extend(sub_links)
    return grant_links + new_links

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
def extract_grant_info(page_text):
    print("🤖 Starting LLM extraction process...")
    OPEN_AI_API_KEY = "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"
    llm = ChatOpenAI(temperature=0.3, 
                     model_name="gpt-4o-mini", 
                     openai_api_key=OPEN_AI_API_KEY)
    print("🔗 Connected to OpenAI API")
    
    prompt = ChatPromptTemplate.from_template("""
    You are an expert grant writer and researcher. You will help extract detailed information about grants from web page text.

    Extract the following fields about ACTIVE grants only from this page. Please think and reason that this is a actual grant/scholarship opportunity.

    1. Grant Name - the grant or funding opportunity name if available elase try to create a suitable name based on the content if not explicitly mentioned.
    2. Funding priorities and interests
    3. Types of grant
    4. Eligibility criteria
    5. Eligible applicants ( nonprofits / individuals / small businesses). Identify if nonprofit organizations or small businesses or individuals are eligible for the grant.
    6. Eligible funding locations
    7. Range of grant amount
    8. Specific grant funding amount
    9. Proposal deadline
    10. Annual or recurring
    11. Contact info (telephone, email, physical address)
    12. Organization information about the grant provider. Include the organization’s name, about us, organization’s mission or focus, background information, types of grants if available.
    13. 300 words summary of the grant which should be comprehensive and cover all important aspects of the grant. Keep this to the point and avoid fluff.

    Include as much detail as possible in each field. Please be very sure that the grant is ACTIVE and accepting applications. If the grant is closed or not currently accepting applications do not include it.
    Avoid making up information if not available on the page.

    Here is the Text from the page: {text}

    Return ONLY valid JSON in this exact format:
    {{
        "grant_name": "string",
        "funding_priorities": "string", 
        "types_of_grant": "string",
        "eligibility_criteria": "string",
        "eligible_applicants": ["string1", "string2"],
        "eligible_locations": "string",
        "grant_amount_range": "string",
        "grant_amount": "string", 
        "proposal_deadline": "string",
        "recurrence": "string",
        "contact_info": {{"email": "string", "phone": "string", "address": "string"}},
        "organization_info": "string",
        "grant_summary": "string",

    }}
    """)
    
    print(f"📝 Processing text of length: {len(page_text)} characters")
    result = llm.predict(prompt.format(text=page_text))
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
        grant = Grant.model_validate_json(result)
        print("✅ Successfully parsed grant information")
        
        # Check if this is a valid grant (has meaningful content)
        if not grant.grant_name or grant.grant_name == "Not specified" or grant.grant_name.strip() == "":
            print("⚠️ No valid grant information found on this page - skipping")
            return None
            
        return grant
    except Exception as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"📄 Raw result: {result}")
        
        # Try to create a default Grant object if JSON is completely empty
        try:
            if result.strip() in ['{}', '']:
                print("📝 Empty response detected - no grant information on this page")
                return None
            else:
                print("🔄 Attempting to create default Grant object...")
                return Grant()
        except Exception as fallback_error:
            print(f"❌ Fallback creation failed: {fallback_error}")
            return None

# Step 4: Run pipeline
def run_pipeline(url):
    print(f"🚀 Starting pipeline for URL: {url}")
    pages = scrape_site(url)
    print(f"📊 Processing {len(pages)} pages for grant information...")
    
    grants = []
    for i, p in enumerate(pages, 1):
        print(f"\n📄 Processing page {i}/{len(pages)}: {p}")
        try:
            # Skip if URL is not properly formed
            if not p.startswith('http'):
                print(f"⚠️ Skipping invalid URL: {p}")
                continue
            
            # Use the new HTML extraction function
            html_content, extracted_text = get_html_content_and_extract_text(p)
            
            if not extracted_text:
                print(f"❌ Failed to extract content from: {p}")
                continue
            
            grant = extract_grant_info(extracted_text)
            
            # Skip if no grant information was found
            if grant is None:
                print(f"⏭️ No grant information found on this page - skipping")
                continue

            grant.grant_url = p  # Add the URL to the grant data
                
            print(f"🎯 Grant extracted: {grant.grant_name}")
            
            if "closed" not in grant.proposal_deadline.lower():
                grants.append(grant.model_dump())
                print(f"✅ Added grant to results (deadline: {grant.proposal_deadline})")
            else:
                print(f"❌ Skipped closed grant (deadline: {grant.proposal_deadline})")
                
        except Exception as e:
            print(f"❌ Error processing {p}: {str(e)}")
            
    print(f"\n🎉 Pipeline completed! Found {len(grants)} active grants")
    # PRINT GRANTS IN JSON FORMAT
    print("\n📋 Grants in JSON format:")
    print(json.dumps(grants, indent=4))
    return grants

# main execution
if __name__ == "__main__":
    print("🎬 Starting Grant Writer Agent...")
    url = "https://www.voiceswithimpact.com/"
    print(f"🌍 Target website: {url}")
    
    grants = run_pipeline(url)
    
    print(f"\n📋 FINAL RESULTS:")
    print(f"🏆 Total active grants found: {len(grants)}")
    
    for i, g in enumerate(grants, 1):
        print(f"\n🎯 Grant #{i}:")
        print(f"   Name: {g.get('grant_name', 'N/A')}")
        print(f"   Deadline: {g.get('proposal_deadline', 'N/A')}")
        print(f"   Amount: {g.get('grant_amount', 'N/A')}")
        print(f"   Full details: {g}")

    print("\n✨ Grant Data Collector Agent completed!")


# https://www.1for2edu.com/
# https://vikingfoundation.godaddysites.com/
# https://mathersfoundation.org/how-to-apply/
# https://www.acceleratefortworth.org/sbag/
# https://www.templeton.org/