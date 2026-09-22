import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Trash2, FileText, Bell, BellOff, X, ChevronRight, Building2, Search, Filter } from 'lucide-react'
import toast from 'react-hot-toast'
import { getCompanies, createCompany, deleteCompany, updateCompany, getFilings } from '../services/api'
import CompanySearch from '../components/CompanySearch'

function Modal({ onClose, onCreate }) {
  const [sel, setSel] = useState(null)
  const [tracked, setTracked] = useState(false)
  return (
    <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,0.75)',backdropFilter:'blur(4px)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:50,padding:16 }} onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:'#10121A',border:'1px solid rgba(255,255,255,0.1)',borderRadius:16,width:'100%',maxWidth:480,padding:28,boxShadow:'0 20px 60px rgba(0,0,0,0.5)' }} className="animate-in">
        <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:24 }}>
          <h2 style={{ fontSize:18,fontWeight:700,color:'#F8FAFC' }}>Add Company</h2>
          <button onClick={onClose} style={{ width:32,height:32,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:8,border:'none',background:'transparent',color:'#94A3B8',cursor:'pointer',transition:'all 0.2s' }} onMouseEnter={e=>{e.currentTarget.style.background='rgba(255,255,255,0.05)';e.currentTarget.style.color='#F8FAFC'}} onMouseLeave={e=>{e.currentTarget.style.background='transparent';e.currentTarget.style.color='#94A3B8'}}><X style={{width:18,height:18}}/></button>
        </div>
        <div style={{ display:'flex',flexDirection:'column',gap:18 }}>
          <div>
            <label style={{ display:'block',fontSize:11,fontWeight:700,color:'#64748B',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:8 }}>Search NSE / BSE</label>
            <CompanySearch value={sel} onChange={setSel} placeholder="e.g. Infosys, RELIANCE…"/>
          </div>
          {sel && (
            <div style={{ background:'rgba(0,0,0,0.3)',border:'1px solid rgba(255,255,255,0.08)',borderRadius:10,padding:'14px 16px' }}>
              {[['Ticker',sel.ticker,true],['Sector',sel.sector,false],['Exchange',sel.exchange,false]].filter(([,v])=>v).map(([l,v,m])=>(
                <div key={l} style={{ display:'flex',justifyContent:'space-between',marginBottom:6,fontSize:13,lastChild:{marginBottom:0} }}>
                  <span style={{ color:'#64748B' }}>{l}</span>
                  <span style={{ color:'#F1F5F9',fontWeight:600,...(m?{fontFamily:'JetBrains Mono, monospace',color:'#fbbf24'}:{}) }}>{v}</span>
                </div>
              ))}
            </div>
          )}
          <label style={{ display:'flex',alignItems:'center',gap:12,cursor:'pointer',padding:'12px 14px',background:'rgba(255,255,255,0.02)',borderRadius:10,border:'1px solid rgba(255,255,255,0.05)',transition:'all 0.2s' }} onMouseEnter={e=>e.currentTarget.style.borderColor='rgba(232,71,10,0.2)'} onMouseLeave={e=>e.currentTarget.style.borderColor='rgba(255,255,255,0.05)'}>
            <div style={{ position:'relative' }}>
              <input type="checkbox" checked={tracked} onChange={e=>setTracked(e.target.checked)} style={{ position:'absolute',opacity:0,width:0 }}/>
              <div style={{ width:44,height:24,borderRadius:99,background:tracked?'linear-gradient(135deg, #e8470a 0%, #f97316 100%)':'#1e293b',transition:'all 0.2s',border:'1px solid '+(tracked?'rgba(232,71,10,0.3)':'rgba(255,255,255,0.1)'),boxShadow:tracked?'0 4px 12px rgba(232,71,10,0.3)':'none' }}>
                <div style={{ width:18,height:18,borderRadius:'50%',background:'white',margin:2,transform:tracked?'translateX(20px)':'none',transition:'transform 0.2s',boxShadow:'0 2px 4px rgba(0,0,0,0.2)' }}/>
              </div>
            </div>
            <span style={{ fontSize:13,color:'#CBD5E1',fontWeight:500 }}>Track new filings automatically</span>
          </label>
          <div style={{ display:'flex',gap:10,paddingTop:8 }}>
            <button className="btn-primary" style={{ flex:1,justifyContent:'center',height:44,fontSize:13 }} disabled={!sel} onClick={()=>onCreate({name:sel.name,ticker:sel.ticker,sector:sel.sector,exchange:sel.exchange,is_tracked:tracked})}>Add Company</button>
            <button className="btn-secondary" style={{ flex:1,justifyContent:'center',height:44,fontSize:13 }} onClick={onClose}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Companies() {
  const qc = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [sectorFilter, setSectorFilter] = useState('all')
  const { data: companies=[], isLoading } = useQuery({ queryKey:['companies'], queryFn:getCompanies })
  const { data: allFilings=[], isLoading: isLoadingFilings } = useQuery({ 
    queryKey:['filings-all'], 
    queryFn:() => getFilings(), 
    refetchInterval: 30000 
  })
  const createMut = useMutation({ mutationFn:createCompany, onSuccess:()=>{qc.invalidateQueries(['companies']);setShowModal(false);toast.success('Company added')}, onError:e=>toast.error(e.response?.data?.detail||'Failed') })
  const deleteMut = useMutation({ mutationFn:deleteCompany, onSuccess:()=>{qc.invalidateQueries(['companies']);toast.success('Deleted')} })
  const toggleTrack = useMutation({ mutationFn:({id,data})=>updateCompany(id,data), onSuccess:()=>qc.invalidateQueries(['companies']) })

  // Extract unique sectors
  const sectors = useMemo(() => {
    const unique = [...new Set(companies.map(c => c.sector).filter(Boolean))]
    return ['all', ...unique.sort()]
  }, [companies])

  // Filter companies
  const filteredCompanies = useMemo(() => {
    return companies.filter(c => {
      const matchesSearch = !searchQuery || 
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.ticker?.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesSector = sectorFilter === 'all' || c.sector === sectorFilter
      return matchesSearch && matchesSector
    })
  }, [companies, searchQuery, sectorFilter])

  // Get company financials from real filing data
  const getCompanyFinancials = (company) => {
    const companyFilings = allFilings.filter(f => f.company_id === company.id)
    
    if (companyFilings.length === 0) {
      return { latestDoc: 'No reports', hasData: false }
    }

    // Get the latest completed filing
    const latestFiling = companyFilings
      .filter(f => f.status === 'completed')
      .sort((a, b) => b.fiscal_year - a.fiscal_year)[0]

    if (!latestFiling) {
      const processingFiling = companyFilings.find(f => f.status === 'processing' || f.status === 'pending')
      if (processingFiling) {
        return { 
          latestDoc: `FY${processingFiling.fiscal_year} (Processing)`,
          hasData: false
        }
      }
      return { latestDoc: 'No reports', hasData: false }
    }

    return {
      latestDoc: `FY${latestFiling.fiscal_year} ${latestFiling.report_type || 'Annual Report'}`,
      hasData: true,
      filingId: latestFiling.id
    }
  }

  if (isLoading || isLoadingFilings) return (
    <div style={{ 
      position: 'relative', 
      minHeight: '100vh', 
      background: '#08090C', 
      overflow: 'hidden' 
    }}>
      {/* Background effects */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '500px',
        background: 'radial-gradient(ellipse 80% 80% at 50% -20%, rgba(255, 85, 0, 0.08), rgba(255, 255, 255, 0))',
        pointerEvents: 'none'
      }} />
      
      <div style={{ position: 'relative', zIndex: 1, padding:'40px 32px', maxWidth:1600, margin:'0 auto' }}>
        {[...Array(5)].map((_,i)=><div key={i} style={{ 
          background:'rgba(16, 18, 26, 0.8)',
          backdropFilter: 'blur(12px)',
          borderRadius:12,
          height:72,
          marginBottom:8,
          opacity:0.5,
          border:'1px solid rgba(255,255,255,0.05)' 
        }}/>)}
      </div>
    </div>
  )

  return (
    <div style={{ 
      position: 'relative', 
      minHeight: '100vh', 
      background: '#08090C', 
      overflow: 'hidden' 
    }}>
      {/* ── Dynamic Top Glow Effect ── */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '500px',
        background: 'radial-gradient(ellipse 80% 80% at 50% -20%, rgba(255, 85, 0, 0.08), rgba(255, 255, 255, 0))',
        pointerEvents: 'none',
        zIndex: 0
      }} />

      {/* ── SVG 3D Grid Pattern ── */}
      <div style={{
        position: 'absolute',
        inset: 0,
        opacity: 0.1,
        pointerEvents: 'none',
        zIndex: 0,
        transform: 'perspective(1000px) rotateX(60deg) scale(2)',
        transformOrigin: 'center top'
      }}>
        <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse">
              <path 
                d="M 80 0 L 0 0 0 80" 
                fill="none" 
                stroke="rgba(232, 71, 10, 0.3)" 
                strokeWidth="0.5"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      {/* ── Main Content ── */}
      <div style={{ 
        position: 'relative', 
        zIndex: 1, 
        padding: '40px 32px', 
        maxWidth: 1600, 
        width: '100%', 
        margin: '0 auto' 
      }}>
        {/* ── Header ── */}
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:32, flexWrap:'wrap', gap:20 }}>
        <div>
          <p style={{ fontSize:11,fontWeight:700,color:'#e8470a',textTransform:'uppercase',letterSpacing:'0.15em',marginBottom:10 }}>Portfolio Management</p>
          <h1 style={{ fontSize:36,fontWeight:700,color:'#F8FAFC',letterSpacing:'-0.02em',marginBottom:6 }}>Companies</h1>
          <p style={{ fontSize:14,color:'#64748B',marginTop:4 }}>Monitor and analyze your corporate portfolio</p>
        </div>
        <button className="btn-primary" style={{ height:48,fontSize:14,padding:'0 24px' }} onClick={()=>setShowModal(true)}><Plus style={{width:18,height:18}}/>Add Company</button>
      </div>

      {/* ── Utility Bar: Search & Filter ── */}
      <div style={{ display:'flex', gap:12, marginBottom:24, flexWrap:'wrap' }}>
        <div style={{ position:'relative', flex:1, minWidth:300 }}>
          <Search style={{ position:'absolute', left:14, top:'50%', transform:'translateY(-50%)', width:18, height:18, color:'#64748B', pointerEvents:'none' }} />
          <input
            type="text"
            placeholder="Search by company name or ticker..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="input"
            style={{ 
              paddingLeft:46, 
              background:'rgba(16, 18, 26, 0.8)', 
              backdropFilter: 'blur(12px)',
              border:'1px solid rgba(255,255,255,0.1)', 
              height:48,
              fontSize:14,
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
            }}
          />
        </div>
        <div style={{ position:'relative', minWidth:220 }}>
          <Filter style={{ position:'absolute', left:14, top:'50%', transform:'translateY(-50%)', width:18, height:18, color:'#64748B', pointerEvents:'none', zIndex:1 }} />
          <select
            value={sectorFilter}
            onChange={e => setSectorFilter(e.target.value)}
            className="select"
            style={{ 
              paddingLeft:46, 
              background:'rgba(16, 18, 26, 0.8)', 
              backdropFilter: 'blur(12px)',
              border:'1px solid rgba(255,255,255,0.1)', 
              height:48,
              fontSize:14,
              fontWeight:600,
              appearance:'none',
              backgroundImage:`url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2364748B'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`,
              backgroundRepeat:'no-repeat',
              backgroundPosition:'right 12px center',
              backgroundSize:'20px',
              paddingRight:40,
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
            }}
          >
            <option value="all">All Sectors</option>
            {sectors.filter(s => s !== 'all').map(sector => (
              <option key={sector} value={sector}>{sector}</option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Results Count ── */}
      {searchQuery || sectorFilter !== 'all' ? (
        <div style={{ marginBottom:16, fontSize:13, color:'#94A3B8' }}>
          Showing <span style={{ fontWeight:700, color:'#F8FAFC' }}>{filteredCompanies.length}</span> of {companies.length} companies
        </div>
      ) : null}

      {/* ── Company List ── */}
      {filteredCompanies.length === 0 ? (
        <div style={{ 
          border:'1px dashed rgba(255,255,255,0.1)',
          borderRadius:16,
          padding:'100px 20px',
          textAlign:'center',
          background:'rgba(16, 18, 26, 0.5)',
          backdropFilter: 'blur(12px)',
          boxShadow: 'inset 0 2px 20px rgba(0, 0, 0, 0.3)'
        }}>
          <Building2 style={{width:56,height:56,color:'#334155',margin:'0 auto 20px'}}/>
          <p style={{ fontSize:18,fontWeight:700,color:'#F8FAFC',marginBottom:8 }}>
            {companies.length === 0 ? 'No companies yet' : 'No companies found'}
          </p>
          <p style={{ fontSize:14,color:'#64748B',maxWidth:320,margin:'0 auto',lineHeight:1.6 }}>
            {companies.length === 0 
              ? 'Upload an annual report or manually add a company to get started.' 
              : 'Try adjusting your search or filter criteria.'}
          </p>
        </div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
          {filteredCompanies.map((c, idx) => {
            const initials = (c.ticker||c.name).slice(0,2).toUpperCase()
            const financials = getCompanyFinancials(c)

            return (
              <div 
                key={c.id} 
                style={{ 
                  display:'grid',
                  gridTemplateColumns:'repeat(12, minmax(0, 1fr))',
                  alignItems:'center',
                  gap:16,
                  background:'rgba(16, 18, 26, 0.95)',
                  backdropFilter: 'blur(12px)',
                  WebkitBackdropFilter: 'blur(12px)',
                  border:'1px solid rgba(255,255,255,0.05)',
                  borderRadius:12,
                  padding:'18px 20px',
                  transition:'all 0.2s ease',
                  animation:`fadeUp 0.3s ease ${idx * 0.05}s both`,
                  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)'
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'rgba(16, 18, 26, 1)'
                  e.currentTarget.style.borderColor = 'rgba(232,71,10,0.3)'
                  e.currentTarget.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(232, 71, 10, 0.2)'
                  e.currentTarget.querySelector('.action-buttons').style.opacity = '1'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'rgba(16, 18, 26, 0.95)'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)'
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.3)'
                  e.currentTarget.querySelector('.action-buttons').style.opacity = '0.5'
                }}
              >
                {/* Column 1: Company Info */}
                <div style={{ gridColumn:'span 6', display:'flex', alignItems:'center', gap:14, minWidth:0 }}>
                  <div style={{ 
                    width:44, 
                    height:44, 
                    borderRadius:10, 
                    background:'#18181b',
                    border:'1px solid rgba(255,255,255,0.1)',
                    display:'flex',
                    alignItems:'center',
                    justifyContent:'center',
                    fontSize:13,
                    fontWeight:700,
                    color:'#f97316',
                    flexShrink:0,
                    letterSpacing:'0.05em'
                  }}>
                    {initials}
                  </div>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4, flexWrap:'wrap' }}>
                      <Link 
                        to={`/companies/${c.id}`} 
                        style={{ 
                          fontSize:15, 
                          fontWeight:600, 
                          color:'#F8FAFC', 
                          textDecoration:'none',
                          overflow:'hidden',
                          textOverflow:'ellipsis',
                          whiteSpace:'nowrap',
                          transition:'color 0.2s'
                        }}
                        onMouseEnter={e => e.currentTarget.style.color = '#f97316'}
                        onMouseLeave={e => e.currentTarget.style.color = '#F8FAFC'}
                      >
                        {c.name}
                      </Link>
                      {c.ticker && (
                        <span style={{ 
                          fontSize:10, 
                          fontWeight:700, 
                          color:'#fbbf24', 
                          background:'rgba(251,191,36,0.12)', 
                          borderRadius:6, 
                          padding:'3px 8px', 
                          fontFamily:'JetBrains Mono, monospace',
                          flexShrink:0,
                          border:'1px solid rgba(251,191,36,0.2)'
                        }}>
                          {c.ticker}
                        </span>
                      )}
                      {c.is_tracked && (
                        <span style={{ 
                          fontSize:10, 
                          fontWeight:700, 
                          color:'#e8470a', 
                          background:'rgba(232,71,10,0.12)',
                          borderRadius:6,
                          padding:'3px 8px',
                          display:'inline-flex',
                          alignItems:'center',
                          gap:4,
                          border:'1px solid rgba(232,71,10,0.2)'
                        }}>
                          <Bell style={{width:10,height:10}}/>
                          TRACKED
                        </span>
                      )}
                    </div>
                    {c.sector && (
                      <p style={{ 
                        fontSize:12, 
                        color:'#64748B',
                        overflow:'hidden',
                        textOverflow:'ellipsis',
                        whiteSpace:'nowrap'
                      }}>
                        {c.sector}
                      </p>
                    )}
                  </div>
                </div>

                {/* Column 2: Filing Status */}
                <div style={{ gridColumn:'span 3', display:'flex', flexDirection:'column', gap:4 }}>
                  <p style={{ fontSize:11, color:'#64748B', textTransform:'uppercase', letterSpacing:'0.05em', fontWeight:700 }}>Latest Filing</p>
                  <p style={{ fontSize:13, color:'#CBD5E1', fontWeight:600 }}>{financials.latestDoc}</p>
                </div>

                {/* Column 3: Actions */}
                <div className="action-buttons" style={{ gridColumn:'span 3', display:'flex', gap:6, justifyContent:'flex-end', opacity:0.5, transition:'opacity 0.2s' }}>
                  {financials.hasData && financials.filingId ? (
                    <Link 
                      to={`/companies/${c.id}`} 
                      className="btn-secondary" 
                      style={{ fontSize:11, padding:'8px 14px', height:36, fontWeight:700 }}
                    >
                      <FileText style={{width:14,height:14}}/>
                      VIEW REPORT
                    </Link>
                  ) : (
                    <Link 
                      to={`/upload?company=${c.id}`} 
                      className="btn-secondary" 
                      style={{ fontSize:11, padding:'8px 14px', height:36, fontWeight:700 }}
                    >
                      <FileText style={{width:14,height:14}}/>
                      UPLOAD REPORT
                    </Link>
                  )}
                  <button 
                    className="btn-icon" 
                    title={c.is_tracked?'Stop tracking':'Track'} 
                    onClick={()=>toggleTrack.mutate({id:c.id,data:{...c,is_tracked:!c.is_tracked}})}
                    style={{ width:36, height:36 }}
                  >
                    {c.is_tracked ? <Bell style={{width:16,height:16,color:'#e8470a'}}/> : <BellOff style={{width:16,height:16}}/>}
                  </button>
                  <button 
                    className="btn-icon" 
                    style={{color:'#ef4444', width:36, height:36}} 
                    onClick={()=>{if(confirm(`Delete ${c.name}?`))deleteMut.mutate(c.id)}}
                    title="Delete company"
                  >
                    <Trash2 style={{width:16,height:16}}/>
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {showModal && <Modal onClose={()=>setShowModal(false)} onCreate={createMut.mutate}/>}
      </div>
    </div>
  )
}
