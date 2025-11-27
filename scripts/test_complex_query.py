#!/usr/bin/env python3
"""
Test Complex Query with Context Display
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from neo4j import GraphDatabase
from loguru import logger

from src.config.settings import settings
from src.retrieval.hierarchical_retriever import HierarchicalRetriever
from openai import OpenAI


def main():
    query = "서면동의 없이 가입된 사망보험에서 보험회사가 보험료를 돌려주지 않고, 계약자가 제6조에 따라 해지를 신청하면 어떻게 처리되나?"
    
    print('='*80)
    print('🧪 복잡 질의 테스트')
    print('='*80)
    print(f"질의: {query}")
    print()
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password)
    )
    
    # Initialize retriever
    retriever = HierarchicalRetriever(driver)
    
    # Retrieve context
    result = retriever.retrieve(query, top_k=5)
    
    if result['selected_article']:
        print('='*80)
        print('✅ 선택된 조항')
        print('='*80)
        print(f"조항 ID: {result['selected_article']['articleId']}")
        print(f"조항 제목: {result['selected_article']['title']}")
        print()
        
        print('='*80)
        print('📊 메타데이터')
        print('='*80)
        print(f"후보 노드 수: {result['metadata']['candidates_count']}")
        print(f"상위 조항 수: {result['metadata']['articles_count']}")
        print(f"참조 수: {result['metadata']['references_count']}")
        print()
        
        print('='*80)
        print('📎 포함된 소스')
        print('='*80)
        for i, source in enumerate(result['sources'], 1):
            print(f"{i}. {source['type']}: {source['id']}")
            if source.get('title'):
                print(f"   제목: {source['title']}")
        print()
        
        print('='*80)
        print('🔗 참조된 조항 (REFERS_TO)')
        print('='*80)
        # Get references from context_data (not from result directly)
        refs_count = result['metadata'].get('references_count', 0)
        if refs_count > 0:
            print(f"총 {refs_count}개의 참조 발견")
            # References are embedded in the context itself
            print("(컨텍스트에 포함됨)")
        else:
            print("참조 없음")
        print()
        
        print('='*80)
        print('📄 LLM에게 전달되는 전체 컨텍스트')
        print('='*80)
        print(result['context'])
        print()
        print('='*80)
        
        # Generate answer using OpenAI
        print()
        print('='*80)
        print('💬 생성된 답변')
        print('='*80)
        
        openai_client = OpenAI(api_key=settings.openai_api_key)
        
        try:
            response = openai_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 보험약관 전문가입니다. 주어진 약관 내용을 바탕으로 사용자 질문에 정확하고 친절하게 답변해주세요."},
                    {"role": "user", "content": f"약관 내용:\n\n{result['context']}\n\n질문: {query}\n\n답변:"}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            answer = response.choices[0].message.content
            print(answer)
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
    else:
        print("❌ 관련 조항을 찾을 수 없습니다.")
    
    driver.close()


if __name__ == "__main__":
    main()

