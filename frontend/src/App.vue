<template>
  <div id="app">
    <!-- API Key Setup Modal -->
    <div v-if="showApiKeySetup" class="modal-overlay">
      <div class="setup-modal">
        <div class="setup-header">
          <div class="setup-icon">🔐</div>
          <h2>API 키 설정</h2>
          <p>PolicyGraph QA를 사용하려면 OpenAI API 키가 필요합니다.</p>
        </div>
        
        <div class="setup-body">
          <div class="form-group">
            <label>OpenAI API Key</label>
            <div class="input-with-icon">
              <input
                :type="showApiKey ? 'text' : 'password'"
                v-model="apiKeyInput"
                placeholder="sk-..."
                class="api-key-input"
                :disabled="isSettingKey"
              />
              <button @click="showApiKey = !showApiKey" class="toggle-visibility">
                {{ showApiKey ? '🙈' : '👁️' }}
              </button>
            </div>
            <p class="input-hint">
              API 키는 <a href="https://platform.openai.com/api-keys" target="_blank">OpenAI Dashboard</a>에서 발급받을 수 있습니다.
            </p>
          </div>
          
          <div v-if="setupError" class="error-message">
            {{ setupError }}
          </div>
          
          <button 
            @click="submitApiKey" 
            :disabled="!apiKeyInput || isSettingKey"
            class="btn btn-primary btn-full"
          >
            <span v-if="isSettingKey" class="spinner"></span>
            {{ isSettingKey ? '확인 중...' : '설정 완료' }}
          </button>
        </div>
        
        <div class="setup-footer">
          <p>🔒 API 키는 서버에만 저장되며 브라우저에는 저장되지 않습니다.</p>
        </div>
      </div>
    </div>

    <!-- Main App -->
    <template v-if="!showApiKeySetup">
      <header class="navbar">
        <div class="container nav-content">
          <router-link to="/" class="nav-brand">
            <span class="logo-icon">📊</span>
            <div class="brand-text">
              <h1>PolicyGraph QA</h1>
              <p>Intelligent Insurance Analysis</p>
            </div>
          </router-link>
          <nav class="nav-links">
            <router-link to="/" class="nav-link" :class="{ 'active': $route.path === '/' }">홈</router-link>
            <router-link to="/ingestion" class="nav-link" :class="{ 'active': $route.path === '/ingestion' }">PDF 업로드</router-link>
            <router-link to="/query" class="nav-link" :class="{ 'active': $route.path === '/query' }">질의하기</router-link>
          </nav>
          
          <!-- Config Status -->
          <div class="config-status" v-if="configStatus">
            <span class="status-dot" :class="{ 'active': configStatus.configured }"></span>
            <span class="status-text">{{ configStatus.masked_key || 'Not configured' }}</span>
          </div>
        </div>
      </header>

      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

      <footer class="footer">
        <div class="container footer-content">
          <div class="footer-brand">
            <h3>PolicyGraph QA</h3>
            <p>Advanced RAG System for Insurance Policies</p>
          </div>
          <p class="footer-links">
            © 2025 <a href="https://www.uengine.io" target="_blank">uEngine</a>. All rights reserved.
          </p>
        </div>
      </footer>
    </template>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import api from './services/api'

export default {
  name: 'App',
  setup() {
    const showApiKeySetup = ref(false)
    const apiKeyInput = ref('')
    const showApiKey = ref(false)
    const isSettingKey = ref(false)
    const setupError = ref('')
    const configStatus = ref(null)

    const checkApiKeyStatus = async () => {
      try {
        const status = await api.getConfigStatus()
        configStatus.value = status
        showApiKeySetup.value = !status.configured
      } catch (error) {
        console.error('Failed to check config status:', error)
        // If API is not reachable, don't show setup modal
        showApiKeySetup.value = false
      }
    }

    const submitApiKey = async () => {
      if (!apiKeyInput.value.trim()) return
      
      isSettingKey.value = true
      setupError.value = ''
      
      try {
        await api.setApiKey(apiKeyInput.value.trim())
        showApiKeySetup.value = false
        await checkApiKeyStatus()
      } catch (error) {
        setupError.value = error.response?.data?.detail || 'API 키 설정에 실패했습니다.'
      } finally {
        isSettingKey.value = false
      }
    }

    onMounted(() => {
      checkApiKeyStatus()
    })

    return {
      showApiKeySetup,
      apiKeyInput,
      showApiKey,
      isSettingKey,
      setupError,
      configStatus,
      submitApiKey
    }
  }
}
</script>

<style>
:root {
  --primary-color: #312E81;
  --secondary-color: #7C3AED;
  --accent-color: #FBBF24;
  --success-color: #10b981;
  --warning-color: #f59e0b;
  --danger-color: #ef4444;
  --text-color: #1f2937;
  --text-light: #6b7280;
  --bg-color: #F9FAFB;
  --bg-light: #F3F4F6;
  --border-color: #e5e7eb;
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-md: 0 6px 12px -2px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Pretendard Variable', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--text-color);
  background-color: var(--bg-color);
  line-height: 1.6;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

/* Modal Overlay */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, #312E81 0%, #4F46E5 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.setup-modal {
  background: white;
  border-radius: 1.5rem;
  max-width: 480px;
  width: 90%;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.setup-header {
  text-align: center;
  padding: 2.5rem 2rem 1.5rem;
  background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
}

.setup-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.setup-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 0.5rem;
}

.setup-header p {
  color: var(--text-light);
  font-size: 0.9375rem;
}

.setup-body {
  padding: 2rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.5rem;
}

.input-with-icon {
  position: relative;
  display: flex;
}

.api-key-input {
  flex: 1;
  padding: 0.875rem 1rem;
  border: 2px solid var(--border-color);
  border-radius: 0.75rem;
  font-size: 1rem;
  font-family: 'SF Mono', 'Fira Code', monospace;
  transition: all 0.2s ease;
}

.api-key-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.toggle-visibility {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem;
}

.input-hint {
  margin-top: 0.5rem;
  font-size: 0.8125rem;
  color: var(--text-light);
}

.input-hint a {
  color: var(--primary-color);
  text-decoration: none;
}

.input-hint a:hover {
  text-decoration: underline;
}

.error-message {
  background: #FEE2E2;
  color: #DC2626;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.setup-footer {
  padding: 1rem 2rem 1.5rem;
  text-align: center;
}

.setup-footer p {
  font-size: 0.8125rem;
  color: var(--text-light);
}

/* Navbar */
.navbar {
  background: white;
  border-bottom: 1px solid var(--border-color);
  padding: 1rem 0;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}

.nav-content {
  display: flex;
  align-items: center;
  gap: 2rem;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
}

.logo-icon {
  font-size: 1.75rem;
}

.brand-text h1 {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-color);
  line-height: 1.2;
}

.brand-text p {
  font-size: 0.6875rem;
  color: var(--text-light);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.nav-links {
  display: flex;
  gap: 0.25rem;
  flex: 1;
}

.nav-link {
  padding: 0.5rem 1rem;
  text-decoration: none;
  color: var(--text-light);
  font-weight: 500;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
}

.nav-link:hover {
  color: var(--text-color);
  background: var(--bg-light);
}

.nav-link.active {
  color: var(--primary-color);
  background: #EEF2FF;
}

.config-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--bg-light);
  border-radius: 2rem;
  font-size: 0.75rem;
  color: var(--text-light);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger-color);
}

.status-dot.active {
  background: var(--success-color);
}

/* Main Content */
.main-content {
  min-height: calc(100vh - 180px);
}

/* Footer */
.footer {
  background: white;
  border-top: 1px solid var(--border-color);
  padding: 2rem 0;
  margin-top: auto;
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-brand h3 {
  font-size: 1rem;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.footer-brand p {
  font-size: 0.8125rem;
  color: var(--text-light);
}

.footer-links {
  font-size: 0.8125rem;
  color: var(--text-light);
}

.footer-links a {
  color: var(--primary-color);
  text-decoration: none;
}

.footer-links a:hover {
  text-decoration: underline;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-radius: 0.75rem;
  font-weight: 600;
  font-size: 0.9375rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-full {
  width: 100%;
}

/* Spinner */
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Page Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .nav-content {
    flex-wrap: wrap;
  }
  
  .nav-links {
    order: 3;
    width: 100%;
    margin-top: 1rem;
    justify-content: center;
  }
  
  .config-status {
    display: none;
  }
  
  .footer-content {
    flex-direction: column;
    text-align: center;
    gap: 1rem;
  }
}
</style>
