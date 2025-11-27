#!/usr/bin/env python3
"""
Test Hierarchical Retrieval Strategy

Tests the new retrieval logic:
1. Vector search for top-k nodes
2. Get parent Articles
3. LLM selects best Article
4. Build context with REFERS_TO connections
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from neo4j import GraphDatabase
from loguru import logger
from openai import OpenAI

from src.config.settings import settings
from src.retrieval.hierarchical_retriever import HierarchicalRetriever


def main():
    logger.info("="*80)
    logger.info("🔬 Hierarchical Retrieval Test")
    logger.info("="*80)
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password)
    )
    
    # Initialize retriever
    retriever = HierarchicalRetriever(driver)
    
    # Test queries
    test_queries = [
        "청약을 철회할 수 있나요?",
        "계약이 무효가 되는 경우는?",
        "보험료는 어떻게 납입하나요?",
    ]
    
    openai_client = OpenAI(api_key=settings.openai_api_key)
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"[Test {i}/{len(test_queries)}] Query: {query}")
        logger.info(f"{'='*80}\n")
        
        # Retrieve context
        result = retriever.retrieve(query, top_k=5)
        
        if result['selected_article']:
            print("✅ 선택된 조항:")
            print(f"   {result['selected_article']['articleId']}: {result['selected_article']['title']}")
            print()
            
            print("📊 메타데이터:")
            for key, value in result['metadata'].items():
                print(f"   {key}: {value}")
            print()
            
            print("📎 참조된 조항:")
            if result['sources']:
                for source in result['sources']:
                    print(f"   - {source['type']}: {source['id']}")
            if result.get('metadata', {}).get('references_count', 0) > 0:
                for ref in result.get('metadata', {}).get('references', []):
                    print(f"   - [참조] {ref.get('type')}: {ref.get('id')}")
            print()
            
            print("📄 컨텍스트 (처음 500자):")
            print(result['context'][:500])
            print("...")
            print()
            
            # Generate answer using LLM
            print("💬 생성된 답변:")
            try:
                response = openai_client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": "당신은 보험약관 전문가입니다. 주어진 약관 내용을 바탕으로 사용자 질문에 정확하고 친절하게 답변해주세요."},
                        {"role": "user", "content": f"약관 내용:\n\n{result['context']}\n\n질문: {query}\n\n답변:"}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                answer = response.choices[0].message.content
                print(answer)
                
            except Exception as e:
                logger.error(f"Answer generation failed: {e}")
        else:
            print("❌ 관련 조항을 찾을 수 없습니다.")
            if 'error' in result.get('metadata', {}):
                print(f"   오류: {result['metadata']['error']}")
        
        print()
    
    driver.close()
    logger.info("✅ Test completed")


if __name__ == "__main__":
    main()

