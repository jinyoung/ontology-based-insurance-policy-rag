"""
FastAPI application for PolicyGraph QA system
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from loguru import logger
import os
import uuid
from pathlib import Path
import asyncio

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

# Ingestion job tracking
ingestion_jobs: Dict[str, Dict[str, Any]] = {}

# Upload directory
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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


class IngestionRequest(BaseModel):
    product_code: str
    product_name: str
    version_id: str
    max_clauses: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_code": "LIG_PERSONAL_INJURY_2007",
                "product_name": "LIG 개인상해보험",
                "version_id": "LIG_PERSONAL_INJURY_2007_V11",
                "max_clauses": 50
            }
        }


class IngestionStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RecommendedQuery(BaseModel):
    question: str
    description: str
    expected_clauses: List[str]


class DetailedQueryRequest(BaseModel):
    question: str
    include_process: bool = True  # 탐색 과정 포함 여부


class DetailedQueryResponse(BaseModel):
    question: str
    answer: str
    intent: str
    confidence: float
    citations: List[Dict[str, Any]]
    process: Optional[Dict[str, Any]] = None  # 탐색 과정 상세 정보


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


@app.get("/api/v1/health", response_model=HealthResponse)
async def api_health():
    """API v1 health check endpoint"""
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


@app.post("/api/v1/query/detailed", response_model=DetailedQueryResponse)
async def query_detailed(request: DetailedQueryRequest):
    """
    Answer a policy question with detailed process information
    
    - **question**: The policy question to answer
    - **include_process**: Include retrieval and reasoning process
    """
    if not qa_engine:
        raise HTTPException(status_code=503, detail="QA engine not initialized")
    
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        
        from src.retrieval.hierarchical_retriever import HierarchicalRetriever
        retriever = HierarchicalRetriever(driver)
        
        # Get detailed retrieval result
        retrieval_result = retriever.retrieve(request.question, top_k=5)
        
        # Generate answer
        from openai import OpenAI
        openai_client = OpenAI(api_key=settings.openai_api_key)
        
        if retrieval_result['selected_article']:
            context = retrieval_result['context']
            
            response = openai_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 보험약관 전문가입니다."},
                    {"role": "user", "content": f"약관 내용:\n\n{context}\n\n질문: {request.question}\n\n답변:"}
                ],
                temperature=0.3
            )
            
            answer = response.choices[0].message.content
            
            # Build process information
            process = None
            if request.include_process:
                process = {
                    "candidates_count": retrieval_result['metadata']['candidates_count'],
                    "articles_evaluated": retrieval_result['metadata']['articles_count'],
                    "selected_article": {
                        "id": retrieval_result['selected_article']['articleId'],
                        "title": retrieval_result['selected_article']['title']
                    },
                    "references": retrieval_result['metadata'].get('references_count', 0),
                    "sources": retrieval_result['sources']
                }
            
            driver.close()
            
            return DetailedQueryResponse(
                question=request.question,
                answer=answer,
                intent="clause_detail",
                confidence=0.9,
                citations=[{
                    "clause_id": retrieval_result['selected_article']['articleId'],
                    "title": retrieval_result['selected_article']['title'],
                    "text": retrieval_result['selected_article']['text'][:200]
                }],
                process=process
            )
        else:
            driver.close()
            return DetailedQueryResponse(
                question=request.question,
                answer="관련 조항을 찾을 수 없습니다.",
                intent="unknown",
                confidence=0.0,
                citations=[],
                process={"error": "No articles found"}
            )
    
    except Exception as e:
        logger.error(f"Error processing detailed query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file for ingestion
    
    - **file**: PDF file to upload
    """
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        file_path = UPLOAD_DIR / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f"PDF uploaded: {filename}")
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "path": str(file_path),
            "size": len(content)
        }
    
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_ingestion(job_id: str, pdf_path: str, product_code: str, 
                       product_name: str, version_id: str, max_clauses: Optional[int]):
    """Background task for ingestion"""
    try:
        ingestion_jobs[job_id]["status"] = "processing"
        ingestion_jobs[job_id]["progress"] = {"stage": "starting", "percent": 0}
        
        # Import ingestion script
        import subprocess
        
        cmd = [
            "python3", "scripts/ingest_hierarchical.py",
            "--pdf", pdf_path,
            "--product-code", product_code,
            "--product-name", product_name,
            "--version-id", version_id
        ]
        
        if max_clauses:
            cmd.extend(["--max-clauses", str(max_clauses)])
        
        ingestion_jobs[job_id]["progress"] = {"stage": "processing", "percent": 50}
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            ingestion_jobs[job_id]["status"] = "completed"
            ingestion_jobs[job_id]["progress"] = {"stage": "completed", "percent": 100}
            logger.info(f"Ingestion job {job_id} completed")
        else:
            ingestion_jobs[job_id]["status"] = "failed"
            ingestion_jobs[job_id]["error"] = result.stderr
            logger.error(f"Ingestion job {job_id} failed: {result.stderr}")
    
    except Exception as e:
        ingestion_jobs[job_id]["status"] = "failed"
        ingestion_jobs[job_id]["error"] = str(e)
        logger.error(f"Ingestion job {job_id} error: {e}")


@app.post("/api/v1/ingestion/start", response_model=IngestionStatus)
async def start_ingestion(
    background_tasks: BackgroundTasks,
    file_id: str,
    request: IngestionRequest
):
    """
    Start ingestion process for uploaded PDF
    
    - **file_id**: ID of uploaded file
    - **product_code**: Product code
    - **product_name**: Product name
    - **version_id**: Version ID
    - **max_clauses**: Maximum clauses to process (optional)
    """
    try:
        # Find uploaded file
        pdf_files = list(UPLOAD_DIR.glob(f"{file_id}_*.pdf"))
        if not pdf_files:
            raise HTTPException(status_code=404, detail="Uploaded file not found")
        
        pdf_path = str(pdf_files[0])
        
        # Create job
        job_id = str(uuid.uuid4())
        ingestion_jobs[job_id] = {
            "status": "pending",
            "file_id": file_id,
            "pdf_path": pdf_path,
            "product_code": request.product_code,
            "progress": None,
            "error": None
        }
        
        # Start background task
        background_tasks.add_task(
            run_ingestion,
            job_id,
            pdf_path,
            request.product_code,
            request.product_name,
            request.version_id,
            request.max_clauses
        )
        
        logger.info(f"Ingestion job {job_id} started")
        
        return IngestionStatus(
            job_id=job_id,
            status="pending",
            progress=None,
            error=None
        )
    
    except Exception as e:
        logger.error(f"Error starting ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ingestion/status/{job_id}", response_model=IngestionStatus)
async def get_ingestion_status(job_id: str):
    """
    Get ingestion job status
    
    - **job_id**: Ingestion job ID
    """
    if job_id not in ingestion_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = ingestion_jobs[job_id]
    
    return IngestionStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        error=job.get("error")
    )


@app.get("/api/v1/recommended-queries")
async def get_recommended_queries():
    """
    Get recommended queries for current ingested policy
    
    Returns queries that require multi-clause traversal
    """
    # Generate recommended queries using LLM
    try:
        from neo4j import GraphDatabase
        from openai import OpenAI
        
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        
        # Get articles with REFERS_TO relationships
        with driver.session() as session:
            result = session.run("""
                MATCH (a:Article)-[:HAS_PARAGRAPH]->(p:Paragraph)-[r:REFERS_TO]->(ref)
                RETURN DISTINCT a.articleId as article_id, 
                       a.title as article_title,
                       labels(ref)[0] as ref_type,
                       CASE 
                         WHEN ref.articleId IS NOT NULL THEN ref.articleId
                         WHEN ref.paragraphId IS NOT NULL THEN ref.paragraphId
                         ELSE ref.itemId
                       END as ref_id
                LIMIT 10
            """)
            
            references = list(result)
        
        driver.close()
        
        if not references:
            return {"queries": []}
        
        # Generate queries using LLM
        openai_client = OpenAI(api_key=settings.openai_api_key)
        
        references_text = "\n".join([
            f"- {ref['article_id']} ({ref['article_title']}) → {ref['ref_id']}"
            for ref in references[:5]
        ])
        
        prompt = f"""다음은 보험약관에서 서로 참조하는 조항들입니다:

{references_text}

위 참조 관계를 활용하여, 답변하기 위해 여러 조항을 함께 읽어야 하는 질문 3개를 생성해주세요.

응답 형식 (JSON):
{{
  "queries": [
    {{
      "question": "질문 내용",
      "description": "이 질문이 왜 여러 조항을 필요로 하는지 간단한 설명",
      "expected_clauses": ["제X조", "제Y조"]
    }}
  ]
}}
"""
        
        response = openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "당신은 보험약관 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        
        return result
    
    except Exception as e:
        logger.error(f"Error generating recommended queries: {e}")
        # Return default queries
        return {
            "queries": [
                {
                    "question": "서면동의 없이 가입된 사망보험에서 보험료를 돌려받을 수 있나요?",
                    "description": "계약의 무효와 해지 조항을 함께 참조해야 합니다.",
                    "expected_clauses": ["제4조", "제6조"]
                },
                {
                    "question": "청약을 철회하려면 어떤 조건이 필요한가요?",
                    "description": "청약 철회와 관련 예외사항을 함께 확인해야 합니다.",
                    "expected_clauses": ["제2조"]
                }
            ]
        }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )

