#!/usr/bin/env python3
"""
Initialize Neo4j schema and create sample data
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.graph.schema import PolicyGraphSchema
from src.config.settings import settings


def main():
    logger.info("Initializing Neo4j schema...")
    
    schema = PolicyGraphSchema(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password
    )
    
    # Initialize schema
    schema.initialize_schema(
        vector_dimensions=settings.vector_dimensions,
        similarity_function=settings.similarity_function
    )
    
    # Optionally create sample data
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--with-sample-data":
        logger.info("Creating sample data...")
        schema.create_sample_data()
    
    # Verify
    result = schema.verify_schema()
    
    print("\n" + "=" * 60)
    print("SCHEMA INITIALIZATION COMPLETE")
    print("=" * 60)
    print(f"Constraints: {result['constraints_count']}")
    print(f"Indexes: {result['indexes_count']}")
    print("\nNode counts:")
    for label, count in result['node_counts'].items():
        print(f"  {label}: {count}")
    print("=" * 60)
    
    schema.close()


if __name__ == "__main__":
    main()

