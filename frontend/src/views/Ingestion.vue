<template>
  <div class="ingestion-page">
    <div class="page-header">
      <div class="container">
        <h1 class="page-title">Document Ingestion</h1>
        <p class="page-subtitle">보험약관 PDF를 업로드하여 지식 그래프를 구축합니다.</p>
      </div>
    </div>

    <div class="container content-container">
      <div class="steps-grid">
        <!-- Step 1: Upload -->
        <div class="step-card" :class="{ active: currentStep === 1, completed: currentStep > 1 }">
          <div class="step-header">
            <div class="step-number">1</div>
            <h3>PDF 업로드</h3>
          </div>
          
          <div class="upload-area" 
               :class="{ 'has-file': selectedFile }"
               @click="triggerFileInput" 
               @drop.prevent="handleDrop" 
               @dragover.prevent>
            <input
              type="file"
              ref="fileInput"
              accept=".pdf"
              @change="handleFileSelect"
              style="display: none"
            />
            
            <div v-if="!selectedFile" class="upload-placeholder">
              <div class="upload-icon-circle">
                <span class="upload-icon">📄</span>
              </div>
              <p class="upload-text">클릭하거나 파일을 드래그하세요</p>
              <p class="upload-hint">PDF 파일만 지원 (최대 50MB)</p>
            </div>

            <div v-else class="file-preview">
              <div class="file-icon">📑</div>
              <div class="file-details">
                <div class="file-name">{{ selectedFile.name }}</div>
                <div class="file-meta">{{ formatFileSize(selectedFile.size) }}</div>
              </div>
              <button @click.stop="clearFile" class="btn-icon-remove">✕</button>
            </div>
          </div>

          <button
            v-if="selectedFile && !uploadedFileId"
            @click="uploadFile"
            :disabled="uploading"
            class="btn btn-primary btn-full"
          >
            <span v-if="uploading" class="spinner mr-2"></span>
            {{ uploading ? '업로드 중...' : '파일 업로드' }}
          </button>
        </div>

        <!-- Step 2: Configure -->
        <div class="step-card" :class="{ active: currentStep === 2, completed: currentStep > 2, disabled: currentStep < 2 }">
          <div class="step-header">
            <div class="step-number">2</div>
            <h3>메타데이터 설정</h3>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label>상품 코드</label>
              <input
                v-model="ingestionConfig.product_code"
                type="text"
                class="input"
                placeholder="예: LIG_2007_PI"
                :disabled="currentStep !== 2"
              />
            </div>

            <div class="form-group">
              <label>상품명</label>
              <input
                v-model="ingestionConfig.product_name"
                type="text"
                class="input"
                placeholder="예: LIG 개인상해보험"
                :disabled="currentStep !== 2"
              />
            </div>

            <div class="form-group">
              <label>버전 ID</label>
              <input
                v-model="ingestionConfig.version_id"
                type="text"
                class="input"
                placeholder="예: V1.0"
                :disabled="currentStep !== 2"
              />
            </div>
            
            <div class="form-group">
              <label>최대 조항 수 <span class="badge badge-warning">Test</span></label>
              <input
                v-model.number="ingestionConfig.max_clauses"
                type="number"
                class="input"
                placeholder="전체 처리 시 비워두세요"
                :disabled="currentStep !== 2"
              />
            </div>
          </div>

          <button
            v-if="currentStep === 2"
            @click="startIngestion"
            :disabled="!canStartIngestion || ingesting"
            class="btn btn-primary btn-full mt-4"
          >
            <span v-if="ingesting" class="spinner mr-2"></span>
            {{ ingesting ? '시작 중...' : 'Ingestion 시작' }}
          </button>
        </div>

        <!-- Step 3: Processing -->
        <div class="step-card full-width" v-if="jobId">
          <div class="step-header">
            <div class="step-number">3</div>
            <h3>처리 진행상황</h3>
            <span class="badge ml-auto" :class="'badge-' + getStatusType(jobStatus)">
              {{ getStatusText(jobStatus) }}
            </span>
          </div>

          <div class="progress-wrapper">
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" :style="{ width: (jobProgress?.percent || 0) + '%' }"></div>
            </div>
            <div class="progress-info">
              <span class="progress-stage">{{ jobProgress?.stage || '준비 중...' }}</span>
              <span class="progress-percent">{{ jobProgress?.percent || 0 }}%</span>
            </div>
          </div>

          <div v-if="jobError" class="alert alert-error mt-4">
            <div class="alert-icon">⚠️</div>
            <div class="alert-content">{{ jobError }}</div>
          </div>

          <div v-if="jobStatus === 'completed'" class="success-action">
            <div class="alert alert-success">
              <div class="alert-icon">✅</div>
              <div class="alert-content">Ingestion이 성공적으로 완료되었습니다.</div>
            </div>
            <router-link to="/query" class="btn btn-primary">
              질의하기로 이동 →
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'

export default {
  name: 'Ingestion',
  setup() {
    const router = useRouter()
    const fileInput = ref(null)
    const selectedFile = ref(null)
    const uploading = ref(false)
    const uploadedFileId = ref(null)
    const currentStep = ref(1)
    
    const ingestionConfig = ref({
      product_code: '',
      product_name: '',
      version_id: '',
      max_clauses: null
    })
    
    const ingesting = ref(false)
    const jobId = ref(null)
    const jobStatus = ref(null)
    const jobProgress = ref(null)
    const jobError = ref(null)
    
    let statusCheckInterval = null

    const canStartIngestion = computed(() => {
      return (
        ingestionConfig.value.product_code &&
        ingestionConfig.value.product_name &&
        ingestionConfig.value.version_id
      )
    })

    watch(uploadedFileId, (newVal) => {
      if (newVal) currentStep.value = 2
    })

    watch(jobId, (newVal) => {
      if (newVal) currentStep.value = 3
    })

    const triggerFileInput = () => fileInput.value.click()

    const handleFileSelect = (event) => {
      const file = event.target.files[0]
      if (file && file.type === 'application/pdf') {
        selectedFile.value = file
      } else {
        alert('PDF 파일만 업로드할 수 있습니다.')
      }
    }

    const handleDrop = (event) => {
      const file = event.dataTransfer.files[0]
      if (file && file.type === 'application/pdf') {
        selectedFile.value = file
      } else {
        alert('PDF 파일만 업로드할 수 있습니다.')
      }
    }

    const clearFile = () => {
      selectedFile.value = null
      uploadedFileId.value = null
      currentStep.value = 1
      if (fileInput.value) fileInput.value.value = ''
    }

    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    }

    const uploadFile = async () => {
      if (!selectedFile.value) return
      uploading.value = true
      try {
        const result = await api.uploadPDF(selectedFile.value)
        uploadedFileId.value = result.file_id
      } catch (error) {
        alert('파일 업로드 실패: ' + error.message)
      } finally {
        uploading.value = false
      }
    }

    const startIngestion = async () => {
      if (!canStartIngestion.value) return
      ingesting.value = true
      try {
        const result = await api.startIngestion(uploadedFileId.value, ingestionConfig.value)
        jobId.value = result.job_id
        jobStatus.value = result.status
        statusCheckInterval = setInterval(checkStatus, 2000)
      } catch (error) {
        alert('Ingestion 시작 실패: ' + error.message)
        ingesting.value = false
      }
    }

    const checkStatus = async () => {
      if (!jobId.value) return
      try {
        const status = await api.getIngestionStatus(jobId.value)
        jobStatus.value = status.status
        jobProgress.value = status.progress
        jobError.value = status.error

        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(statusCheckInterval)
          ingesting.value = false
        }
      } catch (error) {
        console.error('Status check failed:', error)
      }
    }

    const getStatusText = (status) => {
      const statusMap = {
        pending: '대기 중',
        processing: '처리 중',
        completed: '완료됨',
        failed: '실패함'
      }
      return statusMap[status] || status
    }

    const getStatusType = (status) => {
      const map = {
        pending: 'warning',
        processing: 'info',
        completed: 'success',
        failed: 'error'
      }
      return map[status] || 'info'
    }

    return {
      fileInput, selectedFile, uploading, uploadedFileId, ingestionConfig, ingesting,
      jobId, jobStatus, jobProgress, jobError, currentStep, canStartIngestion,
      triggerFileInput, handleFileSelect, handleDrop, clearFile, formatFileSize,
      uploadFile, startIngestion, getStatusText, getStatusType
    }
  }
}
</script>

<style scoped>
.ingestion-page {
  min-height: 100vh;
  background-color: #F8FAFC;
  padding-bottom: 4rem;
}

.page-header {
  background: white;
  border-bottom: 1px solid var(--border-color);
  padding: 3rem 0;
  margin-bottom: 3rem;
}

.page-title {
  font-size: 2rem;
  font-weight: 800;
  color: var(--text-color);
  margin-bottom: 0.5rem;
}

.page-subtitle {
  color: var(--text-light);
  font-size: 1.125rem;
}

.content-container {
  max-width: 1000px;
}

.steps-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
}

.step-card {
  background: white;
  border-radius: 1rem;
  padding: 2rem;
  box-shadow: var(--shadow);
  border: 1px solid transparent;
  transition: all 0.3s ease;
}

.step-card.active {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md);
}

.step-card.disabled {
  opacity: 0.6;
  pointer-events: none;
  filter: grayscale(0.5);
}

.step-card.full-width {
  grid-column: 1 / -1;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.step-number {
  width: 2.5rem;
  height: 2.5rem;
  background: var(--bg-light);
  color: var(--text-light);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.125rem;
  transition: all 0.3s ease;
}

.active .step-number {
  background: var(--primary-color);
  color: white;
}

.completed .step-number {
  background: var(--success-color);
  color: white;
}

.step-header h3 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-color);
  margin: 0;
}

.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: 1rem;
  padding: 2.5rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: var(--bg-light);
}

.upload-area:hover, .upload-area.has-file {
  border-color: var(--primary-color);
  background-color: rgba(79, 70, 229, 0.02);
}

.upload-icon-circle {
  width: 4rem;
  height: 4rem;
  background: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1rem;
  box-shadow: var(--shadow-sm);
}

.upload-icon {
  font-size: 2rem;
}

.upload-text {
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.upload-hint {
  font-size: 0.875rem;
  color: var(--text-light);
}

.file-preview {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: white;
  padding: 1rem;
  border-radius: 0.75rem;
  box-shadow: var(--shadow-sm);
}

.file-icon {
  font-size: 2rem;
}

.file-details {
  flex: 1;
  text-align: left;
}

.file-name {
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.file-meta {
  font-size: 0.75rem;
  color: var(--text-light);
}

.btn-icon-remove {
  background: transparent;
  border: none;
  color: var(--text-light);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 50%;
  transition: all 0.2s;
}

.btn-icon-remove:hover {
  background: var(--bg-light);
  color: var(--danger-color);
}

.btn-full {
  width: 100%;
  margin-top: 1.5rem;
}

.form-grid {
  display: grid;
  gap: 1.5rem;
}

.form-group label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.5rem;
}

.progress-wrapper {
  margin-top: 1rem;
}

.progress-bar-bg {
  height: 0.75rem;
  background: var(--bg-light);
  border-radius: 1rem;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  border-radius: 1rem;
  transition: width 0.5s ease;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-color);
}

.progress-percent {
  color: var(--primary-color);
  font-weight: 700;
}

.success-action {
  margin-top: 2rem;
  text-align: center;
}

.mr-2 { margin-right: 0.5rem; }
.ml-auto { margin-left: auto; }
.mt-4 { margin-top: 1rem; }

@media (max-width: 768px) {
  .steps-grid {
    grid-template-columns: 1fr;
  }
}
</style>
