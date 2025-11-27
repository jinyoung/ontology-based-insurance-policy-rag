#!/usr/bin/env python3
"""
PDF 약관 파일을 파싱하여 Neo4j에 Ingestion
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from neo4j import GraphDatabase
from openai import OpenAI

from src.config.settings import settings
from src.parsers.pdf_parser import PolicyPDFParser
from src.parsers.clause_extractor import ClauseExtractor
from src.chunking.semantic_chunker import SemanticChunker


def ingest_pdf(pdf_path: str,
               product_code: str,
               product_name: str,
               version_id: str,
               use_semantic_chunking: bool = True):
    """
    PDF 약관을 파싱하여 Neo4j에 로딩
    
    Args:
        pdf_path: PDF 파일 경로
        product_code: 상품 코드
        product_name: 상품명
        version_id: 버전 ID
        use_semantic_chunking: LLM 청킹 사용 여부
    """
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.error(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)
    
    logger.info("="*80)
    logger.info(f"🚀 PDF Ingestion 시작: {pdf_file.name}")
    logger.info("="*80)
    
    stats = {
        'pdf_file': pdf_file.name,
        'pages': 0,
        'clauses': 0,
        'chunks': 0,
        'embeddings': 0,
        'nodes_created': 0
    }
    
    # Step 1: Parse PDF
    logger.info("\n[Step 1] PDF 파싱 중...")
    with PolicyPDFParser(str(pdf_file)) as parser:
        full_text = parser.extract_full_text()
        metadata = parser.get_metadata()
        stats['pages'] = metadata['total_pages']
        
        logger.info(f"  ✅ {stats['pages']}페이지 추출 완료")
        logger.info(f"  총 {len(full_text):,}자")
    
    # Step 2: Extract clauses
    logger.info("\n[Step 2] 조항 추출 중...")
    extractor = ClauseExtractor()
    clauses = extractor.extract_clauses(full_text)
    
    # Extract items for each clause
    for clause in clauses:
        extractor.extract_items_from_clause(clause)
    
    stats['clauses'] = len(clauses)
    logger.info(f"  ✅ {stats['clauses']}개 조항 추출 완료")
    
    # Show sample
    logger.info(f"\n  샘플 조항:")
    for clause in clauses[:3]:
        logger.info(f"    - {clause.clause_id}: {clause.title} ({clause.clause_type or 'General'})")
    if len(clauses) > 3:
        logger.info(f"    ... 외 {len(clauses)-3}개")
    
    # Step 3: Semantic chunking
    all_chunks = []
    
    if use_semantic_chunking:
        logger.info("\n[Step 3] LLM 기반 시맨틱 청킹 중...")
        chunker = SemanticChunker()
        
        for i, clause in enumerate(clauses, 1):
            if len(clause.full_text) > 150:
                metadata = {
                    'clause_id': clause.clause_id,
                    'title': clause.title,
                    'clause_type': clause.clause_type
                }
                
                logger.info(f"  [{i}/{len(clauses)}] {clause.clause_id} 청킹 중... ({len(clause.full_text)}자)")
                
                try:
                    chunks = chunker.chunk_text(clause.full_text, metadata)
                    all_chunks.extend(chunks)
                    logger.info(f"       → {len(chunks)}개 청크 생성")
                except Exception as e:
                    logger.error(f"       ✗ 청킹 실패: {e}")
            else:
                logger.debug(f"  [{i}/{len(clauses)}] {clause.clause_id} - 텍스트가 짧아 건너뜀")
        
        stats['chunks'] = len(all_chunks)
        logger.info(f"\n  ✅ 총 {stats['chunks']}개 시맨틱 청크 생성")
    else:
        logger.info("\n[Step 3] 시맨틱 청킹 건너뜀 (--no-semantic-chunking)")
        stats['chunks'] = 0
    
    # Step 4: Generate embeddings
    chunks_with_embeddings = []
    
    if all_chunks:
        logger.info("\n[Step 4] 임베딩 생성 중...")
        openai_client = OpenAI(api_key=settings.openai_api_key)
        
        for i, chunk in enumerate(all_chunks, 1):
            try:
                logger.info(f"  [{i}/{len(all_chunks)}] 임베딩 생성 중...")
                
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
                logger.warning(f"  ✗ 임베딩 생성 실패: {e}")
                continue
        
        stats['embeddings'] = len(chunks_with_embeddings)
        logger.info(f"\n  ✅ {stats['embeddings']}개 임베딩 생성 완료")
    else:
        logger.info("\n[Step 4] 청크가 없어 임베딩 생성 건너뜀")
    
    # Step 5: Load into Neo4j
    logger.info("\n[Step 5] Neo4j에 로딩 중...")
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password)
    )
    
    with driver.session() as session:
        # Create product
        logger.info(f"  상품 생성: {product_name} ({product_code})")
        session.run("""
            MERGE (prod:InsuranceProduct {code: $code})
            SET prod.name = $name,
                prod.kind = 'property',
                prod.lineOfBusiness = 'personal'
            """,
            code=product_code,
            name=product_name
        )
        
        # Create version
        logger.info(f"  버전 생성: {version_id}")
        session.run("""
            MATCH (prod:InsuranceProduct {code: $product_code})
            MERGE (ver:PolicyVersion {versionId: $version_id})
            SET ver.effectiveFrom = date(),
                ver.documentUrl = $pdf_path
            MERGE (prod)-[:HAS_POLICY_VERSION]->(ver)
            """,
            product_code=product_code,
            version_id=version_id,
            pdf_path=str(pdf_file)
        )
        
        # Create clauses
        logger.info(f"  조항 로딩: {len(clauses)}개")
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
            
            # Create special clause link
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
        
        logger.info(f"  ✅ 조항 로딩 완료")
        
        # Create chunks
        if chunks_with_embeddings:
            logger.info(f"  청크 로딩: {len(chunks_with_embeddings)}개")
            
            for i, chunk_data in enumerate(chunks_with_embeddings, 1):
                parent_clause_id = chunk_data['metadata'].get('clause_id')
                
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
                            chunk_id=chunk_data['chunk_id'],
                            text=chunk_data['text'],
                            semantic_type=chunk_data['semantic_type'],
                            embedding=chunk_data['embedding']
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
                        
                    except Exception as e:
                        logger.warning(f"  ✗ 청크 {i} 로딩 실패: {e}")
            
            logger.info(f"  ✅ 청크 로딩 완료")
        
        # Verify
        result = session.run("""
            MATCH (ver:PolicyVersion {versionId: $version_id})
            OPTIONAL MATCH (ver)-[:HAS_CLAUSE]->(c:PolicyClause)
            OPTIONAL MATCH (c)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
            RETURN count(DISTINCT c) as clauses, count(DISTINCT p) as chunks
            """,
            version_id=version_id
        )
        
        record = result.single()
        stats['nodes_created'] = record['clauses'] + record['chunks']
    
    driver.close()
    
    # Final summary
    logger.info("\n" + "="*80)
    logger.info("✅ Ingestion 완료!")
    logger.info("="*80)
    logger.info(f"PDF 파일: {stats['pdf_file']}")
    logger.info(f"페이지: {stats['pages']}개")
    logger.info(f"조항: {stats['clauses']}개")
    logger.info(f"청크: {stats['chunks']}개")
    logger.info(f"임베딩: {stats['embeddings']}개")
    logger.info(f"노드 생성: {stats['nodes_created']}개")
    logger.info("="*80)
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="보험약관 PDF를 파싱하여 Neo4j에 Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/ingest_pdf.py \\
    --pdf data/raw/LIG_주택화재보험.pdf \\
    --product-code LIG_HOME_FIRE_2025 \\
    --product-name "LIG 주택화재보험" \\
    --version-id LIG_HOME_FIRE_2025_V1
        """
    )
    
    parser.add_argument(
        '--pdf',
        required=True,
        help='PDF 파일 경로'
    )
    parser.add_argument(
        '--product-code',
        required=True,
        help='상품 코드 (예: LIG_HOME_FIRE_2025)'
    )
    parser.add_argument(
        '--product-name',
        required=True,
        help='상품명 (예: "LIG 주택화재보험")'
    )
    parser.add_argument(
        '--version-id',
        required=True,
        help='버전 ID (예: LIG_HOME_FIRE_2025_V1)'
    )
    parser.add_argument(
        '--no-semantic-chunking',
        action='store_true',
        help='LLM 시맨틱 청킹 비활성화 (빠른 테스트용)'
    )
    
    args = parser.parse_args()
    
    try:
        stats = ingest_pdf(
            pdf_path=args.pdf,
            product_code=args.product_code,
            product_name=args.product_name,
            version_id=args.version_id,
            use_semantic_chunking=not args.no_semantic_chunking
        )
        
        logger.info("\n💡 다음 단계:")
        logger.info(f"  python3 test_api_client.py")
        logger.info(f"  curl -X POST http://localhost:8001/api/v1/query \\")
        logger.info(f"    -H 'Content-Type: application/json' \\")
        logger.info(f"    -d '{{\"question\": \"보상하는 손해는 무엇인가요?\"}}'")
        
    except Exception as e:
        logger.error(f"\n❌ Ingestion 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

