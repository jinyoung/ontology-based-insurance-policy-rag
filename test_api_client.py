#!/usr/bin/env python3
"""
Simple API test client
"""
import requests
import json

API_URL = "http://localhost:8001/api/v1/query"

test_questions = [
    "보상하는 손해는 무엇인가요?",
    "보상하지 않는 손해는 무엇인가요?",
    "도난으로 인한 손해는 보상되나요?",
    "전쟁으로 인한 손해는 어떻게 처리되나요?",
    "지진 피해는 보상받을 수 있나요?",
]

print("\n" + "="*80)
print("🚀 PolicyGraph QA API 테스트")
print("="*80)

for i, question in enumerate(test_questions, 1):
    print(f"\n[질문 {i}] {question}")
    print("-"*80)
    
    try:
        response = requests.post(
            API_URL,
            json={"question": question},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"의도: {data['intent']}")
            print(f"신뢰도: {data['confidence']:.2f}")
            print(f"검색된 청크: {data['retrieved_chunks_count']}개")
            
            print(f"\n✅ 답변:")
            print(f"  {data['answer']}")
            
            if data['citations']:
                print(f"\n📚 참조 조항 ({len(data['citations'])}개):")
                for j, cit in enumerate(data['citations'][:3], 1):
                    print(f"  {j}. {cit['clause_id']} - {cit['title']}")
        else:
            print(f"❌ 오류: HTTP {response.status_code}")
            print(f"   {response.text}")
    
    except Exception as e:
        print(f"❌ 에러: {e}")
    
    print()

print("="*80)
print("✅ 테스트 완료!")
print("="*80)

