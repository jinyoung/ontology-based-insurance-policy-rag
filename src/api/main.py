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
                # Combine sources (main article) with references for visualization
                all_sources = retrieval_result['sources'].copy()
                
                # Get references from hierarchical retriever context data
                from src.retrieval.hierarchical_retriever import HierarchicalRetriever
                context_data = retriever._build_context_with_references(
                    retrieval_result['selected_article']['articleId']
                )
                
                # Add references to sources for graph visualization
                for ref in context_data.get('references', []):
                    all_sources.append({
                        'type': ref['type'],
                        'id': ref['id'],
                        'title': ref.get('title', '')
                    })
                
                process = {
                    "candidates_count": retrieval_result['metadata']['candidates_count'],
                    "articles_evaluated": retrieval_result['metadata']['articles_count'],
                    "selected_article": {
                        "id": retrieval_result['selected_article']['articleId'],
                        "title": retrieval_result['selected_article']['title']
                    },
                    "references": len(context_data.get('references', [])),
                    "sources": all_sources
                }
            
            driver.close()
            
            # Build citations including main article and references
            citations = [{
                "clause_id": retrieval_result['selected_article']['articleId'],
                "title": retrieval_result['selected_article']['title'],
                "text": retrieval_result['selected_article']['text'][:200]
            }]
            
            # Add referenced clauses to citations
            for ref in context_data.get('references', []):
                # Get full text for the reference if available
                ref_text = ""
                with GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password)
                ) as temp_driver:
                    with temp_driver.session() as temp_session:
                        if ref['type'] == 'Article':
                            ref_result = temp_session.run("""
                                MATCH (a:Article {articleId: $ref_id})
                                RETURN a.text AS text
                            """, ref_id=ref['id'])
                            record = ref_result.single()
                            if record:
                                ref_text = record['text'][:200] if record['text'] else ""
                
                citations.append({
                    "clause_id": ref['id'],
                    "title": ref.get('title', ''),
                    "text": ref_text
                })
            
            return DetailedQueryResponse(
                question=request.question,
                answer=answer,
                intent="clause_detail",
                confidence=0.9,
                citations=citations,
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
                       product_name: str, version_id: str, max_clauses: Optional[int],
                       progress_file: str):
    """Background task for ingestion"""
    import json
    
    try:
        ingestion_jobs[job_id]["status"] = "processing"
        ingestion_jobs[job_id]["progress"] = {"stage": "PDF 파싱 준비 중...", "percent": 5, "detail": ""}
        
        # Get absolute paths
        project_root = Path(__file__).parent.parent.parent.resolve()
        script_path = project_root / "scripts" / "ingest_hierarchical.py"
        abs_pdf_path = Path(pdf_path).resolve()
        
        cmd = [
            "python3", str(script_path),
            "--pdf", str(abs_pdf_path),
            "--product-code", product_code,
            "--product-name", product_name,
            "--version-id", version_id,
            "--progress-file", progress_file
        ]
        
        if max_clauses:
            cmd.extend(["--max-clauses", str(max_clauses)])
        
        logger.info(f"Running ingestion: {' '.join(cmd)}")
        
        # Use asyncio subprocess for non-blocking execution
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root)
        )
        
        # Monitor progress file while process is running
        while process.returncode is None:
            try:
                if os.path.exists(progress_file):
                    with open(progress_file, 'r') as f:
                        progress_data = json.load(f)
                        ingestion_jobs[job_id]["progress"] = progress_data
            except Exception as e:
                logger.debug(f"Progress read error: {e}")
            await asyncio.sleep(0.5)
            
            # Check if process has completed
            try:
                await asyncio.wait_for(process.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
        
        # Get final result
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            ingestion_jobs[job_id]["status"] = "completed"
            ingestion_jobs[job_id]["progress"] = {"stage": "완료!", "percent": 100, "detail": "모든 작업이 성공적으로 완료되었습니다."}
            logger.info(f"Ingestion job {job_id} completed")
        else:
            ingestion_jobs[job_id]["status"] = "failed"
            error_msg = stderr.decode() if stderr else "Unknown error"
            ingestion_jobs[job_id]["error"] = error_msg
            logger.error(f"Ingestion job {job_id} failed: {error_msg}")
        
        # Cleanup progress file
        if os.path.exists(progress_file):
            os.remove(progress_file)
    
    except Exception as e:
        ingestion_jobs[job_id]["status"] = "failed"
        ingestion_jobs[job_id]["error"] = str(e)
        logger.error(f"Ingestion job {job_id} error: {e}")


@app.get("/api/v1/graph/check-existing")
async def check_existing_nodes():
    """
    Check if there are existing nodes in Neo4j
    """
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        
        with driver.session() as session:
            result = session.run("""
                MATCH (n)
                WITH labels(n) AS labels, count(*) AS count
                RETURN labels[0] AS label, count
                ORDER BY count DESC
            """)
            
            nodes = {}
            total = 0
            for record in result:
                label = record['label']
                count = record['count']
                nodes[label] = count
                total += count
        
        driver.close()
        
        return {
            "has_existing": total > 0,
            "total_nodes": total,
            "nodes_by_type": nodes
        }
    
    except Exception as e:
        logger.error(f"Error checking existing nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/graph/clear")
async def clear_graph():
    """
    Clear all nodes from Neo4j
    """
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        
        with driver.session() as session:
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")
        
        driver.close()
        logger.info("Graph cleared successfully")
        
        return {"status": "success", "message": "All nodes deleted"}
    
    except Exception as e:
        logger.error(f"Error clearing graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # Create progress file path
        progress_file = Path(f"/tmp/ingestion_progress_{job_id}.json")
        
        ingestion_jobs[job_id] = {
            "status": "pending",
            "file_id": file_id,
            "pdf_path": pdf_path,
            "product_code": request.product_code,
            "progress": {"stage": "초기화 중...", "percent": 0, "detail": ""},
            "progress_file": str(progress_file),
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
            request.max_clauses,
            str(progress_file)
        )
        
        logger.info(f"Ingestion job {job_id} started")
        
        return IngestionStatus(
            job_id=job_id,
            status="pending",
            progress={"stage": "초기화 중...", "percent": 0, "detail": ""},
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

