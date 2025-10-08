# Grant Writer Agent API

A comprehensive AI-powered FastAPI application for automating grant discovery, analysis, and content generation. This system helps organizations find and apply for grants by collecting data from foundation websites, analyzing organizations, generating compelling grant content, and creating SEO-optimized metadata.

## 🌟 Features

### 4-Step Grant Processing Pipeline

1. **Grant Data Collection** - Extracts grant information from foundation URLs
2. **Organization Analysis** - Analyzes your organization's profile and mission
3. **Content Generation** - Creates compelling, tailored grant applications
4. **Metadata Generation** - Generates SEO-optimized metadata for grant opportunities

### Key Capabilities

- ✅ Automated web scraping and data extraction
- ✅ AI-powered content analysis using GPT-4o-mini
- ✅ Structured JSON output with comprehensive grant details
- ✅ RESTful API with 4 specialized endpoints
- ✅ LangSmith integration for monitoring and tracing
- ✅ Environment-based configuration (no hardcoded API keys!)
- ✅ Comprehensive error handling and logging

## 📋 Prerequisites

- Python 3.12+
- OpenAI API key
- (Optional) LangSmith API key for monitoring

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Grant-Writer-Agent.git
cd Grant-Writer-Agent
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# Required
OPENAI_API_KEY=your-openai-api-key-here

# Optional - LangSmith monitoring
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-api-key-here
LANGSMITH_PROJECT=grant-writer-agent
```

### 5. Run the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## 📚 API Endpoints

### 1. Grant Data Collection
**POST** `/api/collect/grant-data`

Extracts grant information from a foundation URL.

```json
{
  "grant_url": "https://foundation.org/grants"
}
```

### 2. Organization Data Collection
**POST** `/api/collect/organization-data`

Analyzes organization information from their website.

```json
{
  "organization_url": "https://yourorg.org"
}
```

### 3. Grant Content Generation
**POST** `/api/generate/grant-content`

Generates tailored grant application content.

```json
{
  "grant_data": {...},
  "organization_data": {...}
}
```

### 4. Metadata Generation
**POST** `/api/generate/metadata`

Creates SEO-optimized metadata for grant opportunities.

```json
{
  "grant_description": "Full grant description text..."
}
```

### 5. Complete Pipeline
**POST** `/api/pipeline/process`

Runs the complete 4-step pipeline in one call.

```json
{
  "grant_url": "https://foundation.org/grants",
  "organization_url": "https://yourorg.org"
}
```

## 🏗️ Project Structure

```
Grant-Writer-Agent/
├── agents/                          # Core agent modules
│   ├── grant_data_collector.py     # Web scraping & grant extraction
│   ├── organisation_data_collector.py  # Organization analysis
│   ├── grant_writer.py             # Content generation
│   └── grant_metadata_writer.py    # Metadata generation
├── api/                             # FastAPI application
│   ├── config/
│   │   ├── settings.py             # Configuration management
│   │   └── langsmith_setup.py      # LangSmith integration
│   ├── controllers/                 # API route handlers
│   │   ├── data_collection_controller.py
│   │   ├── content_generation_controller.py
│   │   └── pipeline_controller.py
│   ├── services/                    # Business logic layer
│   │   ├── grant_data_service.py
│   │   ├── organization_data_service.py
│   │   ├── grant_writer_service.py
│   │   └── metadata_writer_service.py
│   └── models/
│       └── schemas.py              # Pydantic models
├── logs/                            # Application logs
├── main.py                          # FastAPI application entry
├── requirements.txt                 # Python dependencies
├── .env.example                     # Example environment variables
├── .gitignore                       # Git ignore rules
└── README.md                        # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for GPT models |
| `LANGSMITH_TRACING` | No | `false` | Enable LangSmith tracing |
| `LANGSMITH_API_KEY` | No | - | LangSmith API key |
| `LANGSMITH_PROJECT` | No | `grant-writer-agent` | LangSmith project name |
| `APP_HOST` | No | `0.0.0.0` | API host address |
| `APP_PORT` | No | `8000` | API port |
| `APP_ENV` | No | `development` | Application environment |
| `APP_DEBUG` | No | `true` | Enable debug mode |
| `APP_RELOAD` | No | `true` | Enable auto-reload |

## 🧪 Usage Examples

### Example 1: Collect Grant Data

```python
import requests

response = requests.post(
    "http://localhost:8000/api/collect/grant-data",
    json={"grant_url": "https://foundation.org/grants"}
)

grant_data = response.json()
print(grant_data)
```

### Example 2: Run Complete Pipeline

```python
import requests

response = requests.post(
    "http://localhost:8000/api/pipeline/process",
    json={
        "grant_url": "https://foundation.org/grants",
        "organization_url": "https://yourorg.org"
    }
)

result = response.json()
print("Grant Data:", result["grant_data"])
print("Organization Data:", result["organization_data"])
print("Generated Content:", result["grant_content"])
print("Metadata:", result["metadata"])
```

## 📊 Grant Data Schema

    ```json
    ## 📊 Grant Data Schema

The system extracts comprehensive grant information in structured JSON format:

```json
{
  "grant_name": "Grant title",
  "funding_priorities": "Funding priorities and interests",
  "grant_type": "Type of grant",
  "eligibility_requirements": "Eligibility criteria",
  "geographic_focus": "Geographic focus areas",
  "funding_amount": "Funding amount range",
  "proposal_deadline": "Application deadline",
  "recurrence": "Grant recurrence (Annual, Rolling, etc.)",
  "contact_info": {
    "email": "Contact email",
    "phone": "Contact phone",
    "address": "Contact address"
  },
  "organization_info": "Organization background",
  "grant_summary": "Comprehensive grant summary",
  "grant_url": "Source URL"
}
```

## 🔍 Monitoring with LangSmith

The application includes built-in LangSmith integration for monitoring:

- Track all LLM calls and their performance
- Debug issues with detailed traces
- Monitor token usage and costs
- Analyze application performance

Enable by setting `LANGSMITH_TRACING=true` in your `.env` file.

## 🛡️ Security Best Practices

- ✅ Never commit `.env` files to git
- ✅ All API keys loaded from environment variables
- ✅ `.gitignore` configured to exclude sensitive files
- ✅ Use `.env.example` for documentation only
- ✅ Rotate API keys regularly

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🐛 Troubleshooting

### Issue: "OPENAI_API_KEY not found"
**Solution:** Ensure you've created a `.env` file with your OpenAI API key.

### Issue: LangChain deprecation warnings
**Solution:** The project uses `langchain-community` for chat models. Ensure all dependencies are installed: `pip install -r requirements.txt`

### Issue: Pydantic validation errors
**Solution:** Check that your `.env` file matches the structure in `.env.example`

### Issue: Import errors on startup
**Solution:** Make sure you're in the virtual environment and all dependencies are installed.

## 📧 Support

For issues, questions, or contributions, please open an issue on GitHub.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [LangChain](https://langchain.com/)
- AI models from [OpenAI](https://openai.com/)
- Monitoring by [LangSmith](https://smith.langchain.com/)

---

**Made with ❤️ for the grant writing community**
    ```

Step 5. Filtering Active Grants:

Detect “open”, “currently accepting applications”, or future deadlines.

Discard pages mentioning “closed”, “past deadline”, “archived”.

Step 6. Output:

Return structured JSON or write into a database (Postgres/Elastic).

Optionally push results to your grant catalog system.