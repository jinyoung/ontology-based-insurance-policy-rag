# PolicyGraph QA (MVP)

보험약관 GraphRAG QA 시스템 - LangChain + LangGraph + Neo4j + UV Embeddings

## 📋 프로젝트 개요

LIG 주택화재보험 약관을 포함한 보험약관을 **조·항·호 기반 그래프 구조**로 모델링하고, 
GraphRAG를 통해 정확한 질의응답을 제공하는 시스템입니다.

### 주요 기능

- ✅ 보험약관 PDF 파싱 및 구조적 청킹 (조/항/호 단위)
- ✅ LLM 기반 세미-시맨틱 청킹
- ✅ Neo4j 기반 보험 온톨로지 그래프 구축
- ✅ LangGraph 기반 GraphRAG Retrieval
- ✅ Coverage/Exclusion/Condition 자동 식별
- ✅ 출처 기반 Answer with Citation

## 🏗️ 아키텍처

```
PDF 약관 → 구조 파싱 → 의미 청킹 → Neo4j 그래프 → GraphRAG → QA
                ↓                    ↓
            조/항/호 추출      임베딩 생성
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 편집하여 API 키와 Neo4j 설정을 입력하세요
```

### 2. Neo4j 실행 (Docker)

```bash
cd docker
docker-compose up -d
```

### 3. 약관 데이터 로딩

```bash
# 약관 PDF를 data/raw/ 디렉토리에 배치
python -m src.scripts.ingest_policy --file data/raw/policy.pdf
```

### 4. API 서버 실행

```bash
python -m src.api.main
```

API는 `http://localhost:8000`에서 실행됩니다.

## 📚 사용 예시

### QA 질의

```python
from src.rag.qa_engine import PolicyQAEngine

engine = PolicyQAEngine()
result = engine.query("풍수재위험 특별약관에서 보상하지 않는 손해는?")

print(result["answer"])
print(result["citations"])
```

### REST API

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "도난위험 특약의 면책사항은?",
    "policy_version": "LIG_2025_V1"
  }'
```

## 🗂️ 프로젝트 구조

```
fin_graphRAG/
├── src/
│   ├── config/           # 설정 관리
│   ├── parsers/          # PDF 파싱 및 조항 추출
│   ├── chunking/         # 규칙 기반 및 의미 기반 청킹
│   ├── graph/            # Neo4j 스키마 및 데이터 로딩
│   ├── retrieval/        # 그래프 및 하이브리드 검색
│   ├── rag/              # LangGraph RAG 파이프라인
│   └── api/              # FastAPI 백엔드
├── tests/                # 테스트
├── data/                 # 데이터 디렉토리
├── notebooks/            # Jupyter 노트북
└── docker/               # Docker 설정
```

## 🎯 MVP 성공 기준

- ✅ 정확도 ≥ 80%
- ✅ Coverage/Exclusion/Condition 정확 식별
- ✅ 모든 답변에 조항 출처 제공
- ✅ 응답 시간 < 3초
- ✅ 재현 가능한 GraphRAG QA

## 📖 문서

자세한 내용은 [PRD.md](PRD.md)를 참조하세요.

## 🛠️ 기술 스택

- **Orchestration**: LangGraph
- **LLM**: GPT-4o-mini / GPT-4
- **Embeddings**: OpenAI text-embedding-3-small
- **Graph DB**: Neo4j 5.x
- **Backend**: FastAPI
- **PDF Parser**: PyMuPDF + Regex

## 📝 라이센스

MIT License

