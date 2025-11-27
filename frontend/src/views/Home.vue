<template>
  <div class="home">
    <!-- Hero Section -->
    <div class="hero-section">
      <div class="container">
        <div class="hero-content">
          <span class="badge badge-accent mb-4">New Generation AI</span>
          <h1>보험약관 분석의<br>새로운 기준</h1>
          <p class="subtitle">
            GraphRAG 기술을 활용하여 복잡한 보험약관을<br>
            계층적으로 분석하고 정확한 답변을 제공합니다.
          </p>
          <div class="hero-actions">
            <router-link to="/query" class="btn btn-primary btn-lg">
              지금 시작하기
              <span class="arrow">→</span>
            </router-link>
            <router-link to="/ingestion" class="btn btn-outline btn-lg">
              PDF 업로드
            </router-link>
          </div>
        </div>
        <div class="hero-visual">
          <div class="visual-circle"></div>
          <div class="visual-card glass">
            <div class="visual-icon">🔍</div>
            <div class="visual-text">
              <strong>Smart Analysis</strong>
              <span>Context-aware Retrieval</span>
            </div>
          </div>
          <div class="visual-card glass delay-1">
            <div class="visual-icon">🕸️</div>
            <div class="visual-text">
              <strong>Graph Structure</strong>
              <span>Hierarchical Knowledge</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Features Section -->
    <div class="features-section">
      <div class="container">
        <div class="section-header">
          <h2>Key Features</h2>
          <p>강력한 기능으로 보험약관 분석을 혁신합니다</p>
        </div>
        
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon-wrapper">
              <span class="feature-icon">📄</span>
            </div>
            <h3>PDF 자동 분석</h3>
            <p>복잡한 보험약관 PDF를 자동으로 파싱하여 구조화된 데이터로 변환합니다. 조, 항, 호 단위로 정밀하게 분석합니다.</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon-wrapper">
              <span class="feature-icon">🧠</span>
            </div>
            <h3>문맥 인식 질의</h3>
            <p>단순 키워드 매칭이 아닌, 문맥을 이해하는 AI가 여러 조항을 참조하여 정확하고 논리적인 답변을 생성합니다.</p>
          </div>

          <div class="feature-card">
            <div class="feature-icon-wrapper">
              <span class="feature-icon">🌲</span>
            </div>
            <h3>추론 과정 시각화</h3>
            <p>AI가 어떤 조항들을 참조하고 어떻게 결론을 도출했는지 트리 구조로 투명하게 보여줍니다.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats Section -->
    <div class="stats-section">
      <div class="container">
        <div class="stats-card">
          <div class="stat-item">
            <div class="stat-value status-ok">{{ systemStatus }}</div>
            <div class="stat-label">System Status</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-value">GraphRAG</div>
            <div class="stat-label">Engine Type</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-value">Neo4j</div>
            <div class="stat-label">Knowledge Graph</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from '../services/api'

export default {
  name: 'Home',
  setup() {
    const systemStatus = ref('Checking...')

    onMounted(async () => {
      try {
        const health = await api.healthCheck()
        systemStatus.value = health.engine_status === 'ready' ? 'Operational' : 'Standby'
      } catch (error) {
        systemStatus.value = 'Offline'
      }
    })

    return {
      systemStatus
    }
  }
}
</script>

<style scoped>
.home {
  background-color: #F8FAFC;
}

/* Hero Section */
.hero-section {
  background: radial-gradient(circle at top right, #1e1b4b, #312e81);
  color: white;
  padding: 6rem 0 8rem;
  position: relative;
  overflow: hidden;
}

.hero-section::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
}

.hero-content {
  position: relative;
  z-index: 10;
  max-width: 600px;
}

.badge-accent {
  background: rgba(192, 132, 252, 0.2);
  color: #E9D5FF;
  border: 1px solid rgba(192, 132, 252, 0.3);
  padding: 0.5rem 1rem;
  border-radius: 2rem;
  font-size: 0.875rem;
  font-weight: 600;
  display: inline-block;
  margin-bottom: 1.5rem;
}

.hero-content h1 {
  font-size: 3.5rem;
  font-weight: 800;
  line-height: 1.1;
  margin-bottom: 1.5rem;
  letter-spacing: -0.02em;
  background: linear-gradient(to right, #ffffff, #e0e7ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  font-size: 1.25rem;
  color: #cbd5e1;
  line-height: 1.6;
  margin-bottom: 2.5rem;
}

.hero-actions {
  display: flex;
  gap: 1rem;
}

.btn-lg {
  padding: 1rem 2rem;
  font-size: 1.125rem;
}

.btn-outline {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
}

.btn-outline:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: white;
}

.hero-visual {
  position: absolute;
  right: 5%;
  top: 50%;
  transform: translateY(-50%);
  width: 500px;
  height: 500px;
  display: none; /* Hide on mobile */
}

@media (min-width: 1024px) {
  .hero-visual {
    display: block;
  }
}

.visual-circle {
  position: absolute;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(79, 70, 229, 0.4) 0%, rgba(49, 46, 129, 0) 70%);
  border-radius: 50%;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  filter: blur(40px);
}

.visual-card {
  position: absolute;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 1.25rem;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  width: 240px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2);
  animation: float 6s ease-in-out infinite;
}

.visual-card:first-of-type {
  top: 20%;
  right: 10%;
}

.visual-card.delay-1 {
  bottom: 30%;
  left: 10%;
  animation-delay: 3s;
}

.visual-icon {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
}

.visual-text {
  display: flex;
  flex-direction: column;
}

.visual-text strong {
  font-size: 0.9375rem;
  color: white;
}

.visual-text span {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.7);
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}

/* Features Section */
.features-section {
  padding: 6rem 0;
  position: relative;
  top: -4rem; /* Pull up to overlap hero */
}

.section-header {
  text-align: center;
  margin-bottom: 4rem;
}

.section-header h2 {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 0.5rem;
}

.section-header p {
  color: var(--text-light);
  font-size: 1.125rem;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
}

.feature-card {
  background: white;
  padding: 2.5rem;
  border-radius: 1rem;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(0,0,0,0.02);
  transition: all 0.3s ease;
}

.feature-card:hover {
  transform: translateY(-10px);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.feature-icon-wrapper {
  width: 64px;
  height: 64px;
  background: var(--bg-light);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.feature-icon {
  font-size: 2rem;
}

.feature-card h3 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 1rem;
}

.feature-card p {
  color: var(--text-light);
  line-height: 1.6;
}

/* Stats Section */
.stats-section {
  padding-bottom: 4rem;
}

.stats-card {
  background: white;
  border-radius: 1rem;
  padding: 3rem;
  box-shadow: var(--shadow-md);
  display: flex;
  justify-content: space-around;
  align-items: center;
  border: 1px solid var(--border-color);
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--text-color);
  margin-bottom: 0.5rem;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-value.status-ok {
  color: var(--success-color);
  -webkit-text-fill-color: initial;
}

.stat-label {
  color: var(--text-light);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.875rem;
}

.stat-divider {
  width: 1px;
  height: 60px;
  background: var(--border-color);
}

@media (max-width: 768px) {
  .hero-content h1 {
    font-size: 2.5rem;
  }
  
  .stats-card {
    flex-direction: column;
    gap: 2rem;
  }
  
  .stat-divider {
    width: 100%;
    height: 1px;
  }
}
</style>
