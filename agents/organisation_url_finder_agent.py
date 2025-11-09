"""
Organization URL Finder Agent

This agent finds the official website URL of a given organization using LangGraph and Tavily Search.

Input: Name of the Organization (and optional foundation data)
Output: Official Website URL of the Organization
"""

import os
import re
import requests
from typing import TypedDict, Optional, Dict, Any, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# Load environment variables
load_dotenv()

# System prompt for the agent
SYSTEM_PROMPT = """
You are an expert foundation research assistant using tavily_search to find official foundation websites.

AVAILABLE TOOLS:
- tavily_search: Search for information using Tavily Search API  
- validate_url: Check if a URL contains foundation/grant content

{foundation_info}

MISSION: Find the PRIMARY official website URL for the given organization.

SEARCH METHODOLOGY:
1. Start the search with "[Foundation Name] foundation official website"
2. Then try: "[Foundation Name] foundation .org"
3. If no clear result, try: "[Foundation Name] grants foundation homepage"

ANALYSIS CRITERIA:
- Look for URLs that end with .org, .com, or similar domains
- Prioritize results that clearly match the foundation name
- Use validate_url tool to check if URLs contain foundation content
- Avoid directory listing websites like foundationcenter.org, guidestar.org, charitynavigator.org, grantable.co, grantmakers.io, instrumentl.com, grantadvisor.org, intellispect.co, taxexemptworld.com

VALIDATION REQUIREMENTS:
- Must be the organization's primary domain (not subdirectories)
- Prefer .org domains for foundations
- Avoid news articles, Wikipedia, or third-party sites
- Use validate_url tool to confirm foundation content exists

SUCCESS CRITERIA:
- URL loads successfully
- Matches the organization name clearly

OUTPUT FORMAT: Return ONLY the verified URL, no explanations or additional text.
"""


# Define the state structure for the graph
class AgentState(TypedDict):
    """State for the URL finder agent"""
    organization_name: str
    foundation_data: Optional[Dict[str, Any]]
    messages: List[Any]
    url: Optional[str]
    attempts: int
    max_attempts: int
    error: Optional[str]


# Tool functions
def validate_url(url: str, verbose: bool = False) -> str:
    """
    Validates if a URL contains foundation or grant content.
    
    Args:
        url: The URL to validate
        verbose: Show validation details
        
    Returns:
        The URL if valid, empty string otherwise
    """
    try:
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        if verbose:
            print(f"\n      🌐 Fetching URL: {url}")
        
        # Fetch the URL
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; FoundationFinder/1.0)'
        })
        response.raise_for_status()
        
        if verbose:
            print(f"      ✓ HTTP {response.status_code} - Page loaded successfully")
        
        # Check content
        text = response.text.lower()
        
        # Check for foundation/grant keywords
        has_grant = "grant" in text
        has_foundation = "foundation" in text
        
        if verbose:
            print(f"      🔍 Content analysis:")
            print(f"         - Contains 'grant': {has_grant}")
            print(f"         - Contains 'foundation': {has_foundation}")
        
        if has_grant or has_foundation:
            return url
        return ""
        
    except requests.RequestException as e:
        if verbose:
            print(f"      ✗ Request failed: {e}")
        return ""
    except Exception as e:
        if verbose:
            print(f"      ✗ Unexpected error: {e}")
        return ""


class OrganisationURLFinderAgent:
    """
    LangGraph-based agent to find organization URLs using Tavily Search.
    """
    
    def __init__(
        self, 
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_attempts: int = 1,
        verbose: bool = True
    ):
        """
        Initialize the URL finder agent.
        
        Args:
            model: OpenAI model to use
            temperature: Temperature for LLM
            max_attempts: Maximum search attempts
            verbose: Show agent's thinking process
        """
        self.model = model
        self.temperature = temperature
        self.max_attempts = max_attempts
        self.verbose = verbose
        
        # Initialize LLM
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        
        # Initialize tools
        self.tavily_tool = TavilySearchResults(
            max_results=10,
            include_answer=True,
            include_raw_content=True,
            api_key=os.getenv("TAVILY_API_KEY")
        )
        
        # Create the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create graph
        workflow = StateGraph(AgentState)
        
        # Define nodes
        workflow.add_node("search", self._search_node)
        workflow.add_node("process", self._process_node)
        
        # Define edges
        workflow.set_entry_point("search")
        workflow.add_edge("search", "process")
        workflow.add_conditional_edges(
            "process",
            self._should_continue,
            {
                "continue": "search",
                "end": END
            }
        )
        
        return workflow.compile()
    
    def _search_node(self, state: AgentState) -> AgentState:
        """Execute search based on current state"""
        
        org_name = state["organization_name"]
        attempts = state["attempts"]
        foundation_data = state.get("foundation_data", {})
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"🔍 SEARCH NODE - Attempt {attempts + 1}/{state['max_attempts']}")
            print(f"{'='*60}")
        
        # Build foundation info string
        foundation_info = ""
        if foundation_data:
            foundation_info = f"\nFoundation Data:\n"
            for key, value in foundation_data.items():
                if value:
                    foundation_info += f"- {key}: {value}\n"
            if self.verbose:
                print(f"\n📋 Foundation Context:{foundation_info}")
        
        # Build search query based on attempt number
        if attempts == 0:
            query = f"{org_name} foundation official website"
        elif attempts == 1:
            query = f"{org_name} foundation .org"
        else:
            query = f"{org_name} grants foundation homepage"
        
        if self.verbose:
            print(f"\n🔎 Search Query: '{query}'")
        
        # Perform search
        try:
            if self.verbose:
                print(f"\n⏳ Calling Tavily Search API...")
            
            search_results = self.tavily_tool.invoke({"query": query})
            
            if self.verbose:
                print(f"\n✅ Received {len(search_results)} search results:")
                for idx, result in enumerate(search_results, 1):
                    url = result.get('url', 'N/A')
                    title = result.get('title', 'N/A')
                    print(f"   {idx}. {title}")
                    print(f"      URL: {url}")
            
            # Build system message
            system_msg = SYSTEM_PROMPT.format(foundation_info=foundation_info)
            
            # Build user message with search results
            results_text = f"Search query: {query}\n\nSearch results:\n"
            for idx, result in enumerate(search_results, 1):
                url = result.get('url', 'N/A')
                content = result.get('content', 'N/A')
                results_text += f"\n{idx}. URL: {url}\n   Content: {content}\n"
            
            user_msg = f"Organization: {org_name}\n{results_text}\n\nPlease analyze these results and return ONLY the best official URL for {org_name}."
            
            if self.verbose:
                print(f"\n🤖 Calling LLM ({self.model}) to analyze results...")
            
            # Call LLM
            messages = [
                SystemMessage(content=system_msg),
                HumanMessage(content=user_msg)
            ]
            
            response = self.llm.invoke(messages)
            
            if self.verbose:
                print(f"\n💬 LLM Response:")
                print(f"   {response.content}")
            
            # Update state
            state["messages"] = messages + [response]
            state["attempts"] = attempts + 1
            
        except Exception as e:
            if self.verbose:
                print(f"\n❌ Search Error: {str(e)}")
            state["error"] = f"Search error: {str(e)}"
            state["attempts"] = state["max_attempts"]  # Stop retrying
        
        return state
    
    def _process_node(self, state: AgentState) -> AgentState:
        """Process the search results and validate URL"""
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"⚙️  PROCESS NODE - Validating Results")
            print(f"{'='*60}")
        
        if state.get("error"):
            if self.verbose:
                print(f"\n⚠️  Skipping validation due to error: {state['error']}")
            return state
        
        # Extract URL from the last message
        if state["messages"]:
            last_message = state["messages"][-1]
            content = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            if self.verbose:
                print(f"\n🔍 Extracting URLs from LLM response...")
            
            # Extract URL using regex
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, content)
            
            if not urls:
                if self.verbose:
                    print(f"   No HTTP(S) URLs found, trying domain pattern...")
                # Try to extract domain-like strings
                domain_pattern = r'(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
                urls = re.findall(domain_pattern, content)
            
            if self.verbose:
                print(f"\n📝 Found {len(urls)} potential URL(s):")
                for url in urls:
                    print(f"   - {url}")
            
            # Validate the first URL found
            for idx, url in enumerate(urls, 1):
                if self.verbose:
                    print(f"\n🔐 Validating URL {idx}/{len(urls)}: {url}")
                
                validated_url = validate_url(url, verbose=self.verbose)
                
                if validated_url:
                    if self.verbose:
                        print(f"   ✅ URL validated successfully!")
                        print(f"   ✓ Contains foundation/grant content")
                        print(f"   ✓ HTTP request successful")
                    state["url"] = validated_url
                    return state
                else:
                    if self.verbose:
                        print(f"   ❌ URL validation failed")
                        print(f"   ✗ Either no foundation/grant content or request failed")
        
        # No valid URL found
        if state["attempts"] >= state["max_attempts"]:
            if self.verbose:
                print(f"\n⚠️  Maximum attempts ({state['max_attempts']}) reached")
                print(f"   No valid URL found")
            state["error"] = "Could not find a valid URL after maximum attempts"
        elif self.verbose:
            print(f"\n🔄 No valid URL found, will retry with different search query")
        
        return state
    
    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue searching or end"""
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"🎯 DECISION NODE")
            print(f"{'='*60}")
        
        # End if URL found
        if state.get("url"):
            if self.verbose:
                print(f"\n✅ Decision: END - Valid URL found!")
                print(f"   URL: {state['url']}")
            return "end"
        
        # End if error or max attempts reached
        if state.get("error") or state["attempts"] >= state["max_attempts"]:
            if self.verbose:
                print(f"\n🛑 Decision: END - Stopping")
                if state.get("error"):
                    print(f"   Reason: Error occurred - {state['error']}")
                else:
                    print(f"   Reason: Maximum attempts reached ({state['attempts']}/{state['max_attempts']})")
            return "end"
        
        # Continue searching
        if self.verbose:
            print(f"\n🔄 Decision: CONTINUE - Trying different search strategy")
            print(f"   Current attempts: {state['attempts']}/{state['max_attempts']}")
        return "continue"
    
    def find_url(
        self, 
        organization_name: str, 
        foundation_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Find the official URL for an organization.
        
        Args:
            organization_name: Name of the organization
            foundation_data: Optional dictionary with foundation details
            
        Returns:
            Dictionary with url, success, attempts, and error (if any)
        """
        
        if self.verbose:
            print(f"\n{'#'*60}")
            print(f"🚀 Starting URL Finder Agent")
            print(f"{'#'*60}")
            print(f"\n🏢 Organization: {organization_name}")
            if foundation_data:
                print(f"📊 Additional Data: {list(foundation_data.keys())}")
        
        # Initialize state
        initial_state = {
            "organization_name": organization_name,
            "foundation_data": foundation_data,
            "messages": [],
            "url": None,
            "attempts": 0,
            "max_attempts": self.max_attempts,
            "error": None
        }
        
        try:
            # Run the graph
            if self.verbose:
                print(f"\n▶️  Executing LangGraph workflow...")
            
            final_state = self.graph.invoke(initial_state)
            
            if self.verbose:
                print(f"\n{'#'*60}")
                print(f"🏁 Agent Execution Complete")
                print(f"{'#'*60}")
            
            # Return results
            return {
                "success": final_state.get("url") is not None,
                "url": final_state.get("url"),
                "attempts": final_state.get("attempts", 0),
                "error": final_state.get("error")
            }
            
        except Exception as e:
            if self.verbose:
                print(f"\n❌ Agent execution failed: {str(e)}")
            return {
                "success": False,
                "url": None,
                "attempts": initial_state["attempts"],
                "error": f"Agent error: {str(e)}"
            }


# Service function for API integration
def find_organization_url(
    organization_name: str,
    foundation_data: Optional[Dict[str, Any]] = None,
    model: str = "gpt-4o-mini",
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Service function to find organization URL.
    Can be called from API endpoints.
    
    Args:
        organization_name: Name of the organization
        foundation_data: Optional foundation details
        model: LLM model to use
        verbose: Show agent's thinking process
        
    Returns:
        Dictionary with URL finding results
    """
    agent = OrganisationURLFinderAgent(model=model, verbose=verbose)
    return agent.find_url(organization_name, foundation_data)


# Main function for standalone testing
def main():
    """Main function for testing the agent"""
    
    print("🔍 Organization URL Finder Agent")
    print("=" * 50)
    
    # Test case 1: Simple organization name
    foundation_name = "BRANFORD HILLS HEALTH CARE MEMORIAL TRUST"
    print(f"\n📌 Test: {foundation_name}")
    result = find_organization_url(foundation_name, verbose=True)
    print(f"✅ Success: {result['success']}")
    print(f"🌐 URL: {result['url']}")
    print(f"🔄 Attempts: {result['attempts']}")
    if result['error']:
        print(f"❌ Error: {result['error']}")
    
    print("\n" + "=" * 50)
    print("✨ Testing complete!")


if __name__ == "__main__":
    main()



