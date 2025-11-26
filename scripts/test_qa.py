#!/usr/bin/env python3
"""
Script to test the QA engine with sample questions
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.rag.qa_engine import PolicyQAEngine


def print_result(result):
    """Pretty print QA result"""
    print("\n" + "=" * 80)
    print(f"질문: {result['question']}")
    print("=" * 80)
    print(f"\n의도: {result['intent']}")
    print(f"신뢰도: {result['confidence']:.2f}")
    print(f"\n답변:\n{result['answer']}")
    
    if result['citations']:
        print(f"\n참조 조항 ({len(result['citations'])}개):")
        for i, citation in enumerate(result['citations'], 1):
            print(f"  {i}. {citation.get('clause_id', 'N/A')} - {citation.get('title', 'N/A')}")
            if citation.get('text'):
                print(f"     {citation['text'][:100]}...")
    
    print(f"\n검색된 청크 수: {result['retrieved_chunks_count']}")
    print("=" * 80)


def main():
    logger.info("Initializing QA Engine...")
    engine = PolicyQAEngine()
    
    # Sample test questions
    test_questions = [
        "화재로 인한 손해를 보상받을 수 있나요?",
        "보상하지 않는 손해는 무엇인가요?",
        "도난위험 특약에서 보상하는 손해는?",
        "자기부담금은 얼마인가요?",
        "제11조의 내용은 무엇인가요?",
    ]
    
    print("\n" + "🔍 " * 40)
    print("PolicyGraph QA System - Test Suite")
    print("🔍 " * 40)
    
    for question in test_questions:
        try:
            result = engine.query(question)
            print_result(result)
        except Exception as e:
            logger.error(f"Error processing question '{question}': {e}")
            continue
    
    print("\n✅ Test complete")
    engine.close()


if __name__ == "__main__":
    main()

