#!/usr/bin/env python3
"""
Test parsing and chunking without Neo4j
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.parsers.clause_extractor import ClauseExtractor
from src.chunking.semantic_chunker import SemanticChunker

# Sample insurance policy text
SAMPLE_TEXT = """
【도난위험 특별약관】

제1조(보상하는 손해) 회사는 보험증권에 기재된 보험의 목적에 대하여 도난으로 인한 손해를 보상합니다.
① 도난으로 인한 직접적인 손해를 보상합니다.
② 도난물품의 회수에 소요된 비용을 보상합니다.

제2조(보상하지 아니하는 손해) 회사는 다음의 손해는 보상하지 아니합니다.
1. 계약자, 피보험자 또는 이들의 법정대리인의 고의 또는 중대한 과실로 생긴 손해
2. 전쟁, 혁명, 내란, 사변, 폭동, 소요 및 이와 유사한 사태로 생긴 손해
3. 지진, 분화 등 천재지변으로 생긴 손해

제3조(자기부담금) 회사가 보상할 손해액에서 증권에 기재된 자기부담금을 공제하고 보험금을 지급합니다.

제11조(보상하는 손해) 회사는 이 계약에 따라 보험의 목적에 대하여 다음 각호의 손해를 보상합니다.
1. 직접손해: 화재, 낙뢰, 파열 또는 폭발로 보험의 목적에 생긴 손해를 말합니다.
2. 소방손해: 화재를 소방하기 위하여 필요한 조치로 생긴 손해를 말합니다.
3. 피난손해: 화재가 발생한 때 피난으로 생긴 보험의 목적의 손해를 말합니다.
4. 잔존물 제거비용: 손해를 입은 보험의 목적의 잔존물을 제거하는데 드는 비용
5. 손해방지비용: 손해의 방지 또는 경감을 위하여 지출한 필요 또는 유익한 비용

다만, 계약자, 피보험자 또는 이들의 법정대리인의 고의 또는 중대한 과실로 생긴 손해는 보상하지 아니합니다.
"""


def main():
    print("\n" + "="*80)
    print("📄 보험약관 파싱 및 청킹 테스트 (Neo4j 없이)")
    print("="*80)
    
    # Step 1: Extract clauses
    print("\n[Step 1] 조항 추출 중...")
    extractor = ClauseExtractor()
    clauses = extractor.extract_clauses(SAMPLE_TEXT)
    
    # Extract items for each clause
    for clause in clauses:
        extractor.extract_items_from_clause(clause)
    
    print(f"✅ {len(clauses)}개 조항 추출 완료")
    
    # Display clauses
    print("\n" + "-"*80)
    print("추출된 조항:")
    print("-"*80)
    for i, clause in enumerate(clauses, 1):
        print(f"\n{i}. {clause.clause_id} - {clause.title}")
        print(f"   타입 힌트: {clause.clause_type or 'None (LLM이 결정)'}")
        print(f"   섹션 경로: {clause.section_path}")
        if clause.parent_section:
            print(f"   상위 특약: {clause.parent_section}")
        print(f"   텍스트 길이: {len(clause.full_text)}자")
        if clause.items:
            print(f"   항목 수: {len(clause.items)}개")
            for j, item in enumerate(clause.items[:2], 1):  # Show first 2 items
                print(f"     {j}. {item[:80]}...")
    
    # Step 2: Test semantic chunking
    print("\n" + "="*80)
    print("[Step 2] LLM 기반 세미-시맨틱 청킹 테스트")
    print("="*80)
    
    try:
        chunker = SemanticChunker()
        
        # Test with one clause (use longest one for better demo)
        test_clause = max(clauses, key=lambda c: len(c.full_text))
        print(f"\n테스트 조항: {test_clause.clause_id} - {test_clause.title}")
        print(f"원본 텍스트:\n{test_clause.full_text[:200]}...")
        
        metadata = {
            'clause_id': test_clause.clause_id,
            'title': test_clause.title,
            'clause_type': test_clause.clause_type
        }
        
        print("\n🤖 LLM 분석 중...")
        chunks = chunker.chunk_text(test_clause.full_text, metadata)
        
        print(f"\n✅ {len(chunks)}개 청크 생성 완료")
        
        print("\n" + "-"*80)
        print("LLM이 식별한 Semantic Chunks:")
        print("-"*80)
        
        for i, chunk in enumerate(chunks, 1):
            print(f"\n[Chunk {i}] {chunk.semantic_type.upper()}")
            print(f"  라벨: {chunk.metadata.get('label', 'N/A')}")
            print(f"  근거: {chunk.metadata.get('reasoning', 'N/A')}")
            print(f"  LLM 식별: {chunk.metadata.get('llm_identified', False)}")
            print(f"  내용: {chunk.content[:150]}...")
        
    except Exception as e:
        print(f"\n⚠️  LLM 청킹 테스트 실패: {e}")
        print("   (OpenAI API 키가 올바른지 확인하세요)")
    
    print("\n" + "="*80)
    print("✅ 테스트 완료!")
    print("="*80)
    
    print("\n💡 다음 단계:")
    print("1. Docker를 시작하고 Neo4j 실행: cd docker && docker-compose up -d")
    print("2. 스키마 초기화: python scripts/init_schema.py")
    print("3. 약관 인제스션: python scripts/ingest_policy.py --file <PDF경로> ...")
    print("4. QA 테스트: python scripts/test_qa.py")


if __name__ == "__main__":
    main()

