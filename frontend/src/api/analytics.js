import axios from 'axios'

const client = axios.create({ timeout: 120000 })

const unwrap = (r) => r.data?.data

export const analyticsApi = {
  health: () => client.get('/api/analytics/health').then(unwrap),
  runs: () => client.get('/api/analytics/runs').then(unwrap),
  overview: (simId) => client.get(`/api/analytics/overview/${simId}`).then(unwrap),
  sentiment: (simId) => client.get(`/api/analytics/sentiment/${simId}`).then(unwrap),
  network: (simId) => client.get(`/api/analytics/network/${simId}`).then(unwrap),
  personas: (simId) => client.get(`/api/analytics/personas/${simId}`).then(unwrap),
  confidence: (simId) => client.get(`/api/analytics/confidence/${simId}`).then(unwrap),
  runPipeline: (simId, force = false) =>
    client.post(`/api/analytics/run/${simId}${force ? '?force=1' : ''}`).then(unwrap),
  demo: () => client.get('/api/analytics/demo').then(unwrap),
}

export default analyticsApi
