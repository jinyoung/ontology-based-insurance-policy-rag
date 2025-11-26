#!/usr/bin/env python3
"""
Simple QA test without full pipeline (for debugging)
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from neo4j import GraphDatabase
from src.config.settings import settings

def test_graph_queries():
    """Test basic graph queries"""
    print("\n" + "="*80)
    print("🔍 Neo4j 그래프 쿼리 테스트")
    print("="*80)
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password)
    )
    
    with driver.session() as session:
        # Test 1: Get all clauses
        print("\n[Test 1] 모든 조항 조회")
        result = session.run("""
            MATCH (c:PolicyClause)
            RETURN c.clauseId as id, c.title as title, c.clauseType as type
            ORDER BY c.articleNumber
            """)
        
        for record in result:
            print(f"  - {record['id']}: {record['title']} ({record['type']})")
        
        # Test 2: Get coverage clauses
        print("\n[Test 2] Coverage 타입 조항 검색")
        result = session.run("""
            MATCH (c:PolicyClause)
            WHERE c.clauseType = 'Coverage'
            RETURN c.clauseId as id, c.title as title
            """)
        
        for record in result:
            print(f"  - {record['id']}: {record['title']}")
        
        # Test 3: Get exclusion clauses
        print("\n[Test 3] Exclusion 타입 조항 검색")
        result = session.run("""
            MATCH (c:PolicyClause)
            WHERE c.clauseType = 'Exclusion'
            RETURN c.clauseId as id, c.title as title, c.text as text
            """)
        
        for record in result:
            print(f"  - {record['id']}: {record['title']}")
            print(f"    내용: {record['text'][:100]}...")
        
        # Test 4: Get paragraphs with semantic types
        print("\n[Test 4] Semantic Chunks 검색")
        result = session.run("""
            MATCH (c:PolicyClause)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
            RETURN c.clauseId as clauseId, 
                   p.chunkId as chunkId,
                   p.semanticType as semanticType,
                   p.text as text
            ORDER BY c.articleNumber
            """)
        
        for record in result:
            print(f"\n  [{record['clauseId']}] {record['semanticType'].upper()}")
            print(f"    {record['text'][:100]}...")
        
        # Test 5: Search by keyword
        print("\n[Test 5] 키워드 검색: '보상'")
        result = session.run("""
            MATCH (c:PolicyClause)
            WHERE c.text CONTAINS '보상'
            RETURN c.clauseId as id, c.title as title
            """)
        
        for record in result:
            print(f"  - {record['id']}: {record['title']}")
        
        # Test 6: Get special clause structure
        print("\n[Test 6] 특별약관 구조 조회")
        result = session.run("""
            MATCH (sc:SpecialClause)-[:HAS_CLAUSE]->(c:PolicyClause)
            RETURN sc.name as specialClause, 
                   collect(c.clauseId) as clauses
            """)
        
        for record in result:
            print(f"  {record['specialClause']}")
            print(f"    조항: {', '.join(record['clauses'])}")
        
        # Test 7: Coverage and Exclusion nodes
        print("\n[Test 7] Coverage/Exclusion 노드 조회")
        result = session.run("""
            MATCH (p:ParagraphChunk)-[:DEFINES_COVERAGE]->(cov:Coverage)
            RETURN count(cov) as coverageCount
            """)
        coverage_count = result.single()['coverageCount']
        
        result = session.run("""
            MATCH (p:ParagraphChunk)-[:HAS_EXCLUSION]->(exc:Exclusion)
            RETURN count(exc) as exclusionCount
            """)
        exclusion_count = result.single()['exclusionCount']
        
        print(f"  - Coverage 노드: {coverage_count}개")
        print(f"  - Exclusion 노드: {exclusion_count}개")
        
    driver.close()
    
    print("\n" + "="*80)
    print("✅ 그래프 쿼리 테스트 완료!")
    print("="*80)

def test_simple_qa():
    """Test simple QA without vector search"""
    print("\n" + "="*80)
    print("💬 간단한 QA 테스트 (그래프 기반)")
    print("="*80)
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password)
    )
    
    test_questions = [
        ("보상하는 손해는 무엇인가요?", "Coverage"),
        ("보상하지 않는 경우는 언제인가요?", "Exclusion"),
        ("도난으로 인한 손해가 보상되나요?", "Coverage"),
    ]
    
    for question, intent in test_questions:
        print(f"\n질문: {question}")
        print(f"의도: {intent}")
        print("-" * 80)
        
        with driver.session() as session:
            # Simple keyword-based search
            keywords = ['보상', '손해', '도난']
            keyword_in_question = [kw for kw in keywords if kw in question]
            
            if intent == "Coverage":
                query = """
                    MATCH (c:PolicyClause)
                    WHERE c.clauseType = 'Coverage'
                    OPTIONAL MATCH (c)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
                    WHERE p.semanticType = 'coverage'
                    RETURN c.clauseId as clauseId, 
                           c.title as title,
                           c.text as clauseText,
                           collect(p.text) as paragraphs
                    LIMIT 3
                    """
            else:  # Exclusion
                query = """
                    MATCH (c:PolicyClause)
                    WHERE c.clauseType = 'Exclusion'
                    OPTIONAL MATCH (c)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
                    WHERE p.semanticType = 'exclusion'
                    RETURN c.clauseId as clauseId,
                           c.title as title,
                           c.text as clauseText,
                           collect(p.text) as paragraphs
                    LIMIT 3
                    """
            
            result = session.run(query)
            
            print("검색 결과:")
            for record in result:
                print(f"\n  📄 {record['clauseId']} - {record['title']}")
                if record['paragraphs'] and record['paragraphs'][0]:
                    print(f"    관련 내용:")
                    for para in record['paragraphs'][:2]:
                        if para:
                            print(f"      • {para[:80]}...")
                else:
                    print(f"    전체 내용: {record['clauseText'][:150]}...")
    
    driver.close()
    
    print("\n" + "="*80)
    print("✅ QA 테스트 완료!")
    print("="*80)

def main():
    try:
        test_graph_queries()
        test_simple_qa()
        
        print("\n" + "="*80)
        print("🎉 모든 테스트 완료!")
        print("="*80)
        print("\n💡 다음 단계:")
        print("  1. 벡터 인덱스 설정 (Neo4j 5.12+에서는 다른 구문 필요)")
        print("  2. 전체 LangGraph RAG 파이프라인 테스트")
        print("  3. FastAPI 서버 실행: python3 -m src.api.main")
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

