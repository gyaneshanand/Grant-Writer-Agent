from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

# Import controllers
from api.controllers.data_collection_controller import router as data_collection_router
from api.controllers.content_generation_controller import router as content_generation_router
from api.controllers.pipeline_controller import router as pipeline_router

# Import LangSmith setup
from api.config.langsmith_setup import setup_langsmith, log_langsmith_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Grant Writer API starting up...")
    
    # Initialize LangSmith tracing
    setup_langsmith()
    log_langsmith_status()
    
    # Check for required environment variables
    required_env_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.warning("Some features may not work without proper API keys")
    else:
        logger.info("All required environment variables are set")
    
    logger.info("Grant Writer API started successfully")
    yield
    logger.info("Grant Writer API shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Grant Writer Agent API",
    description="""
    A comprehensive API for grant data collection, processing, and content generation.
    
    ## Features
    
    * **Data Collection**: Extract grant information from foundation websites
    * **Organization Analysis**: Gather foundation mission, values, and priorities
    * **Content Generation**: Create consolidated grant descriptions using AI
    * **Metadata Extraction**: Generate structured metadata for grant details
    * **Full Pipeline**: End-to-end processing from URLs to final content
    
    ## Pipeline Overview
    
    1. **Grant Data Collection**: Extract individual grants from foundation websites
    2. **Organization Data Collection**: Analyze foundation background and priorities
    3. **Grant Description Generation**: Create consolidated descriptions using OpenAI
    4. **Metadata Generation**: Extract structured fields (deadlines, amounts, etc.)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(data_collection_router, prefix="/api/v1")
app.include_router(content_generation_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "message": "Grant Writer Agent API is running",
        "version": "1.0.0",
        "endpoints": {
            "data_collection": "/api/v1/data-collection",
            "content_generation": "/api/v1/content-generation", 
            "pipeline": "/api/v1/pipeline",
            "docs": "/docs"
        }
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api_version": "1.0.0",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "available_endpoints": [
            "/api/v1/data-collection/grants",
            "/api/v1/data-collection/organization",
            "/api/v1/content-generation/grant-description",
            "/api/v1/content-generation/metadata",
            "/api/v1/pipeline/complete"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )