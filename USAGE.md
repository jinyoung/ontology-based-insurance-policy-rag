# PolicyGraph QA - 사용 가이드

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 API 키와 Neo4j 정보 입력

# 2. 의존성 설치
pip install -r requirements.txt

# 3. Neo4j 시작 (Docker 사용)
cd docker
docker-compose up -d
```

### 2. 데이터베이스 초기화

```bash
# Neo4j 스키마 초기화 (제약조건, 인덱스, 벡터 인덱스 생성)
python scripts/init_schema.py

# 샘플 데이터와 함께 초기화하려면:
python scripts/init_schema.py --with-sample-data
```

### 3. 약관 데이터 인제스션

```bash
# 약관 PDF를 Neo4j로 로딩
python scripts/ingest_policy.py \
  --file data/raw/LIG_주택화재보험약관.pdf \
  --product-code LIG_HOME_FIRE_2025 \
  --product-name "LIG 주택화재보험" \
  --version-id LIG_HOME_FIRE_2025_V1 \
  --init-schema

# 옵션:
# --init-schema: 스키마를 먼저 초기화 (첫 실행 시 권장)
# --semantic-chunking: LLM 기반 세미-시맨틱 청킹 사용 (기본값: True)
```

### 4. QA 시스템 테스트

```bash
# 샘플 질문으로 테스트
python scripts/test_qa.py
```

### 5. API 서버 실행

```bash
# FastAPI 서버 시작
python -m src.api.main

# 또는 uvicorn 직접 실행
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

API 문서: http://localhost:8000/docs

## 📚 Python API 사용 예시

### 기본 사용

```python
from src.rag.qa_engine import PolicyQAEngine

# QA 엔진 초기화
engine = PolicyQAEngine()

# 질문하기
result = engine.query("화재로 인한 손해를 보상받을 수 있나요?")

print(f"답변: {result['answer']}")
print(f"신뢰도: {result['confidence']}")
print(f"참조 조항: {result['citations']}")

# 리소스 정리
engine.close()
```

### 배치 질문

```python
questions = [
    "보상하는 손해는 무엇인가요?",
    "보상하지 않는 손해는?",
    "자기부담금은 얼마인가요?"
]

results = engine.batch_query(questions)

for result in results:
    print(f"Q: {result['question']}")
    print(f"A: {result['answer']}\n")
```

## 🌐 REST API 사용 예시

### 단일 질문

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "화재로 인한 손해를 보상받을 수 있나요?",
    "policy_version": "LIG_HOME_FIRE_2025_V1"
  }'
```

### 배치 질문

```bash
curl -X POST http://localhost:8000/api/v1/batch_query \
  -H "Content-Type: application/json" \
  -d '{
    "questions": [
      "보상하는 손해는?",
      "면책사항은?"
    ]
  }'
```

### 헬스 체크

```bash
curl http://localhost:8000/health
```

## 🔧 고급 사용

### 직접 Pipeline 사용

```python
from src.rag.langgraph_pipeline import PolicyGraphRAGPipeline

pipeline = PolicyGraphRAGPipeline()

result = pipeline.query("도난위험 특약의 제2조 내용은?")

print(f"의도: {result['intent']}")
print(f"키워드: {result['keywords']}")
print(f"답변: {result['answer']}")

pipeline.close()
```

### Retriever만 사용

```python
from src.retrieval.hybrid_retriever import HybridRetriever
from src.config.settings import settings

retriever = HybridRetriever(
    uri=settings.neo4j_uri,
    username=settings.neo4j_username,
    password=settings.neo4j_password,
    alpha=0.5  # 0=graph only, 1=vector only
)

results = retriever.retrieve(
    query="화재 보상",
    top_k=5,
    intent="coverage"
)

for result in results:
    print(f"Score: {result['hybrid_score']:.3f}")
    print(f"Text: {result['chunk']['text'][:100]}...")
    print()

retriever.close()
```

### 수동 인제스션 파이프라인

```python
from src.graph.ingestion import PolicyIngestionPipeline

pipeline = PolicyIngestionPipeline()

stats = pipeline.ingest_policy(
    pdf_path="path/to/policy.pdf",
    product_code="PRODUCT_CODE",
    product_name="Product Name",
    version_id="VERSION_ID",
    use_semantic_chunking=True
)

print(f"처리 완료: {stats}")
pipeline.close()
```

## 📊 주요 파라미터 조정

### `.env` 파일 설정

```bash
# 임베딩 모델 변경
EMBEDDING_MODEL=text-embedding-3-small  # 또는 text-embedding-3-large

# LLM 모델 변경
LLM_MODEL=gpt-4o-mini  # 또는 gpt-4o, gpt-4

# 검색 파라미터
RETRIEVAL_TOP_K=10  # 검색 결과 수
HYBRID_ALPHA=0.5  # 벡터/그래프 가중치 (0-1)

# 청킹 파라미터
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## 🐛 문제 해결

### Neo4j 연결 오류

```bash
# Neo4j가 실행 중인지 확인
docker ps | grep neo4j

# Neo4j 재시작
cd docker
docker-compose restart neo4j

# 로그 확인
docker-compose logs neo4j
```

### 임베딩 생성 오류

- OpenAI API 키가 올바른지 확인
- API 할당량이 남아있는지 확인
- 네트워크 연결 확인

### 검색 결과가 없음

- 데이터가 제대로 인제스션되었는지 확인:
  ```python
  from src.graph.schema import PolicyGraphSchema
  from src.config.settings import settings
  
  schema = PolicyGraphSchema(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
  result = schema.verify_schema()
  print(result)
  ```

## 📈 성능 최적화

1. **벡터 인덱스 최적화**: Neo4j 벡터 인덱스가 제대로 생성되었는지 확인
2. **청킹 전략**: 문서 특성에 맞게 `CHUNK_SIZE` 조정
3. **Hybrid Alpha**: 도메인 특성에 맞게 `HYBRID_ALPHA` 조정
4. **모델 선택**: 정확도와 비용의 균형을 위해 LLM 모델 조정

## 📝 추가 리소스

- [PRD.md](PRD.md): 전체 시스템 설계 문서
- [README.md](README.md): 프로젝트 개요
- API 문서: http://localhost:8000/docs (서버 실행 후)

