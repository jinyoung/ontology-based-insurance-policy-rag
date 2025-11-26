"""
Configuration settings for PolicyGraph QA system
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # API Keys
    openai_api_key: str
    anthropic_api_key: Optional[str] = None
    
    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str
    
    # Model Configuration
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Vector Index Settings
    vector_dimensions: int = 1536
    similarity_function: str = "cosine"
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # RAG Settings
    retrieval_top_k: int = 10
    graph_depth: int = 2
    hybrid_alpha: float = 0.5  # Weight for semantic vs graph score
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

