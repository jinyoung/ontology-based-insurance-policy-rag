import axios from 'axios'

const API_BASE_URL = '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export default {
  // Health check
  async healthCheck() {
    const response = await api.get('/health')
    return response.data
  },

  // Upload PDF
  async uploadPDF(file) {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await axios.post('/api/v1/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response.data
  },

  // Check existing nodes in graph
  async checkExistingNodes() {
    const response = await api.get('/graph/check-existing')
    return response.data
  },

  // Clear all nodes from graph
  async clearGraph() {
    const response = await api.delete('/graph/clear')
    return response.data
  },

  // Start ingestion
  async startIngestion(fileId, ingestionData) {
    const response = await api.post(`/ingestion/start?file_id=${fileId}`, ingestionData)
    return response.data
  },

  // Get ingestion status
  async getIngestionStatus(jobId) {
    const response = await api.get(`/ingestion/status/${jobId}`)
    return response.data
  },

  // Get recommended queries
  async getRecommendedQueries() {
    const response = await api.get('/recommended-queries')
    return response.data
  },

  // Query with detailed process
  async queryDetailed(question, includeProcess = true) {
    const response = await api.post('/query/detailed', {
      question,
      include_process: includeProcess
    })
    return response.data
  },

  // Simple query
  async query(question) {
    const response = await api.post('/query', {
      question
    })
    return response.data
  }
}

