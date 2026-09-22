import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { UploadCloud, FileText, Loader2, CheckCircle2, AlertCircle, Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import toast from 'react-hot-toast'
import { detectFiling, uploadFiling, getFilings, getCompanies, getOrCreateCompany } from '../services/api'
import { StatusBadge } from '../components/StatusBadge'
import CompanySearch from '../components/CompanySearch'
import NSE_COMPANIES from '../data/nse_companies.json'

const CURRENCIES = ['INR','USD','EUR','GBP','JPY','CNY']
const UNITS = ['crores','lakhs','millions','billions','units']

const L = ({ children }) => (
  <label style={{ display:'block',fontSize:10,fontWeight:700,color:'#64748B',textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:6 }}>{children}</label>
)

export default function Upload() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [file, setFile] = useState(null)
  const [detecting, setDetecting] = useState(false)
  const [detected, setDetected] = useState(null)
  const [detectError, setDetectError] = useState(null)
  const [selComp, setSelComp] = useState(null)
  const [nameFree, setNameFree] = useState('')
  const [year, setYear] = useState('')
  const [currency, setCurrency] = useState('INR')
  const [unit, setUnit] = useState('crores')
  const [showOverride, setShowOverride] = useState(false)

  const { data: existingFilings=[] } = useQuery({
    queryKey: ['filings-by-ticker', selComp?.ticker],
    queryFn: async () => {
      if (!selComp?.ticker) return []
      const all = await getCompanies()
      const m = all.find(c=>c.ticker?.toUpperCase()===selComp.ticker.toUpperCase())
      if (!m) return []
      return getFilings(m.id)
    },
    enabled: !!selComp?.ticker,
  })

  const onDrop = useCallback(async (accepted) => {
    const f=accepted[0]; if(!f) return
    setFile(f); setDetected(null); setDetectError(null); setDetecting(true)
    try {
      const r = await detectFiling(f); setDetected(r)
      if (!r.is_financial_report) { setDetectError(r.rejection_reason||'Not a financial report.'); setFile(null); return }
      if (r.fiscal_year) setYear(r.fiscal_year)
      if (r.currency)    setCurrency(r.currency)
      if (r.unit_scale)  setUnit(r.unit_scale)
      if (r.ticker) { const m=NSE_COMPANIES.find(c=>c.ticker.toUpperCase()===r.ticker.toUpperCase()); if(m){setSelComp(m);return} }
      if (r.company_name) setNameFree(r.company_name)
    } catch { toast.error('Auto-detect failed — fill in manually'); setYear(new Date().getFullYear()-1) }
    finally { setDetecting(false) }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept:{'application/pdf':['.pdf']}, maxFiles:1, disabled:detecting })

  const uploadMut = useMutation({
    mutationFn: async () => {
      const fd=new FormData(); fd.append('file',file); fd.append('fiscal_year',year); fd.append('currency',currency); fd.append('unit_scale',unit)
      if (selComp) {
        const c=await getOrCreateCompany({ticker:selComp.ticker,name:selComp.name,sector:selComp.sector})
        qc.invalidateQueries(['companies']); fd.append('company_id',c.id)
      } else {
        fd.append('company_name',nameFree||detected?.company_name||'Unknown')
        if(detected?.ticker) fd.append('ticker',detected.ticker)
      }
      return uploadFiling(fd)
    },
    onSuccess: d => { qc.invalidateQueries(['filings']); toast.success('Processing started'); navigate(`/filings/${d.id}`) },
    onError: e => toast.error(e.response?.data?.detail||'Upload failed'),
  })

  const canSubmit = file && !detecting && !detectError && year

  return (
    <div style={{ 
      position: 'relative', 
      minHeight: '100vh', 
      background: '#08090C', 
      overflow: 'hidden' 
    }}>
      {/* ── 3D Grid Background ── */}
      <div 
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px)',
          backgroundSize: '4rem 4rem',
          maskImage: 'radial-gradient(ellipse 60% 50% at 50% 0%, #000 70%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 60% 50% at 50% 0%, #000 70%, transparent 100%)',
          pointerEvents: 'none'
        }}
      />

      {/* ── Top Glow Effect ── */}
      <div 
        style={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '800px',
          height: '500px',
          background: 'rgba(255, 85, 0, 0.1)',
          filter: 'blur(120px)',
          borderRadius: '50%',
          pointerEvents: 'none'
        }}
      />

      {/* ── Main Content ── */}
      <div style={{ 
        position: 'relative', 
        zIndex: 1, 
        maxWidth: '48rem', 
        margin: '0 auto', 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        paddingTop: '6rem',
        paddingLeft: '2rem',
        paddingRight: '2rem',
        paddingBottom: '4rem'
      }}>
        {/* ── Page Title ── */}
        <div style={{ textAlign: 'center', marginBottom: '3rem', width: '100%' }}>
          <p style={{ 
            fontSize: 11, 
            fontWeight: 700, 
            color: '#f97316', 
            textTransform: 'uppercase', 
            letterSpacing: '0.15em', 
            marginBottom: 16 
          }}>
            AI-Powered Data Ingestion
          </p>
          <h1 style={{ 
            fontSize: 40, 
            fontWeight: 700, 
            color: '#F1F5F9', 
            letterSpacing: '-0.02em', 
            marginBottom: 12,
            background: 'linear-gradient(135deg, #F8FAFC 0%, #CBD5E1 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>
            Upload Report
          </h1>
          <p style={{ fontSize: 16, color: '#94A3B8', lineHeight: 1.6 }}>
            Drop any PDF — company, year, and currency detected automatically
          </p>
        </div>

        {/* ── Premium Dropzone ── */}
        <div 
          {...getRootProps()} 
          style={{ 
            width: '100%', 
            height: '20rem', 
            borderRadius: '1rem', 
            background: 'rgba(255, 255, 255, 0.02)', 
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            border: isDragActive ? '2px dashed rgba(249, 115, 34, 0.5)' : (file && !detectError) ? '2px dashed rgba(255, 255, 255, 0.2)' : detectError ? '2px dashed rgba(239, 68, 68, 0.5)' : '2px dashed rgba(255, 255, 255, 0.1)',
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center', 
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            position: 'relative',
            zIndex: 10,
            outline: 'none',
            boxShadow: file && !detectError ? '0 8px 32px rgba(232, 71, 10, 0.15)' : '0 4px 16px rgba(0, 0, 0, 0.3)'
          }}
          onMouseEnter={(e) => {
            if (!detecting) {
              e.currentTarget.style.borderColor = 'rgba(249, 115, 34, 0.5)'
              e.currentTarget.style.background = 'rgba(249, 115, 34, 0.02)'
            }
          }}
          onMouseLeave={(e) => {
            if (!isDragActive && !detectError) {
              e.currentTarget.style.borderColor = file ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)'
            }
          }}
        >
          <input {...getInputProps()}/>
          {detecting ? (
            <div style={{ display:'flex',flexDirection:'column',alignItems:'center',gap:16,color:'#f97316' }}>
              <Loader2 style={{ width: 48, height: 48, animation: 'spin 1s linear infinite' }} />
              <p style={{ fontSize:18,fontWeight:600,color:'#F1F5F9' }}>Scanning report…</p>
              <p style={{ fontSize:14,color:'#64748B',fontFamily:'monospace' }}>Detecting company · year · currency</p>
            </div>
          ) : detectError ? (
            <div style={{ display:'flex',flexDirection:'column',alignItems:'center',gap:12,color:'#ef4444' }}>
              <AlertCircle style={{width:48,height:48}}/>
              <p style={{ fontSize:16,fontWeight:600,color:'#F1F5F9' }}>{detectError}</p>
              <p style={{ fontSize:14,color:'#64748B' }}>Please upload a financial report PDF</p>
            </div>
          ) : file ? (
            <div style={{ display:'flex',flexDirection:'column',alignItems:'center',gap:12 }}>
              <CheckCircle2 style={{width:48,height:48,color:'#10b981'}}/>
              <p style={{ fontSize:18,fontWeight:600,color:'#F1F5F9' }}>{file.name}</p>
              <p style={{ fontSize:14,color:'#64748B',fontFamily:'monospace' }}>{(file.size/1024/1024).toFixed(1)} MB · click to replace</p>
            </div>
          ) : (
            <div style={{ display:'flex',flexDirection:'column',alignItems:'center',gap:16 }}>
              <UploadCloud 
                style={{ 
                  width: 48, 
                  height: 48, 
                  color: isDragActive ? '#f97316' : '#94A3B8',
                  transition: 'color 0.3s ease'
                }} 
              />
              <div style={{ textAlign: 'center' }}>
                <p style={{ fontSize:18,fontWeight:500,color:'#F1F5F9',marginBottom:8 }}>
                  {isDragActive ? 'Drop it here' : 'Drag & drop or click to browse'}
                </p>
                <p style={{ fontSize:14,color:'#64748B',fontFamily:'monospace' }}>
                  PDF • max 100 MB • XBRL supported
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ── Action Button ── */}
        <button 
          type="button" 
          disabled={!canSubmit||uploadMut.isPending} 
          onClick={()=>uploadMut.mutate()}
          style={{ 
            width: '100%', 
            marginTop: '1.5rem',
            padding: '1rem',
            borderRadius: '0.75rem',
            fontWeight: 700,
            fontSize: 14,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            transition: 'all 0.3s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
            cursor: canSubmit && !uploadMut.isPending ? 'pointer' : 'not-allowed',
            background: canSubmit && !uploadMut.isPending 
              ? 'linear-gradient(135deg, #e8470a 0%, #f97316 100%)'
              : 'rgba(255, 255, 255, 0.05)',
            color: canSubmit && !uploadMut.isPending ? '#ffffff' : '#64748B',
            border: canSubmit && !uploadMut.isPending 
              ? '1px solid rgba(249, 115, 34, 0.5)'
              : '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: canSubmit && !uploadMut.isPending 
              ? '0 0 20px rgba(255, 85, 0, 0.3)'
              : 'none'
          }}
          onMouseEnter={(e) => {
            if (canSubmit && !uploadMut.isPending) {
              e.currentTarget.style.background = 'linear-gradient(135deg, #d13d08 0%, #e8470a 100%)'
              e.currentTarget.style.boxShadow = '0 0 30px rgba(255, 85, 0, 0.4)'
              e.currentTarget.style.transform = 'translateY(-2px)'
            }
          }}
          onMouseLeave={(e) => {
            if (canSubmit && !uploadMut.isPending) {
              e.currentTarget.style.background = 'linear-gradient(135deg, #e8470a 0%, #f97316 100%)'
              e.currentTarget.style.boxShadow = '0 0 20px rgba(255, 85, 0, 0.3)'
              e.currentTarget.style.transform = 'translateY(0)'
            }
          }}
        >
          {uploadMut.isPending ? (
            <>
              <Loader2 style={{width:18,height:18,animation:'spin 1s linear infinite'}}/>
              Processing...
            </>
          ) : (
            <>
              <UploadCloud style={{width:18,height:18}}/>
              Upload & Process
            </>
          )}
        </button>

        {!canSubmit&&file&&!detecting&&!detectError&&!year&&(
          <p style={{ fontSize:12,color:'#fbbf24',marginTop:12,textAlign:'center',fontWeight:600 }}>
            ⚠ Enter fiscal year to continue
          </p>
        )}

        {/* ── Detected Card ── */}
        {detected?.is_financial_report && (
          <div style={{ 
            width: '100%',
            marginTop: '2rem',
            background:'rgba(16, 18, 26, 0.8)',
            backdropFilter: 'blur(12px)',
            border:'1px solid rgba(255,255,255,0.1)',
            borderRadius:16,
            overflow:'hidden',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)'
          }}>
            <div style={{ 
              display:'flex',
              alignItems:'center',
              gap:10,
              padding:'14px 20px',
              borderBottom:'1px solid rgba(255,255,255,0.05)',
              background:'rgba(249, 115, 34, 0.05)' 
            }}>
              <Sparkles style={{width:16,height:16,color:'#f97316'}}/>
              <span style={{ fontSize:12,fontWeight:700,color:'#F1F5F9' }}>AI Auto-detected</span>
              <span style={{ 
                fontSize:10,
                fontWeight:700,
                color: detected.confidence==='high' ? '#10b981' : detected.confidence==='medium' ? '#fbbf24' : '#64748B',
                background: detected.confidence==='high' ? 'rgba(16,185,129,0.15)' : detected.confidence==='medium' ? 'rgba(251,191,36,0.15)' : 'rgba(255,255,255,0.05)',
                borderRadius:6,
                padding:'3px 8px',
                textTransform:'uppercase',
                letterSpacing:'0.06em' 
              }}>
                {detected.confidence} confidence
              </span>
              {detected.report_type&&<span style={{marginLeft:'auto',fontSize:11,color:'#64748B',fontFamily:'monospace'}}>{detected.report_type}</span>}
            </div>
            <div style={{ 
              display:'grid',
              gridTemplateColumns:'repeat(2, 1fr)',
              gap:20,
              padding:'20px' 
            }}>
              {[
                ['Company',`${selComp?.name||nameFree||detected.company_name||'—'}${(selComp?.ticker||detected.ticker)?` (${selComp?.ticker||detected.ticker})`:''}` ],
                ['Fiscal Year',year||'—'],
                ['Currency',currency],
                ['Unit Scale',unit]
              ].map(([l,v])=>(
                <div key={l}>
                  <p style={{ 
                    fontSize:10,
                    fontWeight:700,
                    color:'#64748B',
                    textTransform:'uppercase',
                    letterSpacing:'0.1em',
                    marginBottom:6 
                  }}>
                    {l}
                  </p>
                  <p style={{ fontSize:14,fontWeight:600,color:'#F1F5F9' }}>{v}</p>
                </div>
              ))}
            </div>
            <button 
              onClick={()=>setShowOverride(o=>!o)} 
              aria-expanded={showOverride}
              style={{ 
                width:'100%',
                display:'flex',
                alignItems:'center',
                gap:8,
                padding:'12px 20px',
                borderTop:'1px solid rgba(255,255,255,0.05)',
                background:'rgba(255,255,255,0.02)',
                border:'none',
                cursor:'pointer',
                fontSize:12,
                color:'#94A3B8',
                fontWeight:600,
                textTransform:'uppercase',
                letterSpacing:'0.08em',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                e.currentTarget.style.color = '#F1F5F9'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.02)'
                e.currentTarget.style.color = '#94A3B8'
              }}
            >
              {showOverride ? <ChevronUp style={{width:14,height:14}}/> : <ChevronDown style={{width:14,height:14}}/>}
              {showOverride ? 'Hide overrides' : 'Override detected values'}
            </button>
            {showOverride && (
              <div style={{ 
                padding:'20px',
                borderTop:'1px solid rgba(255,255,255,0.05)',
                background:'rgba(0,0,0,0.2)',
                display:'flex',
                flexDirection:'column',
                gap:16 
              }} className="animate-in">
                <div>
                  <L>Company</L>
                  <CompanySearch value={selComp} onChange={c=>{setSelComp(c);if(c)setNameFree('')}} placeholder="Search NSE / BSE…"/>
                  {!selComp&&<input className="input" style={{marginTop:10,background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} placeholder="Or type freely…" value={nameFree} onChange={e=>setNameFree(e.target.value)}/>}
                </div>
                <div style={{ display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12 }}>
                  <div>
                    <L>Fiscal Year</L>
                    <input type="number" min={2000} max={2100} className="input" style={{background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} value={year} onChange={e=>setYear(Number(e.target.value))}/>
                  </div>
                  <div>
                    <L>Currency</L>
                    <select className="select" style={{background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} value={currency} onChange={e=>setCurrency(e.target.value)}>
                      {CURRENCIES.map(c=><option key={c}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <L>Unit Scale</L>
                    <select className="select" style={{background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} value={unit} onChange={e=>setUnit(e.target.value)}>
                      {UNITS.map(s=><option key={s} value={s} style={{textTransform:'capitalize'}}>{s}</option>)}
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Manual Form ── */}
        {!detected && !detecting && file && !detectError && (
          <div style={{ 
            width: '100%',
            marginTop: '2rem',
            background:'rgba(16,18,26,0.8)',
            backdropFilter: 'blur(12px)',
            border:'1px solid rgba(251,191,36,0.3)',
            borderRadius:16,
            padding:20,
            display:'flex',
            flexDirection:'column',
            gap:16,
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)'
          }} className="animate-in">
            <p style={{ 
              fontSize:13,
              fontWeight:600,
              color:'#fbbf24',
              display:'flex',
              alignItems:'center',
              gap:8 
            }}>
              <AlertCircle style={{width:16,height:16}}/>
              Detection unavailable — fill in manually
            </p>
            <CompanySearch value={selComp} onChange={c=>{setSelComp(c);if(c)setNameFree('')}} placeholder="Search NSE / BSE…"/>
            {!selComp&&<input className="input" style={{background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} placeholder="Company name (unlisted)" value={nameFree} onChange={e=>setNameFree(e.target.value)}/>}
            <div style={{ display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12 }}>
              <div>
                <L>Fiscal Year *</L>
                <input type="number" min={2000} max={2100} className="input" style={{background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} value={year} onChange={e=>setYear(Number(e.target.value))}/>
              </div>
              <div>
                <L>Currency</L>
                <select className="select" style={{background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} value={currency} onChange={e=>setCurrency(e.target.value)}>
                  {CURRENCIES.map(c=><option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <L>Unit Scale</L>
                <select className="select" style={{background:'rgba(16,18,26,0.8)',border:'1px solid rgba(255,255,255,0.1)'}} value={unit} onChange={e=>setUnit(e.target.value)}>
                  {UNITS.map(s=><option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* ── Existing Filings ── */}
        {existingFilings.length>0&&(
          <div style={{ width: '100%', marginTop:'3rem' }}>
            <p style={{ 
              fontSize:11,
              fontWeight:700,
              color:'#64748B',
              textTransform:'uppercase',
              letterSpacing:'0.12em',
              marginBottom:16 
            }}>
              Existing filings for {selComp?.name}
            </p>
            <div style={{ display:'flex',flexDirection:'column',gap:8 }}>
              {existingFilings.map(f=>(
                <div key={f.id} style={{ 
                  display:'flex',
                  alignItems:'center',
                  justifyContent:'space-between',
                  background:'rgba(16,18,26,0.6)',
                  backdropFilter: 'blur(12px)',
                  border:'1px solid rgba(255,255,255,0.05)',
                  borderRadius:12,
                  padding:'14px 16px',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(16,18,26,0.9)'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(16,18,26,0.6)'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)'
                }}
                >
                  <div style={{ display:'flex',alignItems:'center',gap:12 }}>
                    <FileText style={{width:16,height:16,color:'#64748B'}}/>
                    <span style={{ fontSize:14,fontWeight:600,color:'#F1F5F9' }}>FY {f.fiscal_year}</span>
                    <span style={{ fontSize:12,color:'#64748B',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:200 }}>{f.file_name}</span>
                  </div>
                  <div style={{ display:'flex',alignItems:'center',gap:10 }}>
                    <StatusBadge status={f.status}/>
                    {f.status==='completed'&&<a href={`/filings/${f.id}`} style={{ fontSize:12,color:'#f97316',textDecoration:'none',fontWeight:600,transition:'color 0.2s' }} onMouseEnter={(e)=>e.currentTarget.style.color='#fb923c'} onMouseLeave={(e)=>e.currentTarget.style.color='#f97316'}>View →</a>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
