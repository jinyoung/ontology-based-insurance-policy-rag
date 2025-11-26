#!/usr/bin/env python3
"""
Test ingestion with sample text (no PDF needed)
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from neo4j import GraphDatabase
from openai import OpenAI

from src.config.settings import settings
from src.parsers.clause_extractor import ClauseExtractor
from src.chunking.semantic_chunker import SemanticChunker

# Sample policy text
SAMPLE_POLICY_TEXT = """
【도난위험 특별약관】

제1조(보상하는 손해) 회사는 보험증권에 기재된 보험의 목적에 대하여 도난으로 인한 손해를 보상합니다.
① 도난으로 인한 직접적인 손해를 보상합니다.
② 도난물품의 회수에 소요된 비용을 보상합니다.

제2조(보상하지 아니하는 손해) 회사는 다음의 손해는 보상하지 아니합니다.
1. 계약자, 피보험자 또는 이들의 법정대리인의 고의 또는 중대한 과실로 생긴 손해
2. 전쟁, 혁명, 내란, 사변, 폭동, 소요 및 이와 유사한 사태로 생긴 손해
3. 지진, 분화 등 천재지변으로 생긴 손해

제3조(자기부담금) 회사가 보상할 손해액에서 증권에 기재된 자기부담금을 공제하고 보험금을 지급합니다.
"""

def main():
    print("\n" + "="*80)
    print("🚀 테스트 데이터 Ingestion 시작")
    print("="*80)
    
    # Step 1: Extract clauses
    print("\n[Step 1] 조항 추출...")
    extractor = ClauseExtractor()
    clauses = extractor.extract_clauses(SAMPLE_POLICY_TEXT)
    
    for clause in clauses:
        extractor.extract_items_from_clause(clause)
    
    print(f"✅ {len(clauses)}개 조항 추출 완료")
    
    # Step 2: Semantic chunking
    print("\n[Step 2] 시맨틱 청킹...")
    chunker = SemanticChunker()
    all_chunks = []
    
    for clause in clauses:
        if len(clause.full_text) > 150:
            metadata = {
                'clause_id': clause.clause_id,
                'title': clause.title,
                'clause_type': clause.clause_type
            }
            chunks = chunker.chunk_text(clause.full_text, metadata)
            all_chunks.extend(chunks)
            print(f"  {clause.clause_id}: {len(chunks)}개 청크")
        else:
            print(f"  {clause.clause_id}: 텍스트가 짧아 건너뜀")
    
    print(f"✅ 총 {len(all_chunks)}개 청크 생성")
    
    # Step 3: Generate embeddings
    print("\n[Step 3] 임베딩 생성...")
    openai_client = OpenAI(api_key=settings.openai_api_key)
    
    chunks_with_embeddings = []
    for chunk in all_chunks:
        try:
            response = openai_client.embeddings.create(
                model=settings.embedding_model,
                input=chunk.content
            )
            embedding = response.data[0].embedding
            
            chunks_with_embeddings.append({
                'chunk_id': chunk.chunk_id,
                'text': chunk.content,
                'embedding': embedding,
                'semantic_type': chunk.semantic_type,
                'metadata': chunk.metadata
            })
        except Exception as e:
            logger.warning(f"임베딩 생성 실패: {e}")
            continue
    
    print(f"✅ {len(chunks_with_embeddings)}개 임베딩 생성 완료")
    
    # Step 4: Load into Neo4j
    print("\n[Step 4] Neo4j에 로딩...")
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password)
    )
    
    with driver.session() as session:
        # Create product and version
        session.run("""
            MERGE (prod:InsuranceProduct {code: 'TEST_THEFT_2025'})
            SET prod.name = '테스트 도난보험',
                prod.kind = 'property'
            """)
        
        session.run("""
            MATCH (prod:InsuranceProduct {code: 'TEST_THEFT_2025'})
            MERGE (ver:PolicyVersion {versionId: 'TEST_THEFT_2025_V1'})
            SET ver.effectiveFrom = date()
            MERGE (prod)-[:HAS_POLICY_VERSION]->(ver)
            """)
        
        # Create clauses
        for clause in clauses:
            session.run("""
                MATCH (ver:PolicyVersion {versionId: 'TEST_THEFT_2025_V1'})
                MERGE (c:PolicyClause {clauseId: $clause_id})
                SET c.title = $title,
                    c.clauseType = $clause_type,
                    c.text = $text,
                    c.sectionPath = $section_path,
                    c.articleNumber = $article_number
                MERGE (ver)-[:HAS_CLAUSE]->(c)
                """,
                clause_id=clause.clause_id,
                title=clause.title,
                clause_type=clause.clause_type or 'General',
                text=clause.full_text,
                section_path=clause.section_path,
                article_number=clause.article_number
            )
            
            # Create special clause link
            if clause.parent_section:
                session.run("""
                    MATCH (ver:PolicyVersion {versionId: 'TEST_THEFT_2025_V1'})
                    MATCH (c:PolicyClause {clauseId: $clause_id})
                    MERGE (sc:SpecialClause {name: $special_clause_name})
                    MERGE (ver)-[:HAS_SPECIAL_CLAUSE]->(sc)
                    MERGE (sc)-[:HAS_CLAUSE]->(c)
                    """,
                    clause_id=clause.clause_id,
                    special_clause_name=clause.parent_section
                )
        
        print(f"  ✅ {len(clauses)}개 조항 로딩 완료")
        
        # Create chunks with embeddings
        for chunk_data in chunks_with_embeddings:
            parent_clause_id = chunk_data['metadata'].get('clause_id')
            
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
                chunk_id=chunk_data['chunk_id'],
                text=chunk_data['text'],
                semantic_type=chunk_data['semantic_type'],
                embedding=chunk_data['embedding']  # 임베딩 추가!
            )
            
            # Create Coverage/Exclusion nodes
            if chunk_data['semantic_type'] == 'coverage':
                session.run("""
                    MATCH (p:ParagraphChunk {chunkId: $chunk_id})
                    MERGE (cov:Coverage {
                        code: $code,
                        name: $name
                    })
                    MERGE (p)-[:DEFINES_COVERAGE]->(cov)
                    """,
                    chunk_id=chunk_data['chunk_id'],
                    code=f"COV_{chunk_data['chunk_id']}",
                    name=chunk_data['text'][:50]
                )
            elif chunk_data['semantic_type'] == 'exclusion':
                session.run("""
                    MATCH (p:ParagraphChunk {chunkId: $chunk_id})
                    MERGE (exc:Exclusion {
                        code: $code,
                        description: $description
                    })
                    MERGE (p)-[:HAS_EXCLUSION]->(exc)
                    """,
                    chunk_id=chunk_data['chunk_id'],
                    code=f"EXC_{chunk_data['chunk_id']}",
                    description=chunk_data['text'][:50]
                )
        
        print(f"  ✅ {len(chunks_with_embeddings)}개 청크 로딩 완료")
        
        # Verify
        result = session.run("""
            MATCH (ver:PolicyVersion {versionId: 'TEST_THEFT_2025_V1'})
            OPTIONAL MATCH (ver)-[:HAS_CLAUSE]->(c:PolicyClause)
            OPTIONAL MATCH (c)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
            RETURN count(DISTINCT c) as clauses, count(DISTINCT p) as chunks
            """)
        
        record = result.single()
        print(f"\n✅ 검증 완료:")
        print(f"   - 조항: {record['clauses']}개")
        print(f"   - 청크: {record['chunks']}개")
    
    driver.close()
    
    print("\n" + "="*80)
    print("✅ Ingestion 완료!")
    print("="*80)
    print("\n💡 다음: python3 scripts/test_qa_simple.py 로 QA 테스트")


if __name__ == "__main__":
    main()

