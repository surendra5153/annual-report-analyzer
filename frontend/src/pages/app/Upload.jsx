import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { AnimatePresence, motion } from 'framer-motion'
import { toast } from 'sonner'
import { AlertCircle, ArrowRight, Check, FileText, Loader2, Lock, ScanSearch, UploadCloud, X } from 'lucide-react'
import NSE_COMPANIES from '@/data/nse_companies.json'
import { detectFiling, getCompanies, getFilings, getOrCreateCompany, uploadFiling } from '@/services/api'
import { PageBody, PageHeader } from '@/components/app/AppShell'
import CompanyPicker from '@/components/app/CompanyPicker'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input, Label, Select } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const STEPS = ['Select PDF', 'Review details', 'Analyse']
const CONF = { high: 'success', medium: 'warning', low: 'danger' }

function Steps({ current }) {
  return (
    <ol className="flex items-center gap-2">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span className={cn('grid size-6 place-items-center rounded-full border text-[11px] font-medium',
            i < current && 'border-primary bg-primary text-primary-foreground', i === current && 'border-primary text-primary')}>
            {i < current ? <Check className="size-3.5" /> : i + 1}
          </span>
          <span className={cn('text-[13px] text-muted-foreground', i === current && 'font-medium text-foreground')}>{s}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-8 bg-border" />}
        </li>
      ))}
    </ol>
  )
}

export default function Upload() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [file, setFile] = useState(null)
  const [detecting, setDetecting] = useState(false)
  const [detected, setDetected] = useState(null)
  const [error, setError] = useState(null)
  const [company, setCompany] = useState(null)
  const [freeName, setFreeName] = useState('')
  const [year, setYear] = useState('')
  const [currency, setCurrency] = useState('INR')
  const [unit, setUnit] = useState('crores')

  const reset = () => { setFile(null); setDetected(null); setError(null); setCompany(null); setFreeName(''); setYear('') }

  // Detected values (or filename hints) pre-fill the review form
  const applyDetected = (r, f) => {
    const fy = r.fiscal_year || f.name.match(/FY\s*-?\s*(?:20)?(\d{2})(?!\d)/i)?.[1]
    if (fy) setYear(String(fy).length === 2 ? `20${fy}` : fy)
    if (r.currency) setCurrency(r.currency)
    if (r.unit_scale) setUnit(r.unit_scale)
    const match = r.ticker && NSE_COMPANIES.find((c) => c.ticker.toUpperCase() === r.ticker.toUpperCase())
    if (match) setCompany(match)
    else if (r.company_name) setFreeName(r.company_name)
  }

  const onDrop = useCallback(async ([f]) => {
    if (!f) return
    reset()
    setFile(f)
    setDetecting(true)
    try {
      const r = await detectFiling(f)
      setDetected(r)
      if (!r.is_financial_report) { setError(r.rejection_reason || 'This does not look like an annual report.'); return }
      applyDetected(r, f)
    } catch {
      toast.error('Auto-detection failed — please fill in the details')
      setYear(new Date().getFullYear() - 1)
    } finally {
      setDetecting(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'application/pdf': ['.pdf'] }, maxFiles: 1, disabled: detecting,
  })

  // Warn when this company already has a report for the same year
  const { data: existing = [] } = useQuery({
    queryKey: ['existing', company?.ticker],
    enabled: !!company?.ticker,
    queryFn: async () => {
      const m = (await getCompanies()).find((c) => c.ticker?.toUpperCase() === company.ticker.toUpperCase())
      return m ? getFilings(m.id) : []
    },
  })
  const duplicate = existing.find((f) => String(f.fiscal_year) === String(year))

  const upload = useMutation({
    mutationFn: async () => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('fiscal_year', year)
      fd.append('currency', currency)
      fd.append('unit_scale', unit)
      if (company) {
        const c = await getOrCreateCompany({ ticker: company.ticker, name: company.name, sector: company.sector })
        fd.append('company_id', c.id)
      } else {
        fd.append('company_name', freeName || detected?.company_name || 'Unknown company')
        if (detected?.ticker) fd.append('ticker', detected.ticker)
      }
      return uploadFiling(fd)
    },
    onSuccess: (f) => {
      qc.invalidateQueries({ queryKey: ['filings-all'] })
      qc.invalidateQueries({ queryKey: ['companies'] })
      toast.success('Upload complete — analysis started')
      navigate(`/app/filings/${f.id}`)
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Upload failed'),
  })

  const step = !file || error ? 0 : upload.isPending ? 2 : 1
  const canSubmit = file && !detecting && !error && year && (company || freeName || detected?.company_name)

  return (
    <PageBody className="max-w-3xl">
      <PageHeader title="Upload annual report" description="PDFs are parsed, indexed and analysed locally — nothing leaves your machine." />
      <Steps current={step} />

      <AnimatePresence mode="wait">
        {!file || error ? (
          <motion.div key="drop" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div
              {...getRootProps()}
              className={cn(
                'group relative cursor-pointer overflow-hidden rounded-xl border-2 border-dashed bg-background px-6 py-16 text-center transition-colors',
                isDragActive ? 'border-primary bg-primary/5' : 'hover:border-primary/50 hover:bg-accent/30'
              )}
            >
              <input {...getInputProps()} />
              <div className="mx-auto grid size-14 place-items-center rounded-2xl border bg-card shadow-card transition-transform group-hover:-translate-y-1">
                <UploadCloud className="size-6 text-primary" />
              </div>
              <p className="mt-4 text-[15px] font-medium">{isDragActive ? 'Drop the PDF here' : 'Drag & drop an annual report PDF'}</p>
              <p className="mt-1 text-[13px] text-muted-foreground">or click to browse · up to 100 MB</p>
              <p className="mt-6 inline-flex items-center gap-1.5 text-[12px] text-muted-foreground"><Lock className="size-3.5" /> Processed on-device</p>
            </div>
            {error && (
              <div className="mt-4 flex items-start gap-3 rounded-lg border border-danger/30 bg-danger/5 p-4 text-[13px]">
                <AlertCircle className="mt-0.5 size-4 shrink-0 text-danger" />
                <div className="flex-1">
                  <p className="font-medium text-danger">Not accepted: {file?.name}</p>
                  <p className="mt-0.5 text-muted-foreground">{error}</p>
                </div>
                <Button variant="outline" size="sm" className="shrink-0"
                  onClick={() => { applyDetected(detected || {}, file); setError(null) }}>
                  Upload anyway
                </Button>
              </div>
            )}
          </motion.div>
        ) : (
          <motion.div key="review" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <Card className="flex items-center gap-3 p-4">
              <div className="grid size-10 place-items-center rounded-lg bg-danger/10 text-danger"><FileText className="size-5" /></div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{file.name}</p>
                <p className="text-[12px] text-muted-foreground">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
              </div>
              {detecting ? (
                <Badge variant="default"><Loader2 className="animate-spin" /> Detecting…</Badge>
              ) : detected?.confidence && (
                <Badge variant={CONF[detected.confidence]}><ScanSearch /> {detected.confidence} confidence</Badge>
              )}
              <Button variant="ghost" size="icon-sm" onClick={reset} aria-label="Remove file"><X /></Button>
            </Card>

            <Card className="p-5">
              {detecting ? (
                <div className="space-y-3 py-6 text-center">
                  <Loader2 className="mx-auto size-6 animate-spin text-primary" />
                  <p className="text-[13px] text-muted-foreground">Reading the first pages with the local model to detect company, year and units…</p>
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5 sm:col-span-2">
                    <Label>Company</Label>
                    <CompanyPicker value={company} onChange={setCompany} />
                    {!company && (
                      <Input value={freeName} onChange={(e) => setFreeName(e.target.value)} placeholder="…or type the company name" className="mt-2" />
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <Label>Fiscal year</Label>
                    <Input type="number" value={year} onChange={(e) => setYear(e.target.value)} placeholder="2025" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>Currency</Label>
                      <Select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                        {['INR', 'USD', 'EUR', 'GBP'].map((c) => <option key={c}>{c}</option>)}
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Unit</Label>
                      <Select value={unit} onChange={(e) => setUnit(e.target.value)}>
                        {['crores', 'lakhs', 'millions', 'billions', 'thousands'].map((u) => <option key={u}>{u}</option>)}
                      </Select>
                    </div>
                  </div>
                  {duplicate && (
                    <p className="flex items-center gap-2 rounded-md bg-warning/10 px-3 py-2 text-[12.5px] text-warning sm:col-span-2">
                      <AlertCircle className="size-4" /> A FY{year} report for this company already exists — uploading will add another.
                    </p>
                  )}
                </div>
              )}
            </Card>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={reset}>Cancel</Button>
              <Button disabled={!canSubmit || upload.isPending} onClick={() => upload.mutate()}>
                {upload.isPending ? <><Loader2 className="animate-spin" /> Uploading…</> : <>Start analysis <ArrowRight /></>}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </PageBody>
  )
}
