from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import json
from datetime import datetime
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GrantWriter:
    def __init__(self, openai_api_key: str = None):
        """
        Initialize the Grant Writer with OpenAI API key
        Args:
            openai_api_key: Optional API key. If not provided, will use OPENAI_API_KEY from environment
        """
        if not openai_api_key:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file.")
        
        self.llm = ChatOpenAI(
            temperature=0.1, 
            model_name="gpt-4o-mini", 
            openai_api_key=openai_api_key
        )
        
    def is_deadline_expired(self, deadline_str: str) -> bool:
        """
        Check if the grant deadline has expired
        """
        if not deadline_str or deadline_str.lower() in ["not specified", "n/a", ""]:
            return False
            
        # Handle various deadline formats
        current_date = datetime.now()
        
        # Simple check for common expired indicators
        expired_indicators = ["closed", "expired", "past", "deadline passed"]
        if any(indicator in deadline_str.lower() for indicator in expired_indicators):
            return True
            
        # For more complex date parsing, you might want to add specific logic here
        # For now, we'll assume the deadline is valid if it doesn't contain expired indicators
        return False
    
    def filter_active_grants(self, grants_data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """
        Filter out grants with expired deadlines
        """
        active_grants = []
        for grant in grants_data:
            deadline = grant.get("proposal_deadline", "")
            if not self.is_deadline_expired(deadline):
                active_grants.append(grant)
            else:
                print(f"🚫 Filtered out expired grant: {grant.get('grant_name', 'Unknown')}")
        
        return active_grants
    
    def generate_consolidated_grant_description(self, grants_data: List[Dict[str, Any]], org_data: Dict[str, Any] = None) -> str:
        """
        Generate a single consolidated 500-word grant opportunity description from multiple grants data
        Optionally includes organization information for better context
        
        Args:
            grants_data: List of grant dictionaries
            org_data: Optional organization information dictionary
        """
        
        # Prepare organization context if provided
        org_context = ""
        if org_data:
            org_context = f"""
        
        📋 ADDITIONAL ORGANIZATION CONTEXT (use to enhance the description):
        Organization Name: {org_data.get('org_name', 'Not specified')}
        Organization Mission: {org_data.get('mission', 'Not specified')}
        Organization Background: {org_data.get('background', 'Not specified')}
        About Organization: {org_data.get('about', 'Not specified')}
        Organization Contact Info: {json.dumps(org_data.get('contact', {}), indent=2) if org_data.get('contact') else 'Not specified'}
        
        Use this organization information to provide better context and fill in any gaps in the grant data. If organization information conflicts with grant data, prioritize the grant data.
        """
        
        prompt = ChatPromptTemplate.from_template("""
        You are an expert grant writer who creates clean, professional, and comprehensive grant opportunity descriptions for The Grant Portal - an online grant directory.

        You have been provided with data from multiple grant opportunities from a foundation. Your task is to create ONE SINGLE consolidated 500-word professional opportunity description that synthesizes and combines all the ACTIVE grant information into a comprehensive funding opportunity description.

        📝 FORMATTING REQUIREMENTS:
        - Add appropriate icons (📊, 💰, 🎯, 📅, etc.) beside all section titles. make them as h3
        - Use bullet points for lists when appropriate
        - NO horizontal lines between text sections
        - NO source URLs in the description
        - Clean, readable formatting with proper spacing
        
        📋 CONTENT REQUIREMENTS:
        Create ONE description that includes:
        1. 🏢 Organization Name
        2. 📖 Background Information
        3. 🎯 Mission / Purpose - organization focus, funding priorities and interests in 100 words
        4. 🌍 Geographic Focus - All eligible locations
        5. 🗂 Funding Areas & Interests
        6. ✅ Eligibility Criteria - Identify if nonprofit organizations or small businesses or individuals are eligible for the grant
        7. 💰 Funding Amounts / Grant Amounts - Complete range of grant amounts (show the full spectrum from all grants)
        8. 📅 Proposal Deadlines / Grant Cycles - Include all relevant deadlines and cycles for grant proposals
        9. 🔁 Grant Frequency / Reapplication Rules - Describe if grants are awarded annually or not.
        10. 💡 Grant Programs & Awards - Bulleted List of short description of each grant provided by the foundation along with the URLs in the format url: <grant_url> - No hyperlink. The format should be url: <grant_url> only
        11. 📞 Contact Information - Include contact information with telephone number, email address and physical address.
                                                  
        Do not make up any information. Only use the data provided.
        
        ✅ CONSOLIDATION APPROACH:
        - Merge similar information rather than repeating it
        - Show the breadth of opportunities available
        - Create a unified narrative that flows naturally
        - Highlight the diverse range of funding available
        - Make it clear this represents multiple funding opportunities
        - Exactly 500 words (be precise)
        - Professional, engaging tone that encourages applications
        - If some information is missing or not specified, mention that to check on the foundation website
        {org_context}
        
        Multiple Grants Data:
        {grants_data}
        
        Write the single opportunity description now:
        """)
        
        try:
            formatted_data = json.dumps(grants_data, indent=2)
            result = self.llm.predict(prompt.format(grants_data=formatted_data, org_context=org_context))
            return result.strip()
        except Exception as e:
            print(f"❌ Error generating consolidated description: {e}")
            return f"Error generating consolidated description from {len(grants_data)} grants"
    

    
    def process_grants_consolidated(self, grants_json: List[Dict[str, Any]], org_data: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Process multiple grants and generate ONE consolidated description covering all opportunities
        
        Args:
            grants_json: List of grant dictionaries
            org_data: Optional organization information dictionary
        """
        print("🚀 Starting consolidated grant description generation...")
        
        if org_data:
            org_name = org_data.get('org_name', 'Unknown Organization')
            print(f"🏢 Including organization context: {org_name}")
        else:
            print("📝 No organization data provided - using grant data only")
        
        # Filter out expired grants
        active_grants = self.filter_active_grants(grants_json)
        print(f"📊 Processing {len(active_grants)} active grants out of {len(grants_json)} total grants")
        
        if not active_grants:
            print("❌ No active grants found to process")
            return {
                "title": "No Active Grants Available",
                "description": "No active grant opportunities are currently available.",
                "grant_count": 0,
                "grant_names": [],
                "org_data": org_data
            }
        
        print(f"\n📝 Generating consolidated description from {len(active_grants)} grants...")
        
        # Extract grant names for reference
        grant_names = [grant.get('grant_name', 'Unknown Grant') for grant in active_grants]
        print(f"🎯 Consolidating grants: {', '.join(grant_names)}")
        
        # Pass organization data to the description generator
        description = self.generate_consolidated_grant_description(active_grants, org_data)
        
        result = {
            "title": "Consolidated Grant Opportunities",
            "description": description,
            "grant_count": len(active_grants),
            "grant_names": grant_names,
            "source_urls": [grant.get('grant_url', '') for grant in active_grants if grant.get('grant_url')],
            "org_data": org_data  # Include org data in result for reference
        }
        
        print(f"✅ Successfully generated consolidated description covering {len(active_grants)} grant opportunities!")
        if org_data:
            print(f"🏢 Enhanced with organization context from: {org_data.get('org_name', 'N/A')}")
        return result
    

    
    def save_consolidated_description_to_file(self, consolidated_result: Dict[str, str], filename: str = "consolidated_grant_description.md"):
        """
        Save consolidated description to a text file
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(consolidated_result['description'])
            
        except Exception as e:
            print(f"❌ Error saving consolidated description to file: {e}")

def create_organization_data(org_name: str = None, mission: str = None, background: str = None, 
                           about: str = None, contact: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Helper function to create organization data dictionary
    
    Args:
        org_name: Organization name
        mission: Organization mission
        background: Organization background
        about: About the organization
        contact: Contact information dictionary with phone, email, address, other_info
        
    Returns:
        Dict containing organization data (all fields optional)
    """
    org_data = {}
    
    if org_name:
        org_data['org_name'] = org_name
    if mission:
        org_data['mission'] = mission
    if background:
        org_data['background'] = background
    if about:
        org_data['about'] = about
    if contact:
        org_data['contact'] = contact
        
    return org_data if org_data else None




def main():
    """
    Main function to demonstrate the Consolidated Grant Writer functionality with optional organization data
    """
    # Sample organization data (optional - demonstrates the new feature)
    sample_org_data = create_organization_data(
        org_name="Newcomb Institute at Tulane University",
        mission="To advance gender equity research and scholarly outputs, supporting work that offers insight and solutions to advance respect and equal opportunity for all people regardless of gender and inclusive of all gender identities.",
        background="The Newcomb Institute was established at Tulane University with a focus on advancing women's leadership and gender equity research. Founded as part of Tulane University's commitment to promoting gender equality and social justice.",
        about="The Newcomb Institute is a leading research and advocacy center focused on gender equity issues. We support faculty, students, and community members through various grant programs, research initiatives, and educational opportunities.",
        contact={
            "phone": "(504) 865-5238",
            "email": "newcomb@tulane.edu",
            "address": "200 Broadway, New Orleans, LA 70118",
            "other_info": {
                "website": "https://newcomb.tulane.edu",
                "social_media": {"twitter": "@NewcombInstitute"}
            }
        }
    )
    
    # Sample grant data for testing with multiple grants
    sample_grants = [
        {
            "grant_name": "Newcomb Institute Faculty Grants",
            "funding_priorities": "Advancing gender equity research and scholarly outputs, elimination of gender-based violence, advancement of sexual and/or reproductive health and justice, feminist civic engagement and leadership.",
            "types_of_grant": "Research Grants, Skau Art and Music Fund grants, Cross-School Planning Grants on Gender Equity",
            "eligibility_criteria": "Open to Tulane faculty members of all ranks, both tenure and non-tenure track, and from all schools at Tulane. Skau Art and Music Fund grants are open to faculty and staff in the art and music departments and the Newcomb Art Museum or other Tulane faculty with a compelling art or music-based project. Cross-School Planning Grants require collaboration across two schools within Tulane University.",
            "eligible_applicants": [
                "nonprofits"
            ],
            "eligible_locations": "Tulane University",
            "grant_amount_range": "Up to $25,000",
            "grant_amount": "Research Grants: up to $5,000, Skau Art and Music Fund grants: up to $10,000, Cross-School Planning Grants: up to $25,000",
            "proposal_deadline": "Fall cycle – October 15, 2025; Spring cycle – March 15, 2026",
            "recurrence": "Annual",
            "contact_info": {
                "email": "",
                "phone": "",
                "address": ""
            },
            "organization_info": "Newcomb Institute at Tulane University. The Institute's mission is to advance gender equity research and scholarly outputs. It supports work that offers insight and solutions to advance respect and equal opportunity for all people regardless of gender and inclusive of all gender identities. The Institute prioritizes funding applications from Newcomb Faculty Affiliates and is interested in proposals that include community engagement, undergraduate research assistants, or that benefit New Orleans and/or the Gulf South.",
            "grant_summary": "The Newcomb Institute at Tulane University offers faculty grants to support research projects that align with its mission of advancing gender equity. The grants are available in three categories: Research Grants, Skau Art and Music Fund grants, and Cross-School Planning Grants on Gender Equity. The Institute prioritizes projects that focus on eliminating gender-based violence, advancing sexual and reproductive health and justice, and promoting feminist civic engagement and leadership. Eligible applicants include Tulane faculty members from all disciplines and ranks, with specific eligibility criteria for each grant type. The maximum funding amounts vary, with Research Grants offering up to $5,000, Skau Art and Music Fund grants up to $10,000, and Cross-School Planning Grants up to $25,000. The grants are awarded in two cycles, with deadlines on October 15, 2025, and March 15, 2026. The Institute emphasizes the importance of community and student involvement in the projects and requires grant recipients to credit the Institute in their scholarly outputs. The Newcomb Institute aims to support projects that can lead to larger-scale funding opportunities and contribute to the broader understanding and implementation of gender equity approaches.",
            "grant_url": "https://newcomb.tulane.edu/faculty-grants"
        },
        {
            "grant_name": "Emily Schoenbaum Grant",
            "funding_priorities": "Projects that benefit the lives of women and girls, particularly in the New Orleans area, with a focus on sexual and reproductive health/rights/justice, gender-based violence, and feminist civic engagement.",
            "types_of_grant": "Project funding",
            "eligibility_criteria": "Individuals or nonprofit, IRS tax-exempt organizations in Louisiana. Preference for applications involving community organizations.",
            "eligible_applicants": [
                "Individuals",
                "Nonprofit organizations"
            ],
            "eligible_locations": "Louisiana",
            "grant_amount_range": "Up to $3000",
            "grant_amount": "Maximum $3000",
            "proposal_deadline": "Not specified",
            "recurrence": "Annual",
            "contact_info": {
                "email": "lwolford@tulane.edu",
                "phone": "",
                "address": ""
            },
            "organization_info": "The Emily Schoenbaum Grant Program was founded in 1999 by Emily Schoenbaum, a Newcomb College alumna, and is administered by Newcomb Institute. The program aims to support projects that benefit women and girls, with a particular focus on the New Orleans area. The Newcomb Institute is part of Tulane University and focuses on gender equity and women's leadership.",
            "grant_summary": "The Emily Schoenbaum Grant is designed to support projects that positively impact the lives of women and girls, especially in the New Orleans area. The grant prioritizes initiatives related to sexual and reproductive health, gender-based violence, and feminist civic engagement. Eligible applicants include individuals and nonprofit organizations in Louisiana, with a preference for those involving community organizations. The maximum funding available per project is $3000. The grant is administered by the Newcomb Institute at Tulane University, which focuses on gender equity and women's leadership. The program was established in 1999 by Emily Schoenbaum, a Newcomb College alumna. While the exact proposal deadline is not specified, the grant appears to be offered annually. For more information, interested parties can contact Laura Wolford, Associate Director of Newcomb Institute, via email at lwolford@tulane.edu.",
            "grant_url": "https://newcomb.tulane.edu/emily-schoenbaum-grant"
        },
        {
            "grant_name": "Newcomb Institute Grant",
            "funding_priorities": "Protection of sexual and reproductive health and rights; Prevention of gender-based and discriminatory violence, including intimate partner violence, sexual harassment and sexual assault, and homophobic and transphobic discrimination; Strengthening feminist civic and community engagement through the development of student leaders and community members as change agents.",
            "types_of_grant": "Research and scholarly work grants",
            "eligibility_criteria": "Projects must connect to the Institute’s mission of advancing gender equity research and scholarly outputs.",
            "eligible_applicants": [
                "Tulane faculty members",
                "Tulane students"
            ],
            "eligible_locations": "Tulane University",
            "grant_amount_range": "Not specified",
            "grant_amount": "Not specified",
            "proposal_deadline": "Not specified",
            "recurrence": "Not specified",
            "contact_info": {
                "email": "Not specified",
                "phone": "Not specified",
                "address": "Not specified"
            },
            "organization_info": "Newcomb Institute provides grant funding to the community, Tulane faculty members, and Tulane students for projects that connect to the Institute’s mission of advancing gender equity research and scholarly outputs. The Institute values applications focused on its current priority areas, including protection of sexual and reproductive health and rights, prevention of gender-based and discriminatory violence, and strengthening feminist civic and community engagement.",
            "grant_summary": "The Newcomb Institute Grant is designed to support projects that align with the Institute's mission of advancing gender equity research and scholarly outputs. The grant welcomes applications from any discipline and aims to fund scholars from across all schools and departments at Tulane University. The funding priorities include protection of sexual and reproductive health and rights, prevention of gender-based and discriminatory violence, and strengthening feminist civic and community engagement. Eligible applicants are Tulane faculty members and students who can propose projects that offer insight and solutions to advance respect and equal opportunity for all people without discrimination. The grant is open to any area of focus on issues of gender equity, with a particular interest in the Institute's current priority areas. While specific grant amounts and deadlines are not provided, the grant supports research and scholarly work that contributes to the advancement of gender equity.",
            "grant_url": "https://newcomb.tulane.edu/grantopportunities"
        },
        {
            "grant_name": "Undergraduate Student Grants",
            "funding_priorities": "Advancing gender equity, elimination of gender-based violence, advancement of sexual and/or reproductive health and justice, feminist civic engagement and leadership.",
            "types_of_grant": "Research grants, Conference travel grants",
            "eligibility_criteria": "Full-time, undergraduate Tulane University students. Projects must have academic merit and connect to the Newcomb Institute’s core focus on gender equity.",
            "eligible_applicants": [
                "individuals"
            ],
            "eligible_locations": "International travel must be to countries cleared from the U.S. Department of State travel warning list.",
            "grant_amount_range": "Up to $4000 for research grants, up to $2000 for conference grants",
            "grant_amount": "Maximum $4000 for research grants, maximum $2000 for conference grants",
            "proposal_deadline": "Fall cycle – October 15, 2025; Spring cycle – March 15, 2026",
            "recurrence": "Annual",
            "contact_info": {
                "email": "lwolford@tulane.edu",
                "phone": "",
                "address": ""
            },
            "organization_info": "Newcomb Institute at Tulane University focuses on advancing gender equity through research and scholarly outputs. It supports undergraduate students in independent research projects and conference travel related to gender equity.",
            "grant_summary": "The Undergraduate Student Grants offered by the Newcomb Institute at Tulane University are designed to support full-time undergraduate students in conducting independent research and attending conferences related to gender equity. The grants prioritize projects that focus on eliminating gender-based violence, advancing sexual and reproductive health and justice, and promoting feminist civic engagement and leadership. Students from diverse disciplines, including arts, humanities, social sciences, health, medicine, engineering, and law, are encouraged to apply. The grants are available to all students regardless of gender identity. Research grants provide up to $4000, while conference travel grants offer up to $2000. The grants are awarded annually, with proposal deadlines on October 15, 2025, for the fall cycle and March 15, 2026, for the spring cycle. Eligible applicants must be full-time undergraduate students at Tulane University, and projects must align with the Newcomb Institute's mission of gender equity. The grants do not cover tuition, fees, or personal property items, and all travel must be booked through the Concur travel system. The Newcomb Institute emphasizes the importance of academic merit and the connection to gender equity in all funded projects.",
            "grant_url": "https://newcomb.tulane.edu/content/student-grants"
        },
        {
            "grant_name": "Newcomb Institute Internship Program",
            "funding_priorities": "Gender equity and women's empowerment",
            "types_of_grant": "Paid internship",
            "eligibility_criteria": "Undergraduate students interested in gender equity and women's empowerment",
            "eligible_applicants": [
                "individuals"
            ],
            "eligible_locations": "Not specified",
            "grant_amount_range": "$15 per hour for up to 15 hours per week",
            "grant_amount": "$15 per hour",
            "proposal_deadline": "Ongoing",
            "recurrence": "Annual",
            "contact_info": {
                "email": "jqiu@tulane.edu",
                "phone": "",
                "address": ""
            },
            "organization_info": "Newcomb Institute coordinates with local, national and global organizations as well as Tulane faculty to provide paid internships for undergraduates. The program is supported by the Donna and Richard Esteves Fund for Reproductive Rights and Reproductive Health, the Bonnie and William Chapman Fund for Reproductive Health, Newcomb Institute Endowment Funding, and the generosity of donors.",
            "grant_summary": "The Newcomb Institute Internship Program offers undergraduate students the opportunity to engage in paid internships focused on gender equity and women's empowerment. Participants can earn $15 per hour for up to 15 hours per week, gaining valuable skills, knowledge, and connections in the field. The program is supported by various funds and donors, including the Donna and Richard Esteves Fund for Reproductive Rights and Reproductive Health and the Bonnie and William Chapman Fund for Reproductive Health. The internship positions are designed to build professional skills and provide experiential learning opportunities. Students will also benefit from biweekly meetings with leaders in the field and other interns. The application process is ongoing, and the program is coordinated by the Newcomb Institute in collaboration with Tulane faculty and various organizations.",
            "grant_url": "https://newcomb.tulane.edu/grantsinternships"
        }
    ]

    
    # Initialize with OpenAI API key from environment
    grant_writer = GrantWriter()  # Will automatically use OPENAI_API_KEY from .env
    
    print("🎯 CONSOLIDATED GRANT WRITER WITH ORGANIZATION DATA")
    print("=" * 60)
    print("Creates comprehensive descriptions with optional organization context")
    
    # Demonstrate with organization data
    print("\n🏢 EXAMPLE 1: WITH ORGANIZATION DATA")
    print("-" * 40)
    consolidated_result_with_org = grant_writer.process_grants_consolidated(sample_grants, sample_org_data)
    
    print(f"\n📄 CONSOLIDATED DESCRIPTION (WITH ORG CONTEXT)")
    print("=" * 60)
    print(f"📊 Total Grants: {consolidated_result_with_org['grant_count']}")
    print(f"🏢 Organization: {consolidated_result_with_org.get('org_data', {}).get('org_name', 'N/A')}")
    print(f"🎯 Grant Programs: {', '.join(consolidated_result_with_org['grant_names'])}")
    print("\n📝 Description:")
    print("-" * 40)
    print(consolidated_result_with_org['description'])
    
    # Demonstrate without organization data (backward compatibility)
    print("\n" + "=" * 60)
    print("🏢 EXAMPLE 2: WITHOUT ORGANIZATION DATA (BACKWARD COMPATIBLE)")
    print("-" * 40)
    consolidated_result_no_org = grant_writer.process_grants_consolidated(sample_grants)
    
    print(f"\n📄 CONSOLIDATED DESCRIPTION (GRANT DATA ONLY)")
    print("=" * 60)
    print(f"📊 Total Grants: {consolidated_result_no_org['grant_count']}")
    print(f"🎯 Grant Programs: {', '.join(consolidated_result_no_org['grant_names'])}")
    
    # Save both versions to files
    grant_writer.save_consolidated_description_to_file(consolidated_result_with_org, "consolidated_with_org.md")
    grant_writer.save_consolidated_description_to_file(consolidated_result_no_org, "consolidated_no_org.md")
    
    print("\n" + "=" * 60)
    print("✅ Grant descriptions generated successfully!")
    print("📄 Output: Enhanced descriptions with optional organization context")
    print("🔄 Backward compatible - organization data is completely optional")

if __name__ == "__main__":
    main()
