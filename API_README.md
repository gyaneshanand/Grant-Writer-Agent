# Grant Writer Agent API

A comprehensive FastAPI-based REST API for grant data collection, processing, and content generation using AI.

## Overview

This API provides a complete pipeline for processing grant information from foundation websites, including:

1. **Grant Data Collection** - Extract individual grants from foundation websites
2. **Organization Data Collection** - Analyze foundation background and priorities  
3. **Grant Description Generation** - Create consolidated descriptions using OpenAI
4. **Metadata Generation** - Extract structured fields (deadlines, amounts, etc.)

## Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation & Setup

1. **Clone and navigate to the project:**
   ```bash
   cd Grant-Writer-Agent
   ```

2. **Set up environment:**
   ```bash
   # Set your OpenAI API key
   export OPENAI_API_KEY="your_openai_api_key_here"
   ```

3. **Start the API:**
   ```bash
   ./start_api.sh
   ```

The API will be available at:
- **Server**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Endpoints

### Data Collection

#### `POST /api/v1/data-collection/grants`
Collect grant data from foundation URLs.

**Request:**
```json
{
  "foundation_urls": [
    "https://example-foundation.org/grants"
  ],
  "max_grants": 10
}
```

**Response:**
```json
[
  {
    "title": "Education Grant Program",
    "description": "Supporting educational initiatives...",
    "amount": "$50,000",
    "deadline": "2024-03-15",
    "eligibility": "Non-profit organizations",
    "source_url": "https://example-foundation.org/grant-1"
  }
]
```

#### `POST /api/v1/data-collection/organization`
Collect organization data from foundation website.

**Request:**
```json
{
  "foundation_url": "https://example-foundation.org"
}
```

**Response:**
```json
{
  "organization_name": "Example Foundation",
  "mission_statement": "Advancing education and community development",
  "core_values": ["Education", "Innovation", "Community"],
  "funding_priorities": ["K-12 Education", "STEM Programs"],
  "geographic_focus": ["United States"],
  "target_demographics": ["Students", "Educators"],
  "source_url": "https://example-foundation.org"
}
```

### Content Generation

#### `POST /api/v1/content-generation/grant-description`
Generate consolidated grant description from multiple grants.

**Request:**
```json
{
  "grants_data": [
    {
      "title": "Education Grant",
      "description": "Supporting schools...",
      "amount": "$50,000"
    }
  ],
  "org_data": {
    "organization_name": "Example Foundation",
    "mission_statement": "Advancing education"
  }
}
```

**Response:**
```json
{
  "consolidated_description": "A comprehensive grant program focused on educational advancement..."
}
```

#### `POST /api/v1/content-generation/metadata`
Generate metadata fields from consolidated description.

**Request:**
```json
{
  "consolidated_description": "A comprehensive grant program..."
}
```

**Response:**
```json
{
  "deadline": "March 15, 2024",
  "amount": "Up to $50,000",
  "eligibility": "501(c)(3) organizations",
  "application_process": "Submit via online portal",
  "required_documents": "Budget, narrative, references",
  "contact_information": "grants@foundation.org"
}
```

### Full Pipeline

#### `POST /api/v1/pipeline/complete`
Run the complete 4-step grant processing pipeline.

**Request:**
```json
{
  "foundation_urls": [
    "https://example-foundation.org/grants"
  ],
  "max_grants": 10,
  "include_org_data": true
}
```

**Response:**
```json
{
  "grants_data": [...],
  "organization_data": {...},
  "consolidated_description": "...",
  "metadata": {
    "deadline": "March 15, 2024",
    "amount": "Up to $50,000",
    "eligibility": "501(c)(3) organizations",
    "application_process": "Submit via online portal",
    "required_documents": "Budget, narrative, references",
    "contact_information": "grants@foundation.org"
  }
}
```

## Project Structure

```
Grant-Writer-Agent/
├── main.py                     # FastAPI application entry point
├── start_api.sh               # Startup script
├── api_requirements.txt       # API dependencies
├── api/                       # API package
│   ├── __init__.py
│   ├── config/
│   │   └── settings.py        # Configuration settings
│   ├── models/
│   │   └── schemas.py         # Pydantic models
│   ├── services/              # Business logic layer
│   │   ├── grant_data_service.py
│   │   ├── organization_data_service.py
│   │   ├── grant_writer_service.py
│   │   └── metadata_writer_service.py
│   ├── controllers/           # API endpoint handlers
│   │   ├── data_collection_controller.py
│   │   ├── content_generation_controller.py
│   │   └── pipeline_controller.py
│   └── utils/
│       └── module_loader.py   # Dynamic module loading
├── grant-data-collector.py    # Original grant collection script
├── organisation-data-collector.py  # Original org collection script
├── grant-writer.py           # Original grant writing script
└── grant-metadata-writer.py  # Original metadata writing script
```

## Architecture

The API follows a clean architecture pattern with clear separation of concerns:

- **Controllers**: Handle HTTP requests/responses and validation
- **Services**: Contain business logic and coordinate between components
- **Models**: Define data structures using Pydantic
- **Utils**: Provide shared utilities and helpers
- **Config**: Manage application settings and environment variables

## Integration with Existing Scripts

The API integrates seamlessly with the existing Python scripts:

- Uses dynamic module loading to import existing functions
- Maintains compatibility with original script interfaces
- Adds API layer without modifying core logic
- Provides both individual component APIs and full pipeline access

## Environment Variables

- `OPENAI_API_KEY`: Required for AI-powered content generation

## Error Handling

The API includes comprehensive error handling:

- Input validation using Pydantic models
- Service-level error catching and re-raising
- HTTP status codes and descriptive error messages
- Logging for debugging and monitoring

## Development

### Running in Development Mode

The API runs with auto-reload enabled by default for development:

```bash
./start_api.sh
```

### Testing

Access the interactive API documentation at http://localhost:8000/docs to test endpoints directly in your browser.

## Production Deployment

For production deployment, consider:

1. Using environment-specific configuration
2. Adding authentication/authorization
3. Implementing rate limiting
4. Adding monitoring and logging
5. Using a production WSGI server like Gunicorn

## API Features

- **Interactive Documentation**: Automatic OpenAPI/Swagger documentation
- **Request/Response Validation**: Pydantic-based data validation
- **Error Handling**: Comprehensive error responses
- **CORS Support**: Cross-origin resource sharing enabled
- **Modular Design**: Clean separation of concerns
- **Health Checks**: Built-in health monitoring endpoints

## Support

The API provides detailed error messages and comprehensive documentation. Check the interactive docs at `/docs` for complete API specifications and examples.