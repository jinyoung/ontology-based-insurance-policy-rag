<template>
  <div class="query-page">
    <div class="page-header">
      <div class="container">
        <h1 class="page-title">Intelligent Query</h1>
        <p class="page-subtitle">자연어로 보험약관에 대해 질문하세요</p>
      </div>
    </div>

    <div class="container content-container">
      <!-- Query Input -->
      <div class="query-input-section">
        <div class="query-input-card">
          <div class="input-wrapper">
            <input
              type="text"
              v-model="question"
              @keyup.enter="submitQuery"
              placeholder="질문을 입력하세요... (예: 청약 철회는 어떻게 하나요?)"
              class="query-input"
              :disabled="isLoading"
            />
            <button @click="submitQuery" :disabled="!question.trim() || isLoading" class="send-button">
              <span v-if="isLoading" class="spinner"></span>
              <span v-else>➤</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Recommended Queries -->
      <div v-if="!queryResult && !isLoading && recommendedQueries.length > 0" class="recommended-section">
        <h3 class="section-title">💡 추천 질문</h3>
        <div class="recommended-grid">
          <div 
            v-for="(rec, index) in recommendedQueries" 
            :key="index" 
            class="recommended-card"
            @click="selectRecommendedQuery(rec.question)"
          >
            <div class="rec-question">{{ rec.question }}</div>
            <div class="rec-description">{{ rec.description }}</div>
            <div class="rec-clauses">
              <span v-for="clause in rec.expected_clauses" :key="clause" class="clause-badge">
                {{ clause }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Processing Steps -->
      <div v-if="isLoading" class="processing-section">
        <div class="processing-card">
          <h3 class="processing-title">🔍 질의 처리 중...</h3>
          
          <div class="progress-bar-wrapper">
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" :style="{ width: currentProgress + '%' }"></div>
            </div>
            <span class="progress-percent">{{ currentProgress }}%</span>
          </div>
          
          <div class="steps-timeline">
            <div 
              v-for="step in processingSteps" 
              :key="step.id"
              class="step-item"
              :class="{ 
                active: currentStep === step.id, 
                completed: completedSteps.includes(step.id),
                pending: currentStep < step.id
              }"
            >
              <div class="step-icon">
                <span v-if="completedSteps.includes(step.id)">✓</span>
                <span v-else-if="currentStep === step.id" class="spinner-small"></span>
                <span v-else>{{ step.id }}</span>
              </div>
              <div class="step-content">
                <div class="step-name">{{ step.name }}</div>
                <div v-if="currentStep === step.id && stepDetail" class="step-detail">
                  {{ stepDetail }}
                </div>
                <div v-if="step.id === 2 && stepData.candidates" class="step-data">
                  후보: {{ stepData.candidates.join(', ') }}
                </div>
                <div v-if="step.id === 3 && stepData.articles" class="step-data">
                  조항: {{ stepData.articles.join(', ') }}
                </div>
                <div v-if="step.id === 4 && stepData.selected_article" class="step-data">
                  선택됨: <strong>{{ stepData.selected_article }}</strong>
                </div>
                <div v-if="step.id === 5 && stepData.references" class="step-data">
                  참조: {{ stepData.references.join(', ') || '없음' }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Query Result -->
      <div v-if="queryResult" class="result-section">
        <!-- Answer First -->
        <div class="answer-card">
          <div class="card-header">
            <span class="header-icon">✨</span>
            <h3>AI 답변</h3>
            <span class="confidence-badge" :class="getConfidenceClass(queryResult.confidence)">
              신뢰도 {{ Math.round((queryResult.confidence || 0) * 100) }}%
            </span>
          </div>
          
          <div class="answer-content markdown-body" v-html="renderMarkdown(queryResult.answer)"></div>
          
          <div v-if="queryResult.citations?.length > 0" class="citations-section">
            <h4>📚 참조 근거</h4>
            <div v-for="(citation, index) in queryResult.citations" :key="index" class="citation-item">
              <div class="citation-header">
                <span class="citation-id">{{ citation.clause_id }}</span>
                <span class="citation-title">{{ citation.title }}</span>
              </div>
              <p class="citation-text">{{ citation.text }}</p>
            </div>
          </div>
        </div>

        <!-- Process Visualization Below -->
        <div class="process-card">
          <div class="card-header collapsible" @click="showProcess = !showProcess">
            <span class="header-icon">🌲</span>
            <h3>추론 과정</h3>
            <span class="toggle-icon">{{ showProcess ? '▲' : '▼' }}</span>
          </div>
          
          <div v-show="showProcess" class="process-body">
            <div class="process-summary">
              <div class="summary-item">
                <span class="label">검색된 후보</span>
                <span class="value">{{ queryResult.process?.candidates_count || 0 }}개</span>
              </div>
              <div class="summary-item highlight">
                <span class="label">선택된 조항</span>
                <span class="value">{{ queryResult.process?.selected_article?.id }}</span>
              </div>
              <div class="summary-item">
                <span class="label">참조 조항</span>
                <span class="value">{{ queryResult.process?.references || 0 }}개</span>
              </div>
            </div>
            
            <GraphVisualization 
              v-if="queryResult.process?.sources"
              :sources="queryResult.process.sources" 
              :selectedArticle="queryResult.process.selected_article" 
            />
          </div>
        </div>

        <div class="action-buttons">
          <button @click="resetQuery" class="btn btn-primary">새로운 질문하기</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { marked } from 'marked'
import api from '../services/api'
import GraphVisualization from '../components/GraphVisualization.vue'

export default {
  name: 'Query',
  components: { GraphVisualization },
  setup() {
    const question = ref('')
    const isLoading = ref(false)
    const queryResult = ref(null)
    const recommendedQueries = ref([])
    
    // Processing state
    const currentStep = ref(0)
    const currentProgress = ref(0)
    const completedSteps = ref([])
    const stepDetail = ref('')
    const stepData = ref({})
    const showProcess = ref(true)  // Toggle for process visualization
    
    const processingSteps = [
      { id: 1, name: '질문 분석 및 임베딩 생성' },
      { id: 2, name: '유사 조항 검색 (벡터 유사도)' },
      { id: 3, name: '상위 조(條) 추출' },
      { id: 4, name: 'LLM으로 최적 조항 선택' },
      { id: 5, name: '참조 조항(REFERS_TO) 탐색' },
      { id: 6, name: 'LLM 답변 생성' }
    ]

    onMounted(async () => {
      try {
        const result = await api.getRecommendedQueries()
        recommendedQueries.value = result.queries || []
      } catch (error) {
        console.error('Failed to load recommended queries:', error)
      }
    })

    const selectRecommendedQuery = (q) => {
      question.value = q
      submitQuery()
    }
    
    const renderMarkdown = (text) => {
      if (!text) return ''
      return marked(text)
    }

    const submitQuery = async () => {
      if (!question.value.trim() || isLoading.value) return
      
      isLoading.value = true
      queryResult.value = null
      currentStep.value = 0
      currentProgress.value = 0
      completedSteps.value = []
      stepDetail.value = ''
      stepData.value = {}
      
      try {
        // Use EventSource for streaming
        const response = await fetch('/api/v1/query/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            question: question.value,
            include_process: true
          })
        })
        
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
          const text = decoder.decode(value)
          const lines = text.split('\n')
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                handleStreamData(data)
              } catch (e) {
                // Ignore parse errors
              }
            }
          }
        }
        
      } catch (error) {
        console.error('Query failed:', error)
        alert('질의 처리 중 오류가 발생했습니다.')
      } finally {
        isLoading.value = false
      }
    }
    
    const handleStreamData = (data) => {
      if (data.percent) {
        currentProgress.value = data.percent
      }
      
      if (data.step) {
        currentStep.value = data.step
        
        if (data.status === 'completed' && !completedSteps.value.includes(data.step)) {
          completedSteps.value.push(data.step)
        }
        
        if (data.detail) {
          stepDetail.value = data.detail
        }
        
        // Store step-specific data
        if (data.candidates) {
          stepData.value.candidates = data.candidates
        }
        if (data.articles) {
          stepData.value.articles = data.articles
        }
        if (data.selected_article) {
          stepData.value.selected_article = data.selected_article
        }
        if (data.references) {
          stepData.value.references = data.references
        }
        
        // Final result
        if (data.result) {
          queryResult.value = data.result
        }
      }
      
      if (data.error) {
        alert(`오류: ${data.error}`)
      }
    }

    const resetQuery = () => {
      question.value = ''
      queryResult.value = null
      currentStep.value = 0
      currentProgress.value = 0
      completedSteps.value = []
      stepDetail.value = ''
      stepData.value = {}
    }
    
    const getConfidenceClass = (confidence) => {
      if (confidence >= 0.8) return 'high'
      if (confidence >= 0.5) return 'medium'
      return 'low'
    }

    return {
      question, isLoading, queryResult, recommendedQueries,
      currentStep, currentProgress, completedSteps, stepDetail, stepData,
      processingSteps, showProcess,
      selectRecommendedQuery, submitQuery, resetQuery, getConfidenceClass, renderMarkdown
    }
  }
}
</script>

<style scoped>
.query-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #F8FAFC 0%, #EEF2FF 100%);
  padding-bottom: 4rem;
}

.page-header {
  background: linear-gradient(135deg, #312E81 0%, #4F46E5 100%);
  color: white;
  padding: 3rem 0;
  margin-bottom: 2rem;
  border-bottom-left-radius: 2rem;
  border-bottom-right-radius: 2rem;
}

.page-title {
  font-size: 2.5rem;
  font-weight: 800;
  margin-bottom: 0.5rem;
}

.page-subtitle {
  opacity: 0.9;
  font-size: 1.125rem;
}

.content-container {
  max-width: 900px;
}

/* Query Input */
.query-input-section {
  margin-bottom: 2rem;
}

.query-input-card {
  background: white;
  border-radius: 1.5rem;
  padding: 0.5rem;
  box-shadow: 0 10px 40px rgba(79, 70, 229, 0.15);
}

.input-wrapper {
  display: flex;
  gap: 0.5rem;
}

.query-input {
  flex: 1;
  padding: 1.25rem 1.5rem;
  border: none;
  border-radius: 1.25rem;
  font-size: 1.125rem;
  background: transparent;
  outline: none;
}

.query-input::placeholder {
  color: #9CA3AF;
}

.send-button {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
  color: white;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.send-button:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 20px rgba(79, 70, 229, 0.4);
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Recommended Section */
.recommended-section {
  margin-bottom: 2rem;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 1rem;
}

.recommended-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.recommended-card {
  background: white;
  border-radius: 1rem;
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid transparent;
}

.recommended-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.rec-question {
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.5rem;
  line-height: 1.4;
}

.rec-description {
  font-size: 0.875rem;
  color: var(--text-light);
  margin-bottom: 0.75rem;
}

.rec-clauses {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.clause-badge {
  background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
  color: #4F46E5;
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 600;
}

/* Processing Section */
.processing-section {
  margin-bottom: 2rem;
}

.processing-card {
  background: white;
  border-radius: 1.5rem;
  padding: 2rem;
  box-shadow: var(--shadow-lg);
}

.processing-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
  color: var(--text-color);
}

.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.progress-bar-bg {
  flex: 1;
  height: 8px;
  background: #E5E7EB;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 100%);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-percent {
  font-weight: 700;
  color: var(--primary-color);
  min-width: 50px;
  text-align: right;
}

.steps-timeline {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.step-item {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border-radius: 0.75rem;
  background: #F9FAFB;
  transition: all 0.3s ease;
}

.step-item.active {
  background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
  border-left: 3px solid var(--primary-color);
}

.step-item.completed {
  background: #ECFDF5;
  border-left: 3px solid #10B981;
}

.step-item.pending {
  opacity: 0.5;
}

.step-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.875rem;
  color: var(--text-light);
  box-shadow: var(--shadow-sm);
}

.step-item.completed .step-icon {
  background: #10B981;
  color: white;
}

.step-item.active .step-icon {
  background: var(--primary-color);
  color: white;
}

.step-content {
  flex: 1;
}

.step-name {
  font-weight: 600;
  color: var(--text-color);
}

.step-detail {
  font-size: 0.875rem;
  color: var(--text-light);
  margin-top: 0.25rem;
}

.step-data {
  font-size: 0.8125rem;
  color: var(--primary-color);
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: white;
  border-radius: 0.5rem;
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Result Section */
.result-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.process-card, .answer-card {
  background: white;
  border-radius: 1.5rem;
  padding: 2rem;
  box-shadow: var(--shadow-lg);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.card-header.collapsible {
  cursor: pointer;
  padding: 0.5rem;
  margin: -0.5rem;
  margin-bottom: 0;
  border-radius: 0.5rem;
  transition: background 0.2s ease;
}

.card-header.collapsible:hover {
  background: var(--bg-light);
}

.toggle-icon {
  font-size: 0.75rem;
  color: var(--text-light);
  transition: transform 0.2s ease;
}

.header-icon {
  font-size: 1.5rem;
}

.card-header h3 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0;
  flex: 1;
}

.process-body {
  margin-top: 1rem;
}

.process-summary {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary-item {
  flex: 1;
  background: #F9FAFB;
  padding: 1rem;
  border-radius: 0.75rem;
  text-align: center;
}

.summary-item.highlight {
  background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
}

.summary-item .label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-light);
  margin-bottom: 0.25rem;
}

.summary-item .value {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-color);
}

.summary-item.highlight .value {
  color: var(--primary-color);
}

.confidence-badge {
  padding: 0.375rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.confidence-badge.high {
  background: #ECFDF5;
  color: #10B981;
}

.confidence-badge.medium {
  background: #FEF3C7;
  color: #F59E0B;
}

.confidence-badge.low {
  background: #FEE2E2;
  color: #EF4444;
}

.answer-content {
  font-size: 1.0625rem;
  line-height: 1.8;
  color: var(--text-color);
  margin-bottom: 1.5rem;
}

/* Markdown Styles */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.markdown-body :deep(h1) { font-size: 1.5rem; }
.markdown-body :deep(h2) { font-size: 1.25rem; }
.markdown-body :deep(h3) { font-size: 1.125rem; }

.markdown-body :deep(p) {
  margin-bottom: 1rem;
}

.markdown-body :deep(ul), 
.markdown-body :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

.markdown-body :deep(li) {
  margin-bottom: 0.5rem;
}

.markdown-body :deep(strong) {
  color: var(--primary-color);
  font-weight: 700;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--primary-color);
  background: #F9FAFB;
  padding: 1rem;
  margin: 1.5rem 0;
  border-radius: 0 0.5rem 0.5rem 0;
  color: var(--text-light);
}

.markdown-body :deep(code) {
  background: #F3F4F6;
  padding: 0.2rem 0.4rem;
  border-radius: 0.25rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 0.875em;
  color: var(--secondary-color);
}

.citations-section {
  border-top: 1px solid var(--border-color);
  padding-top: 1.5rem;
}

.citations-section h4 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

.citation-item {
  background: #F9FAFB;
  border-left: 3px solid var(--primary-color);
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 0.75rem;
}

.citation-header {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.citation-id {
  font-weight: 700;
  color: var(--primary-color);
}

.citation-title {
  color: var(--text-color);
  font-weight: 500;
}

.citation-text {
  font-size: 0.875rem;
  color: var(--text-light);
  margin: 0;
}

.action-buttons {
  display: flex;
  justify-content: center;
  margin-top: 1rem;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
</style>
