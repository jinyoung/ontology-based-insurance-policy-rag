<template>
  <div class="query-page">
    <div class="container">
      <div class="query-header">
        <h1>Intelligent Query</h1>
        <p>자연어로 자유롭게 질문하세요. AI가 최적의 답변을 찾아드립니다.</p>
      </div>

      <!-- Query Input Section -->
      <div class="query-input-section">
        <div class="input-wrapper">
          <textarea
            v-model="question"
            class="query-textarea"
            placeholder="질문을 입력하세요..."
            :disabled="querying"
            @keydown.enter.prevent="submitQuery"
          ></textarea>
          <div class="input-actions">
            <span class="hint">Enter키를 눌러 전송</span>
            <button
              @click="submitQuery"
              :disabled="!question.trim() || querying"
              class="btn-send"
            >
              <span v-if="querying" class="spinner"></span>
              <span v-else>➤</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Recommended Queries -->
      <div v-if="!querying && !result" class="recommended-section">
        <div class="section-label">추천 질의</div>
        
        <div v-if="loadingRecommended" class="loading-skeleton">
          <div class="skeleton-card" v-for="i in 3" :key="i"></div>
        </div>

        <div v-else class="recommended-grid">
          <div
            v-for="(query, index) in recommendedQueries"
            :key="index"
            class="recommended-card"
            @click="selectRecommendedQuery(query.question)"
          >
            <div class="card-icon">💡</div>
            <div class="card-content">
              <div class="query-text">{{ query.question }}</div>
              <div class="query-desc">{{ query.description }}</div>
              <div class="tags">
                <span
                  v-for="clause in query.expected_clauses"
                  :key="clause"
                  class="tag"
                >
                  {{ clause }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Result Section -->
      <div v-if="result || querying" class="result-section">
        <!-- Loading State -->
        <div v-if="querying" class="processing-state">
          <div class="processing-steps">
            <div class="step active">질문 분석 중...</div>
            <div class="step">관련 조항 검색 중...</div>
            <div class="step">답변 생성 중...</div>
          </div>
        </div>

        <div v-if="result" class="result-container">
          <!-- Process Visualization -->
          <div v-if="process" class="process-card">
            <div class="card-header">
              <span class="icon">🌲</span>
              <h3>추론 과정 시각화</h3>
            </div>
            
            <div class="process-stats">
              <div class="stat">
                <span class="label">후보 조항</span>
                <span class="value">{{ process.candidates_count }}개</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat">
                <span class="label">선택 조항</span>
                <span class="value highlight">{{ process.selected_article.id }}</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat">
                <span class="label">참조 조항</span>
                <span class="value">{{ process.references }}개</span>
              </div>
            </div>

            <GraphVisualization
              v-if="process.sources"
              :sources="process.sources"
              :selected-article="process.selected_article"
            />
          </div>

          <!-- AI Answer -->
          <div class="answer-card">
            <div class="card-header">
              <span class="icon">✨</span>
              <h3>AI 답변</h3>
              <div class="confidence-badge" :class="getConfidenceClass(result.confidence)">
                신뢰도 {{ (result.confidence * 100).toFixed(0) }}%
              </div>
            </div>
            
            <div class="answer-body">
              <div class="answer-text">{{ result.answer }}</div>
            </div>

            <div v-if="result.citations && result.citations.length > 0" class="citations-area">
              <h4>참조된 근거 자료</h4>
              <div class="citations-list">
                <div
                  v-for="(citation, index) in result.citations"
                  :key="index"
                  class="citation-box"
                >
                  <div class="citation-header">
                    <span class="citation-id">{{ citation.clause_id }}</span>
                    <span class="citation-title">{{ citation.title }}</span>
                  </div>
                  <div v-if="citation.text" class="citation-snippet">
                    {{ citation.text }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <button @click="resetQuery" class="btn btn-secondary btn-reset">
            새로운 질문하기
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '../services/api'
import GraphVisualization from '../components/GraphVisualization.vue'

export default {
  name: 'Query',
  components: {
    GraphVisualization
  },
  setup() {
    const question = ref('')
    const querying = ref(false)
    const result = ref(null)
    const process = ref(null)
    
    const loadingRecommended = ref(false)
    const recommendedQueries = ref([])

    const loadRecommendedQueries = async () => {
      loadingRecommended.value = true
      try {
        const data = await api.getRecommendedQueries()
        recommendedQueries.value = data.queries || []
      } catch (error) {
        console.error('Failed to load recommended queries:', error)
      } finally {
        loadingRecommended.value = false
      }
    }

    const selectRecommendedQuery = (query) => {
      question.value = query
    }

    const submitQuery = async () => {
      if (!question.value.trim()) return

      querying.value = true
      result.value = null
      process.value = null

      try {
        const response = await api.queryDetailed(question.value, true)
        result.value = response
        process.value = response.process
      } catch (error) {
        alert('질의 처리 실패: ' + error.message)
      } finally {
        querying.value = false
      }
    }

    const resetQuery = () => {
      question.value = ''
      result.value = null
      process.value = null
    }

    const getConfidenceClass = (score) => {
      if (score >= 0.8) return 'high'
      if (score >= 0.5) return 'medium'
      return 'low'
    }

    onMounted(() => {
      loadRecommendedQueries()
    })

    return {
      question,
      querying,
      result,
      process,
      loadingRecommended,
      recommendedQueries,
      selectRecommendedQuery,
      submitQuery,
      resetQuery,
      getConfidenceClass
    }
  }
}
</script>

<style scoped>
.query-page {
  min-height: 100vh;
  background-color: #F8FAFC;
  padding-bottom: 4rem;
}

.query-header {
  text-align: center;
  padding: 3rem 0;
}

.query-header h1 {
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--text-color);
  margin-bottom: 0.5rem;
}

.query-header p {
  color: var(--text-light);
  font-size: 1.125rem;
}

.query-input-section {
  max-width: 800px;
  margin: 0 auto 3rem;
}

.input-wrapper {
  background: white;
  border-radius: 1.5rem;
  box-shadow: var(--shadow-lg);
  padding: 1rem;
  border: 1px solid rgba(0,0,0,0.05);
  position: relative;
  transition: all 0.3s ease;
}

.input-wrapper:focus-within {
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  transform: translateY(-2px);
  border-color: var(--primary-color);
}

.query-textarea {
  width: 100%;
  border: none;
  resize: none;
  font-size: 1.125rem;
  padding: 1rem;
  min-height: 80px;
  outline: none;
  color: var(--text-color);
  background: transparent;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem 0;
  border-top: 1px solid var(--border-color);
}

.hint {
  font-size: 0.75rem;
  color: var(--text-light);
}

.btn-send {
  background: var(--primary-color);
  color: white;
  border: none;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 1.2rem;
}

.btn-send:hover:not(:disabled) {
  transform: scale(1.1);
  background: var(--secondary-color);
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Recommended Queries */
.recommended-section {
  max-width: 1000px;
  margin: 0 auto;
}

.section-label {
  font-size: 0.875rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-light);
  margin-bottom: 1rem;
  letter-spacing: 0.05em;
}

.recommended-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}

.recommended-card {
  background: white;
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: var(--shadow);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  gap: 1rem;
}

.recommended-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--primary-color);
}

.card-icon {
  font-size: 1.5rem;
}

.query-text {
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.5rem;
  line-height: 1.4;
}

.query-desc {
  font-size: 0.875rem;
  color: var(--text-light);
  margin-bottom: 1rem;
}

.tags {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tag {
  background: var(--bg-light);
  color: var(--text-light);
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-weight: 500;
}

/* Results */
.result-section {
  max-width: 800px;
  margin: 0 auto;
}

.process-card, .answer-card {
  background: white;
  border-radius: 1rem;
  padding: 2rem;
  box-shadow: var(--shadow);
  margin-bottom: 2rem;
  border: 1px solid rgba(0,0,0,0.05);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.card-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.icon {
  font-size: 1.5rem;
}

.process-stats {
  display: flex;
  justify-content: space-around;
  background: var(--bg-light);
  padding: 1rem;
  border-radius: 0.75rem;
  margin-bottom: 2rem;
}

.stat {
  text-align: center;
}

.stat .label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-light);
  margin-bottom: 0.25rem;
}

.stat .value {
  font-weight: 700;
  font-size: 1.125rem;
  color: var(--text-color);
}

.stat .value.highlight {
  color: var(--primary-color);
}

.stat-divider {
  width: 1px;
  background: var(--border-color);
}

.answer-body {
  font-size: 1.125rem;
  line-height: 1.8;
  color: var(--text-color);
  margin-bottom: 2rem;
  white-space: pre-wrap;
}

.confidence-badge {
  margin-left: auto;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
}

.confidence-badge.high {
  background: #ECFDF5;
  color: #059669;
}

.citations-area {
  border-top: 1px solid var(--border-color);
  padding-top: 1.5rem;
}

.citations-area h4 {
  font-size: 0.875rem;
  color: var(--text-light);
  text-transform: uppercase;
  margin-bottom: 1rem;
}

.citation-box {
  background: var(--bg-light);
  padding: 1rem;
  border-radius: 0.75rem;
  margin-bottom: 0.75rem;
  border-left: 3px solid var(--primary-color);
}

.citation-header {
  margin-bottom: 0.25rem;
}

.citation-id {
  font-weight: 700;
  color: var(--primary-color);
  margin-right: 0.5rem;
}

.citation-title {
  font-weight: 600;
}

.citation-snippet {
  font-size: 0.875rem;
  color: var(--text-light);
  line-height: 1.5;
}

.btn-reset {
  width: 100%;
  padding: 1rem;
}

/* Loading Skeleton */
.loading-skeleton {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}

.skeleton-card {
  height: 120px;
  background: #e2e8f0;
  border-radius: 1rem;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
</style>
