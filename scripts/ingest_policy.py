#!/usr/bin/env python3
"""
Script to ingest a policy PDF into Neo4j
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.graph.ingestion import PolicyIngestionPipeline
from src.graph.schema import PolicyGraphSchema
from src.config.settings import settings


def main():
    parser = argparse.ArgumentParser(description="Ingest insurance policy PDF into Neo4j")
    parser.add_argument("--file", required=True, help="Path to policy PDF file")
    parser.add_argument("--product-code", required=True, help="Product code (e.g., LIG_HOME_FIRE_2025)")
    parser.add_argument("--product-name", required=True, help="Product name")
    parser.add_argument("--version-id", required=True, help="Version ID (e.g., LIG_HOME_FIRE_2025_V1)")
    parser.add_argument("--init-schema", action="store_true", help="Initialize schema before ingestion")
    parser.add_argument("--semantic-chunking", action="store_true", default=True, help="Use semantic chunking")
    
    args = parser.parse_args()
    
    pdf_path = Path(args.file)
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Initialize schema if requested
    if args.init_schema:
        logger.info("Initializing Neo4j schema...")
        schema = PolicyGraphSchema(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password
        )
        schema.initialize_schema(
            vector_dimensions=settings.vector_dimensions,
            similarity_function=settings.similarity_function
        )
        schema.close()
        logger.info("✅ Schema initialized")
    
    # Run ingestion
    pipeline = PolicyIngestionPipeline()
    
    try:
        stats = pipeline.ingest_policy(
            pdf_path=str(pdf_path),
            product_code=args.product_code,
            product_name=args.product_name,
            version_id=args.version_id,
            use_semantic_chunking=args.semantic_chunking
        )
        
        logger.info("=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Product: {args.product_name} ({args.product_code})")
        logger.info(f"Version: {args.version_id}")
        logger.info(f"Pages processed: {stats['pages']}")
        logger.info(f"Clauses extracted: {stats['clauses']}")
        logger.info(f"Chunks created: {stats['chunks']}")
        logger.info(f"Embeddings generated: {stats['embeddings_created']}")
        logger.info(f"Nodes created: {stats['nodes_created']}")
        logger.info(f"Relationships created: {stats['relationships_created']}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)
    
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()

