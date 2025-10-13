# Organization URL Finder Agent 🔍

A LangGraph-based AI agent that finds official website URLs for foundations and organizations using Tavily Search and intelligent validation.

## Features ✨

- **LangGraph Workflow**: Modern state-based agent architecture
- **Tavily Search**: Powerful web search API integration
- **Smart Validation**: Automatically validates URLs for foundation/grant content
- **Multi-Strategy Search**: Progressive search refinement with 3 different strategies
- **Dual Interface**: Standalone testing + API service integration

## Quick Start 🚀

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file with:

```bash
OPENAI_API_KEY=your-openai-api-key-here
TAVILY_API_KEY=your-tavily-api-key-here
```

Get your Tavily API key at: https://tavily.com

### 3. Standalone Testing

```bash
cd agents
python organisation_url_finder_agent.py
```

This will run test cases for:
- Bill & Melinda Gates Foundation
- Ford Foundation (with additional data)
- Knight Foundation

## Usage 📖

### As Standalone Function

```python
from agents.organisation_url_finder_agent import find_organization_url

# Simple usage
result = find_organization_url("Gates Foundation")
print(result)
# Output: {
#     "success": True,
#     "url": "https://www.gatesfoundation.org",
#     "attempts": 1,
#     "error": None
# }

# With additional foundation data
foundation_data = {
    "ein": "13-1684331",
    "city": "New York",
    "state": "NY"
}
result = find_organization_url("Ford Foundation", foundation_data)
```

### As Agent Class

```python
from agents.organisation_url_finder_agent import OrganisationURLFinderAgent

# Create agent instance
agent = OrganisationURLFinderAgent(
    model="gpt-4o-mini",
    temperature=0.1,
    max_attempts=3
)

# Find URL
result = agent.find_url(
    organization_name="Knight Foundation",
    foundation_data={"city": "Miami"}
)
```

### Via API Endpoint

```bash
curl -X POST "http://localhost:8000/api/v1/grant-data-collection/find-url" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "Gates Foundation",
    "foundation_data": {"city": "Seattle"},
    "model": "gpt-4o-mini"
  }'
```

Response:
```json
{
  "success": true,
  "url": "https://www.gatesfoundation.org",
  "attempts": 1,
  "error": null,
  "organization_name": "Gates Foundation"
}
```

## How It Works 🔧

### LangGraph Workflow

```
START
  ↓
search_node (Execute Tavily search)
  ↓
process_node (Extract & validate URLs)
  ↓
should_continue? (Decision node)
  ↓ (URL found or max attempts)
END
```

### Search Strategies

The agent uses progressive search refinement:

1. **Attempt 1**: `"[Foundation Name] foundation official website"`
2. **Attempt 2**: `"[Foundation Name] foundation .org"`
3. **Attempt 3**: `"[Foundation Name] grants foundation homepage"`

### URL Validation

The agent validates URLs by:
- Fetching the webpage content
- Checking for "foundation" or "grant" keywords
- Verifying successful HTTP response
- Excluding directory sites (guidestar, foundationcenter, etc.)

## Configuration ⚙️

### Agent Parameters

- `model`: OpenAI model (default: `"gpt-4o-mini"`)
- `temperature`: LLM temperature (default: `0.1`)
- `max_attempts`: Maximum search attempts (default: `3`)

### Tavily Search

- `max_results`: Results per search (default: `5`)
- `include_answer`: Include AI answer (default: `True`)

## API Integration 🌐

The agent is integrated into the Grant Writer API at:

```
POST /api/v1/grant-data-collection/find-url
```

**Request Body:**
```json
{
  "organization_name": "string (required)",
  "foundation_data": {
    "ein": "string",
    "city": "string",
    "state": "string"
  },
  "model": "gpt-4o-mini"
}
```

**Response:**
```json
{
  "success": true,
  "url": "https://example.org",
  "attempts": 1,
  "error": null,
  "organization_name": "Example Foundation"
}
```

## Error Handling 🚨

The agent handles:
- Network errors during URL validation
- Search API failures
- Invalid URLs
- Maximum attempt limits
- Missing API keys

All errors are captured in the response:
```python
{
    "success": False,
    "url": None,
    "attempts": 3,
    "error": "Could not find a valid URL after maximum attempts"
}
```

## LangSmith Tracing 📊

Enable LangSmith for debugging (optional):

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-key
LANGSMITH_PROJECT=grant-writer-agent
```

## Architecture 🏗️

### State Structure
```python
class AgentState(TypedDict):
    organization_name: str
    foundation_data: Optional[Dict]
    messages: List[Any]
    url: Optional[str]
    attempts: int
    max_attempts: int
    error: Optional[str]
```

### Tools
1. **tavily_search**: Web search via Tavily API
2. **validate_url**: URL content validation

### Nodes
1. **search_node**: Executes search queries
2. **process_node**: Extracts and validates URLs
3. **should_continue**: Decides next action

## Testing 🧪

Run the built-in test suite:

```bash
python agents/organisation_url_finder_agent.py
```

Test output:
```
🔍 Organization URL Finder Agent
==================================================

📌 Test 1: Bill & Melinda Gates Foundation
✅ Success: True
🌐 URL: https://www.gatesfoundation.org
🔄 Attempts: 1

📌 Test 2: Ford Foundation with additional data
✅ Success: True
🌐 URL: https://www.fordfoundation.org
🔄 Attempts: 1

📌 Test 3: Knight Foundation
✅ Success: True
🌐 URL: https://knightfoundation.org
🔄 Attempts: 1

==================================================
✨ Testing complete!
```

## Troubleshooting 🔧

### "No module named 'langgraph'"
```bash
pip install langgraph>=0.0.50
```

### "TAVILY_API_KEY not found"
Get your API key at https://tavily.com and add to `.env`

### "Agent taking too long"
Adjust `max_attempts` parameter:
```python
agent = OrganisationURLFinderAgent(max_attempts=2)
```

## License 📄

Part of the Grant Writer Agent project.

## Support 💬

For issues or questions, please check the main Grant Writer Agent documentation.


graph TD
    Start([START]) --> Search[Search Node<br/>Execute Tavily Search]
    Search --> Process[Process Node<br/>Validate URLs]
    Process --> Decision{Decision Point}
    Decision -->|Valid URL Found| End([END])
    Decision -->|Need Retry| Search
    Decision -->|Max Attempts| End
    
    style Start fill:#90EE90
    style End fill:#FFB6C1
    style Search fill:#87CEEB
    style Process fill:#DDA0DD
    style Decision fill:#F0E68C
