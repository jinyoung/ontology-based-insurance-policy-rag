# PolicyGraph QA Frontend

Vue.js 기반 보험약관 GraphRAG QA 시스템 프론트엔드

## 주요 기능

- 📄 **PDF 업로드 & Ingestion**: 보험약관 PDF를 업로드하고 자동으로 그래프 구조로 변환
- 🔍 **지능형 질의응답**: 여러 조항을 참조하는 복잡한 질문에도 정확한 답변 제공
- 💡 **추천 질의**: 자동 생성된 추천 질의로 쉽게 시작
- 🌲 **탐색 과정 시각화**: AI가 약관을 탐색하는 과정을 트리 구조로 시각화
- 📊 **실시간 진행 상태**: Ingestion 진행 상황을 실시간으로 확인

## 기술 스택

- **Frontend Framework**: Vue.js 3
- **Build Tool**: Vite
- **State Management**: Pinia
- **HTTP Client**: Axios
- **Visualization**: D3.js
- **Styling**: Custom CSS

## 설치 및 실행

### 1. 의존성 설치

```bash
cd frontend
npm install
```

### 2. 개발 서버 실행

```bash
npm run dev
```

프론트엔드는 `http://localhost:3000`에서 실행됩니다.

Backend API 서버가 `http://localhost:8001`에서 실행되고 있어야 합니다.

### 3. 프로덕션 빌드

```bash
npm run build
```

빌드된 파일은 `dist/` 디렉토리에 생성됩니다.

## 프로젝트 구조

```
frontend/
├── src/
│   ├── components/           # 재사용 가능한 컴포넌트
│   │   └── GraphVisualization.vue
│   ├── views/                # 페이지 컴포넌트
│   │   ├── Home.vue         # 홈 화면
│   │   ├── Ingestion.vue    # PDF 업로드 & Ingestion
│   │   └── Query.vue        # 질의응답 화면
│   ├── services/            # API 클라이언트
│   │   └── api.js
│   ├── router/              # Vue Router 설정
│   │   └── index.js
│   ├── App.vue              # 메인 앱 컴포넌트
│   ├── main.js              # 앱 진입점
│   └── style.css            # 전역 스타일
├── index.html               # HTML 템플릿
├── vite.config.js           # Vite 설정
└── package.json             # 패키지 정보
```

## 주요 화면

### 홈 (/)
- 시스템 소개 및 상태 확인
- 주요 기능 안내

### PDF 업로드 (/ingestion)
1. PDF 파일 업로드 (드래그 앤 드롭 지원)
2. Ingestion 설정 입력
3. 실시간 진행 상황 모니터링

### 질의하기 (/query)
1. 추천 질의 표시
2. 질문 입력
3. 약관 탐색 과정 시각화
4. AI 답변 및 참조 조항 표시

## API 엔드포인트

프론트엔드는 다음 Backend API를 사용합니다:

- `POST /api/v1/upload` - PDF 파일 업로드
- `POST /api/v1/ingestion/start` - Ingestion 시작
- `GET /api/v1/ingestion/status/{job_id}` - Ingestion 상태 조회
- `GET /api/v1/recommended-queries` - 추천 질의 조회
- `POST /api/v1/query/detailed` - 상세 질의 (탐색 과정 포함)

## 개발 가이드

### 새로운 컴포넌트 추가

```javascript
// src/components/NewComponent.vue
<template>
  <div class="new-component">
    <!-- 템플릿 -->
  </div>
</template>

<script>
export default {
  name: 'NewComponent',
  setup() {
    // 컴포넌트 로직
  }
}
</script>

<style scoped>
/* 컴포넌트 스타일 */
</style>
```

### API 클라이언트 확장

```javascript
// src/services/api.js
export default {
  async newEndpoint(param) {
    const response = await api.post('/new-endpoint', { param })
    return response.data
  }
}
```

## 트러블슈팅

### API 연결 오류
- Backend 서버가 `http://localhost:8001`에서 실행되고 있는지 확인
- CORS 설정이 올바른지 확인

### 빌드 오류
- Node.js 버전 확인 (v16 이상 권장)
- `node_modules` 삭제 후 재설치: `rm -rf node_modules && npm install`

## 라이선스

MIT License

