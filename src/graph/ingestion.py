"""
Policy Ingestion Pipeline
Orchestrates the full pipeline from PDF to Neo4j graph
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
from neo4j import GraphDatabase
from loguru import logger
from openai import OpenAI

from src.config.settings import settings
from src.parsers.pdf_parser import PolicyPDFParser
from src.parsers.clause_extractor import ClauseExtractor, extract_clauses_from_text
from src.chunking.rule_chunker import RuleBasedChunker
from src.chunking.semantic_chunker import SemanticChunker


class PolicyIngestionPipeline:
    """
    Complete pipeline for ingesting insurance policy documents into Neo4j
    """
    
    def __init__(self, 
                 neo4j_uri: str = None,
                 neo4j_username: str = None,
                 neo4j_password: str = None):
        """Initialize the ingestion pipeline"""
        self.neo4j_uri = neo4j_uri or settings.neo4j_uri
        self.neo4j_username = neo4j_username or settings.neo4j_username
        self.neo4j_password = neo4j_password or settings.neo4j_password
        
        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_username, self.neo4j_password)
        )
        
        self.clause_extractor = ClauseExtractor()
        self.rule_chunker = RuleBasedChunker(max_chunk_size=settings.chunk_size)
        self.semantic_chunker = SemanticChunker(model=settings.llm_model)
        
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
        logger.info("✅ PolicyIngestionPipeline initialized")
    
    def ingest_policy(self,
                     pdf_path: str,
                     product_code: str,
                     product_name: str,
                     version_id: str,
                     use_semantic_chunking: bool = True) -> Dict[str, Any]:
        """
        Complete ingestion pipeline
        
        Args:
            pdf_path: Path to policy PDF
            product_code: Insurance product code
            product_name: Insurance product name
            version_id: Policy version ID
            use_semantic_chunking: Whether to use LLM-based semantic chunking
            
        Returns:
            Dictionary with ingestion statistics
        """
        logger.info(f"🚀 Starting ingestion for {product_name} ({version_id})")
        
        stats = {
            'product_code': product_code,
            'version_id': version_id,
            'pages': 0,
            'clauses': 0,
            'chunks': 0,
            'embeddings_created': 0,
            'nodes_created': 0,
            'relationships_created': 0
        }
        
        try:
            # Step 1: Parse PDF
            logger.info("📄 Step 1: Parsing PDF...")
            with PolicyPDFParser(pdf_path) as parser:
                text = parser.extract_full_text()
                metadata = parser.get_metadata()
                stats['pages'] = metadata['total_pages']
            
            # Step 2: Extract clauses
            logger.info("📋 Step 2: Extracting clauses...")
            clauses = self.clause_extractor.extract_clauses(text)
            # Extract items for each clause
            for clause in clauses:
                self.clause_extractor.extract_items_from_clause(clause)
            stats['clauses'] = len(clauses)
            
            # Step 3: Create chunks
            logger.info("✂️  Step 3: Creating chunks...")
            rule_chunks = self.rule_chunker.chunk_clauses(clauses)
            
            if use_semantic_chunking:
                # Apply semantic chunking to large chunks
                chunks_to_refine = []
                for chunk in rule_chunks:
                    if len(chunk.content) > 800:
                        chunks_to_refine.append({
                            'content': chunk.content,
                            'metadata': chunk.metadata
                        })
                
                if chunks_to_refine:
                    semantic_chunks = self.semantic_chunker.chunk_multiple_texts(chunks_to_refine)
                    # Use semantic chunks
                    chunks = semantic_chunks
                else:
                    chunks = rule_chunks
            else:
                chunks = rule_chunks
            
            stats['chunks'] = len(chunks)
            
            # Step 4: Generate embeddings
            logger.info("🔢 Step 4: Generating embeddings...")
            chunks_with_embeddings = self._generate_embeddings(chunks)
            stats['embeddings_created'] = len(chunks_with_embeddings)
            
            # Step 5: Create graph in Neo4j
            logger.info("🔗 Step 5: Creating graph in Neo4j...")
            graph_stats = self._create_graph(
                product_code=product_code,
                product_name=product_name,
                version_id=version_id,
                clauses=clauses,
                chunks=chunks_with_embeddings,
                pdf_path=pdf_path
            )
            stats.update(graph_stats)
            
            logger.info(f"✅ Ingestion complete! Stats: {stats}")
            return stats
        
        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}")
            raise
    
    def _generate_embeddings(self, chunks: List[Any]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for all chunks
        
        Args:
            chunks: List of chunk objects (RuleChunk or SemanticChunk)
            
        Returns:
            List of chunk dictionaries with embeddings
        """
        from tqdm import tqdm
        
        chunks_with_embeddings = []
        
        # Batch process embeddings
        batch_size = 100
        texts = [chunk.content if hasattr(chunk, 'content') else str(chunk) for chunk in chunks]
        
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
            batch_texts = texts[i:i + batch_size]
            
            try:
                # Call OpenAI embeddings API
                response = self.openai_client.embeddings.create(
                    model=settings.embedding_model,
                    input=batch_texts
                )
                
                # Extract embeddings
                for j, embedding_obj in enumerate(response.data):
                    chunk_idx = i + j
                    chunk = chunks[chunk_idx]
                    
                    chunk_dict = {
                        'chunk_id': chunk.chunk_id,
                        'text': chunk.content if hasattr(chunk, 'content') else str(chunk),
                        'embedding': embedding_obj.embedding,
                        'metadata': {}
                    }
                    
                    # Add metadata based on chunk type
                    if hasattr(chunk, 'semantic_type'):
                        # SemanticChunk
                        chunk_dict['metadata'] = {
                            'semantic_type': chunk.semantic_type,
                            'parent_chunk_id': chunk.parent_chunk_id,
                            **chunk.metadata
                        }
                    elif hasattr(chunk, 'chunk_type'):
                        # RuleChunk
                        chunk_dict['metadata'] = {
                            'chunk_type': chunk.chunk_type,
                            'clause_id': chunk.clause_id,
                            **chunk.metadata
                        }
                    else:
                        chunk_dict['metadata'] = {'type': 'unknown'}
                    
                    chunks_with_embeddings.append(chunk_dict)
            
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i}: {e}")
                continue
        
        logger.info(f"✅ Generated {len(chunks_with_embeddings)} embeddings")
        return chunks_with_embeddings
    
    def _create_graph(self,
                     product_code: str,
                     product_name: str,
                     version_id: str,
                     clauses: List[Any],
                     chunks: List[Dict[str, Any]],
                     pdf_path: str) -> Dict[str, int]:
        """
        Create the graph structure in Neo4j
        
        Returns:
            Dictionary with node and relationship counts
        """
        nodes_created = 0
        relationships_created = 0
        
        with self.driver.session() as session:
            # Create Product node
            logger.info(f"Creating product node: {product_code}")
            session.run("""
                MERGE (prod:InsuranceProduct {code: $code})
                SET prod.name = $name,
                    prod.kind = 'property',
                    prod.lineOfBusiness = 'personal'
                """,
                code=product_code,
                name=product_name
            )
            nodes_created += 1
            
            # Create PolicyVersion node
            logger.info(f"Creating policy version: {version_id}")
            session.run("""
                MATCH (prod:InsuranceProduct {code: $product_code})
                MERGE (ver:PolicyVersion {versionId: $version_id})
                SET ver.documentUrl = $pdf_path,
                    ver.effectiveFrom = date()
                MERGE (prod)-[:HAS_POLICY_VERSION]->(ver)
                """,
                product_code=product_code,
                version_id=version_id,
                pdf_path=pdf_path
            )
            nodes_created += 1
            relationships_created += 1
            
            # Create PolicyClause nodes
            logger.info(f"Creating {len(clauses)} clause nodes...")
            for clause in clauses:
                session.run("""
                    MATCH (ver:PolicyVersion {versionId: $version_id})
                    MERGE (c:PolicyClause {clauseId: $clause_id})
                    SET c.title = $title,
                        c.clauseType = $clause_type,
                        c.text = $text,
                        c.sectionPath = $section_path,
                        c.articleNumber = $article_number
                    MERGE (ver)-[:HAS_CLAUSE]->(c)
                    """,
                    version_id=version_id,
                    clause_id=clause.clause_id,
                    title=clause.title,
                    clause_type=clause.clause_type or 'General',
                    text=clause.full_text,
                    section_path=clause.section_path,
                    article_number=clause.article_number
                )
                nodes_created += 1
                relationships_created += 1
                
                # Create SpecialClause if applicable
                if clause.parent_section:
                    session.run("""
                        MATCH (ver:PolicyVersion {versionId: $version_id})
                        MATCH (c:PolicyClause {clauseId: $clause_id})
                        MERGE (sc:SpecialClause {name: $special_clause_name})
                        MERGE (ver)-[:HAS_SPECIAL_CLAUSE]->(sc)
                        MERGE (sc)-[:HAS_CLAUSE]->(c)
                        """,
                        version_id=version_id,
                        clause_id=clause.clause_id,
                        special_clause_name=clause.parent_section
                    )
                    relationships_created += 2
            
            # Create chunk nodes (ParagraphChunk/SemanticChunk)
            logger.info(f"Creating {len(chunks)} chunk nodes with embeddings...")
            for chunk in chunks:
                parent_clause_id = chunk['metadata'].get('parent_chunk_id') or \
                                  chunk['metadata'].get('clause_id') or \
                                  chunk['metadata'].get('parent_clause_id')
                
                semantic_type = chunk['metadata'].get('semantic_type', 
                                                     chunk['metadata'].get('chunk_type', 'general'))
                
                # Only create if we have a valid parent clause
                if parent_clause_id:
                    try:
                        session.run("""
                            MATCH (c:PolicyClause {clauseId: $parent_clause_id})
                            CREATE (p:ParagraphChunk {
                                chunkId: $chunk_id,
                                text: $text,
                                semanticType: $semantic_type,
                                embedding: $embedding
                            })
                            CREATE (c)-[:HAS_PARAGRAPH]->(p)
                            """,
                            parent_clause_id=parent_clause_id,
                            chunk_id=chunk['chunk_id'],
                            text=chunk['text'],
                            semantic_type=semantic_type,
                            embedding=chunk['embedding']
                        )
                        nodes_created += 1
                        relationships_created += 1
                    except Exception as e:
                        logger.warning(f"Failed to create chunk {chunk['chunk_id']}: {e}")
                        continue
                
                # Create Coverage/Exclusion nodes based on semantic type
                if semantic_type == 'coverage':
                    session.run("""
                        MATCH (p:ParagraphChunk {chunkId: $chunk_id})
                        MERGE (cov:Coverage {
                            code: $code,
                            name: $name
                        })
                        MERGE (p)-[:DEFINES_COVERAGE]->(cov)
                        """,
                        chunk_id=chunk['chunk_id'],
                        code=f"COV_{chunk['chunk_id']}",
                        name=chunk['text'][:100]
                    )
                    nodes_created += 1
                    relationships_created += 1
                
                elif semantic_type == 'exclusion':
                    session.run("""
                        MATCH (p:ParagraphChunk {chunkId: $chunk_id})
                        MERGE (exc:Exclusion {
                            code: $code,
                            description: $description
                        })
                        MERGE (p)-[:HAS_EXCLUSION]->(exc)
                        """,
                        chunk_id=chunk['chunk_id'],
                        code=f"EXC_{chunk['chunk_id']}",
                        description=chunk['text'][:100]
                    )
                    nodes_created += 1
                    relationships_created += 1
        
        logger.info(f"✅ Created {nodes_created} nodes and {relationships_created} relationships")
        
        return {
            'nodes_created': nodes_created,
            'relationships_created': relationships_created
        }
    
    def close(self):
        """Close connections"""
        self.driver.close()
        logger.info("Pipeline connections closed")


if __name__ == "__main__":
    # Example usage
    pipeline = PolicyIngestionPipeline()
    
    # Ingest a policy
    # stats = pipeline.ingest_policy(
    #     pdf_path="data/raw/LIG_주택화재보험약관.pdf",
    #     product_code="LIG_HOME_FIRE_2025",
    #     product_name="LIG 주택화재보험",
    #     version_id="LIG_HOME_FIRE_2025_V1",
    #     use_semantic_chunking=True
    # )
    
    # print("Ingestion stats:", stats)
    
    pipeline.close()

