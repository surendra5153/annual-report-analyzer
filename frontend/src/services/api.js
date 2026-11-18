import axios from 'axios'

// In production on separate domains (e.g. Render), set VITE_API_URL to the backend URL.
// With Docker/Railway nginx proxy, leave it unset — relative /api path is used.
const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

const api = axios.create({
  baseURL,
  timeout: 60000,
})

// ── Companies ──────────────────────────────────────────────────────────────
export const getCompanies = () => api.get('/companies/').then(r => r.data)
export const createCompany = (data) => api.post('/companies/', data).then(r => r.data)
export const updateCompany = (id, data) => api.put(`/companies/${id}`, data).then(r => r.data)
export const deleteCompany = (id) => api.delete(`/companies/${id}`)
export const getCompanyPeers = (id) => api.get(`/companies/${id}/peers`).then(r => r.data)

// ── Filings ────────────────────────────────────────────────────────────────
export const getFilings = (companyId) =>
  api.get('/filings/', { params: companyId ? { company_id: companyId } : {} }).then(r => r.data)

/**
 * Send a PDF to the backend for metadata detection.
 * Returns DetectResponse: { is_financial_report, company_name, ticker,
 *   fiscal_year, currency, unit_scale, report_type, confidence, rejection_reason }
 */
export const detectFiling = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/filings/detect', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const uploadFiling = (formData) =>
  api.post('/filings/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)

export const getFiling = (id) => api.get(`/filings/${id}`).then(r => r.data)
export const deleteFiling = (id) => api.delete(`/filings/${id}`)

export const getKPIs = (filingId, verifiedOnly = false) =>
  api.get(`/filings/${filingId}/kpis`, { params: { verified_only: verifiedOnly } }).then(r => r.data)

export const getRisks = (filingId) =>
  api.get(`/filings/${filingId}/risks`).then(r => r.data)

export const getFlags = (filingId) =>
  api.get(`/filings/${filingId}/flags`).then(r => r.data)

export const getSections = (filingId) =>
  api.get(`/filings/${filingId}/sections`).then(r => r.data)

export const getDashboard = (filingId) =>
  api.get(`/filings/${filingId}/dashboard`).then(r => r.data)

export const getPromises = (filingId) =>
  api.get(`/filings/${filingId}/promises`).then(r => r.data)

// ── Jobs ───────────────────────────────────────────────────────────────────
export const getJob = (jobId) => api.get(`/jobs/${jobId}`).then(r => r.data)
export const getJobByFiling = (filingId) =>
  api.get(`/jobs/by-filing/${filingId}`).then(r => r.data)

// ── Companies (extended) ───────────────────────────────────────────────────
export const getCompanyProfile = (companyId) =>
  api.get(`/companies/${companyId}/profile`).then(r => r.data)

// ── Q&A ────────────────────────────────────────────────────────────────────
export const askQuestion = (question, filingIds, conversationHistory = null) =>
  api.post('/qa/', {
    question,
    filing_ids: filingIds,
    ...(conversationHistory ? { conversation_history: conversationHistory } : {}),
  }).then(r => r.data)

/**
 * Streaming Q&A over Server-Sent Events (POST, so fetch + ReadableStream).
 * Calls onEvent for each event: {type:'sources'|'token'|'done'|'error', ...}.
 * Returns an AbortController-compatible abort function.
 */
export function streamQuestion({ question, filingIds, conversationHistory, onEvent }) {
  const controller = new AbortController()
  ;(async () => {
    try {
      const res = await fetch(`${baseURL}/qa/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          filing_ids: filingIds,
          ...(conversationHistory?.length ? { conversation_history: conversationHistory } : {}),
        }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        onEvent({ type: 'error', message: body.detail || `HTTP ${res.status}` })
        return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop()
        for (const e of events) {
          const line = e.trim()
          if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)))
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') onEvent({ type: 'error', message: err.message })
    }
  })()
  return () => controller.abort()
}

// ── PDF ────────────────────────────────────────────────────────────────────
export const filingPdfUrl = (filingId) => `${baseURL}/filings/${filingId}/pdf`

// ── ML / Model Lab ─────────────────────────────────────────────────────────
export const getMlHealth = () => api.get('/ml/health').then(r => r.data)
export const getMlMetrics = () => api.get('/ml/metrics').then(r => r.data)
export const getMlEda = () => api.get('/ml/eda').then(r => r.data)
export const getMlPreprocessing = () => api.get('/ml/preprocessing').then(r => r.data)
export const mlFigureUrl = (name) => `${baseURL}/ml/figures/${name}`

// ── Comparison ─────────────────────────────────────────────────────────────
export const compareFilings = (filingIds, kpiNames) =>
  api.post('/comparison/', { filing_ids: filingIds, kpi_names: kpiNames }).then(r => r.data)

// ── Helpers ────────────────────────────────────────────────────────────────
/**
 * Look up a company by ticker; create it if it doesn't exist yet.
 * Returns the company object (with id).
 */
export const getOrCreateCompany = async ({ ticker, name, sector }) => {
  const list = await getCompanies()
  const existing = list.find(c => c.ticker?.toUpperCase() === ticker?.toUpperCase())
  if (existing) return existing
  return createCompany({ ticker, name, sector, exchange: 'NSE' })
}
