"""
FastAPI application for PolicyGraph QA system
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from loguru import logger

from src.rag.qa_engine import PolicyQAEngine
from src.config.settings import settings

# Initialize FastAPI app
app = FastAPI(
    title="PolicyGraph QA API",
    description="Insurance Policy GraphRAG QA System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize QA engine
qa_engine = None


# Request/Response models
class QueryRequest(BaseModel):
    question: str
    policy_version: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "화재로 인한 손해를 보상받을 수 있나요?",
                "policy_version": "LIG_HOME_FIRE_2025_V1"
            }
        }


class Citation(BaseModel):
    clause_id: str
    title: str
    text: Optional[str] = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    intent: str
    confidence: float
    citations: List[Dict[str, Any]]
    retrieved_chunks_count: int


class BatchQueryRequest(BaseModel):
    questions: List[str]
    policy_version: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    engine_status: str


# API endpoints
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    global qa_engine
    try:
        qa_engine = PolicyQAEngine()
        logger.info("✅ QA Engine initialized")
    except Exception as e:
        logger.error(f"Failed to initialize QA engine: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    global qa_engine
    if qa_engine:
        qa_engine.close()
        logger.info("QA Engine closed")


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "engine_status": "ready" if qa_engine else "not initialized"
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "engine_status": "ready" if qa_engine else "not initialized"
    }


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Answer a policy question
    
    - **question**: The policy question to answer
    - **policy_version**: Optional policy version filter
    """
    if not qa_engine:
        raise HTTPException(status_code=503, detail="QA engine not initialized")
    
    try:
        result = qa_engine.query(request.question)
        
        return QueryResponse(
            question=result["question"],
            answer=result["answer"],
            intent=result["intent"],
            confidence=result["confidence"],
            citations=result["citations"],
            retrieved_chunks_count=result["retrieved_chunks_count"]
        )
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/batch_query")
async def batch_query(request: BatchQueryRequest):
    """
    Answer multiple policy questions
    
    - **questions**: List of questions to answer
    - **policy_version**: Optional policy version filter
    """
    if not qa_engine:
        raise HTTPException(status_code=503, detail="QA engine not initialized")
    
    try:
        results = qa_engine.batch_query(request.questions)
        return {"results": results}
    
    except Exception as e:
        logger.error(f"Error processing batch query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )

