# 개선 사항 (Improvements)

## ✅ LLM 기반 Semantic Type 식별

### 문제점
초기 구현에서는 `clause_extractor.py`가 단순 키워드 매칭으로 Coverage/Exclusion/Condition을 구분했습니다:

```python
# ❌ 부정확한 방식
COVERAGE_KEYWORDS = ['보상하는', '지급', '담보', '보장']
EXCLUSION_KEYWORDS = ['보상하지', '면책', '제외', '지급하지']
# ... keyword matching으로 타입 결정
```

**문제점:**
- 키워드가 여러 문맥에서 사용될 수 있어 부정확
- 복합적인 조항 (coverage + exclusion 혼재) 처리 불가
- 한국어 문맥 이해 부족

### 개선 사항

#### 1. Clause Extractor - 최소한의 Hint만 제공
```python
# ✅ clause_extractor.py
def _get_hint_from_title(self, title: str) -> Optional[str]:
    """
    제목에서만 기본 힌트를 얻고, 
    정확한 타입은 LLM이 결정하도록 함
    """
    # 제목에 명확한 키워드가 있을 때만 힌트 제공
    if "보상하지" in title or "면책" in title:
        return "Exclusion"
    # ... 
    return None  # 대부분의 경우 LLM이 결정
```

#### 2. Semantic Chunker - LLM 기반 정확한 식별

**개선된 프롬프트:**
```python
SEMANTIC_TYPE_DEFINITIONS:
- "coverage": What IS covered/compensated (보상하는 손해, 지급하는 보험금)
- "exclusion": What is NOT covered/excluded (보상하지 아니하는 손해, 면책사항)
- "condition": Requirements, procedures (조건, 의무, 청구절차)
- "deductible": Self-payment amounts (자기부담금)
- "limit": Coverage limits (보상한도)
- "definition": Term definitions (용어의 정의)
- "procedure": Administrative procedures (절차, 방법)
```

**LLM이 반환하는 정보:**
```json
{
  "chunks": [
    {
      "label": "화재 직접손해 보상",
      "semantic_type": "coverage",
      "content": "원문 그대로...",
      "reasoning": "보상하는 손해의 범위를 명시하고 있음"
    }
  ]
}
```

#### 3. 메타데이터에 LLM 식별 여부 표시

```python
chunk_metadata = {
    'semantic_type': 'coverage',
    'llm_identified': True,  # LLM이 식별했음을 표시
    'reasoning': '보상 범위 명시',
    'label': '화재 직접손해 보상'
}
```

### 효과

#### Before (키워드 매칭)
```
제11조 "화재로 인한 손해를 보상하되, 계약자의 고의는 제외합니다"
→ "보상" 키워드 발견 → Coverage 분류 ❌
  (exclusion 내용이 포함되어 있는데 놓침)
```

#### After (LLM 분석)
```
제11조 "화재로 인한 손해를 보상하되, 계약자의 고의는 제외합니다"
→ LLM 분석:
  Chunk 1: "화재로 인한 손해를 보상" → Coverage ✅
  Chunk 2: "계약자의 고의는 제외" → Exclusion ✅
  (정확히 두 개의 semantic type으로 분리)
```

### 구현 상세

#### clause_extractor.py
- `_detect_clause_type()` 메서드 제거
- `_get_hint_from_title()` 로 대체 (제목에서만 힌트)
- clause_type은 기본적으로 `None` 또는 basic hint

#### semantic_chunker.py
- 강화된 프롬프트 (semantic type 정의 명확화)
- LLM에게 각 청크의 reasoning 요구
- `llm_identified: True` 메타데이터 추가
- `_infer_type_from_metadata()` 메서드 제거

#### ingestion.py
- LLM이 식별한 semantic_type을 Neo4j에 저장
- Coverage/Exclusion 노드 생성 시 LLM 판단 사용

### 추가 개선 가능 사항

1. **Few-shot Examples**: 프롬프트에 정확한 예시 추가
2. **Validation**: LLM 출력 검증 로직 추가
3. **Confidence Score**: LLM이 semantic type 판단의 신뢰도 반환
4. **Human-in-the-Loop**: 낮은 신뢰도의 경우 사람 검증

## 🎯 핵심 원칙

1. **구조 추출은 규칙 기반** (조/항/호 파싱)
   - 정규식으로 정확하게 추출 가능

2. **의미 식별은 LLM 기반** (semantic type)
   - 문맥 이해가 필요한 작업
   - 키워드 매칭으로는 부정확

3. **원문 보존**
   - LLM은 요약/재작성하지 않음
   - 분리와 분류만 수행

4. **추적 가능성**
   - 모든 LLM 판단에 reasoning 추가
   - 메타데이터에 출처 명시

## 📊 기대 효과

- ✅ Semantic Type 식별 정확도 향상 (60% → 90%+ 예상)
- ✅ 복합 조항 처리 가능 (coverage + exclusion 혼재)
- ✅ 문맥 기반 정확한 분류
- ✅ 추후 fine-tuning 가능한 구조

