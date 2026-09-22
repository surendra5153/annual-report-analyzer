import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Building2, Upload, ChevronRight, Bell, Loader2, XCircle, AlertTriangle, TrendingUp, DollarSign, FileText, PieChart } from 'lucide-react'
import { useState, useEffect } from 'react'
import { getCompanies, getFilings, getKPIs, getRisks } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

// ── Hook to detect mobile ────────────────────────────────────────────────────
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false)
  
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])
  
  return isMobile
}

// ── Sub-components ───────────────────────────────────────────────────────────
function MetricCard({ label, value, change, trend, icon: Icon, color = '#f5f5f0' }) {
  const isPositive = change?.startsWith('+')
  const isMobile = useIsMobile()
  
  return (
    <div style={{ 
      background: '#0f0f0f', 
      border: '1px solid #1a1a1a', 
      borderRadius: 12, 
      padding: isMobile ? '16px' : '20px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <p style={{ fontSize: 10, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {label}
        </p>
        {Icon && <Icon style={{ width: 18, height: 18, color: '#555' }} />}
      </div>
      <p style={{ fontSize: isMobile ? 28 : 32, fontWeight: 700, color, lineHeight: 1, fontFamily: 'monospace', marginBottom: 8 }}>
        {value}
      </p>
      {change && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ 
            fontSize: 11, 
            fontWeight: 600, 
            color: isPositive ? '#34d399' : '#f87171',
            background: isPositive ? 'rgba(52, 211, 153, 0.1)' : 'rgba(248, 113, 113, 0.1)',
            padding: '3px 8px',
            borderRadius: 6
          }}>
            {change}
          </span>
          {trend && (
            <div style={{ flex: 1, height: 20 }}>
              <svg width="60" height="20" style={{ opacity: 0.6 }}>
                <polyline
                  fill="none"
                  stroke={isPositive ? '#34d399' : '#f87171'}
                  strokeWidth="2"
                  points={trend}
                />
              </svg>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function RiskFeedItem({ company, risk, severity, date }) {
  const severityColors = {
    critical: { 
      bg: 'rgba(220, 38, 38, 0.08)', 
      border: 'rgba(239, 68, 68, 0.3)', 
      text: '#FCA5A5',
      icon: '#EF4444'
    },
    high: { 
      bg: 'rgba(217, 119, 6, 0.08)', 
      border: 'rgba(251, 191, 36, 0.3)', 
      text: '#FCD34D',
      icon: '#FBBF24'
    },
    medium: { 
      bg: 'rgba(79, 70, 229, 0.08)', 
      border: 'rgba(129, 140, 248, 0.3)', 
      text: '#A5B4FC',
      icon: '#818CF8'
    }
  }
  const colors = severityColors[severity] || severityColors.medium

  return (
    <div style={{ 
      background: colors.bg, 
      border: `1px solid ${colors.border}`,
      borderRadius: 12, 
      padding: '16px',
      marginBottom: 12,
      transition: 'all 0.2s ease'
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.borderColor = colors.icon
      e.currentTarget.style.transform = 'translateX(4px)'
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.borderColor = colors.border
      e.currentTarget.style.transform = 'translateX(0)'
    }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: `${colors.icon}15`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0
        }}>
          <AlertTriangle style={{ width: 18, height: 18, color: colors.icon }} />
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ 
            fontSize: 11, 
            fontWeight: 700, 
            color: colors.text, 
            marginBottom: 6, 
            textTransform: 'uppercase', 
            letterSpacing: '0.08em' 
          }}>
            {company}
          </p>
          <p style={{ 
            fontSize: 14, 
            color: '#F1F5F9', 
            lineHeight: 1.6, 
            marginBottom: 8,
            fontWeight: 500
          }}>
            {risk}
          </p>
          <p style={{ 
            fontSize: 11, 
            color: '#64748B',
            display: 'flex',
            alignItems: 'center',
            gap: 6
          }}>
            <span style={{
              width: 4,
              height: 4,
              borderRadius: '50%',
              background: '#64748B'
            }} />
            {date}
          </p>
        </div>
      </div>
    </div>
  )
}

function StatusPill({ status }) {
  const map = {
    completed:  { label: 'Completed',  color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
    processing: { label: 'Processing', color: '#818cf8', bg: 'rgba(129,140,248,0.1)' },
    pending:    { label: 'Pending',    color: '#fbbf24', bg: 'rgba(251,191,36,0.1)'  },
    failed:     { label: 'Failed',     color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
  }
  const s = map[status] || map.pending
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 600, color: s.color, background: s.bg, borderRadius: 6, padding: '3px 8px' }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: s.color,
        ...(status === 'processing' || status === 'pending' ? { animation: 'pulse 1.5s ease-in-out infinite' } : {})
      }} />
      {s.label}
    </span>
  )
}

function CompanyRow({ company, filings }) {
  const latest = [...filings].sort((a, b) => b.fiscal_year - a.fiscal_year)[0]
  const initials = (company.ticker || company.name).slice(0, 2).toUpperCase()
  const completed = filings.filter(f => f.status === 'completed').length
  
  // Use Clearbit Logo API for company logos (open-source alternative)
  // Falls back to UI Avatars if logo not found
  const getCompanyLogo = (companyName) => {
    const domain = companyName.toLowerCase().replace(/\s+/g, '').replace(/[^a-z]/g, '');
    return `https://logo.clearbit.com/${domain}.com`;
  }

  return (
    <Link to={`/companies/${company.id}`} className="card-hover group" style={{ gap: 16 }}>
      <div style={{ 
        width: 40, 
        height: 40, 
        borderRadius: 10, 
        overflow: 'hidden',
        background: '#1a1a1a',
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        fontSize: 13, 
        fontWeight: 700, 
        color: 'white', 
        flexShrink: 0,
        border: '1px solid #2a2a2a'
      }}>
        <img 
          src={getCompanyLogo(company.name)}
          alt={company.name}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          onError={(e) => {
            e.target.style.display = 'none';
            e.target.parentElement.innerHTML = initials;
          }}
        />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#f5f5f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{company.name}</span>
          {company.ticker && <span style={{ fontSize: 10, fontWeight: 700, color: '#818cf8', background: 'rgba(99,102,241,0.12)', borderRadius: 5, padding: '2px 6px', fontFamily: 'monospace', flexShrink: 0 }}>{company.ticker}</span>}
          {company.is_tracked && <Bell style={{ width: 12, height: 12, color: '#e8470a', flexShrink: 0 }} />}
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#666' }}>
          {company.sector && <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{company.sector}</span>}
          <span style={{ flexShrink: 0 }}>{filings.length} filing{filings.length !== 1 ? 's' : ''}</span>
          {completed > 0 && <span style={{ color: '#34d399', flexShrink: 0 }}>{completed} processed</span>}
        </div>
      </div>
      <div style={{ flexShrink: 0, textAlign: 'right' }}>
        {latest
          ? <><StatusPill status={latest.status} /><p style={{ fontSize: 10, color: '#666', marginTop: 4, fontFamily: 'monospace' }}>FY{latest.fiscal_year}</p></>
          : <span style={{ fontSize: 11, color: '#666' }}>No reports</span>
        }
      </div>
      <ChevronRight style={{ width: 16, height: 16, color: '#555', flexShrink: 0, transition: 'color 0.15s' }} className="group-hover:!text-orange-500" />
    </Link>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  // ALL HOOKS MUST BE AT THE TOP - BEFORE ANY CONDITIONALS
  const { data: companies = [], isLoading: lCo } = useQuery({ queryKey: ['companies'], queryFn: getCompanies, refetchInterval: 30000 })
  const { data: allFilings = [], isLoading: lFi } = useQuery({ 
    queryKey: ['filings-all'], 
    queryFn: () => getFilings(), 
    refetchInterval: (data) => {
      // Faster refresh if there are processing filings
      if (!data || !Array.isArray(data)) return 30000
      const hasProcessing = data.some(f => f.status === 'processing' || f.status === 'pending')
      return hasProcessing ? 5000 : 30000 // 5s when processing, 30s otherwise
    }
  })
  
  const isMobile = useIsMobile()
  const [selectedCompany, setSelectedCompany] = useState('all')
  
  // State for chart company selection (max 3 companies)
  const [selectedChartCompanies, setSelectedChartCompanies] = useState([])
  
  // Initialize selected chart companies (first 3 alphabetically with completed filings)
  useEffect(() => {
    if (companies.length > 0 && allFilings.length > 0 && selectedChartCompanies.length === 0) {
      const companiesWithData = companies
        .filter(c => allFilings.some(f => f.company_id === c.id && f.status === 'completed'))
        .sort((a, b) => a.name.localeCompare(b.name))
        .slice(0, 3)
      setSelectedChartCompanies(companiesWithData.map(c => c.id))
    }
  }, [companies, allFilings, selectedChartCompanies.length])
  
  // Fetch KPIs for companies to display real financial data
  const { data: companyKPIs = {} } = useQuery({
    queryKey: ['dashboard-kpis', selectedChartCompanies],
    queryFn: async () => {
      const companiesForChart = companies.filter(c => selectedChartCompanies.includes(c.id))
      
      const kpiData = {}
      
      for (const company of companiesForChart) {
        const companyFilings = allFilings.filter(f => 
          f.company_id === company.id && f.status === 'completed'
        ).sort((a, b) => b.fiscal_year - a.fiscal_year)
        
        if (companyFilings.length > 0) {
          const latestFiling = companyFilings[0]
          try {
            const kpis = await getKPIs(latestFiling.id)
            
            // Extract key financial metrics
            const revenueKPI = kpis.find(k => 
              k.name?.toLowerCase().includes('total revenue') ||
              k.name?.toLowerCase().includes('revenue from operations')
            )
            const profitKPI = kpis.find(k => 
              k.name?.toLowerCase().includes('profit after tax') ||
              k.name?.toLowerCase().includes('net profit') ||
              k.name?.toLowerCase().includes('pat')
            )
            
            // Calculate expenses as revenue - profit (if both available)
            const revenue = revenueKPI?.value || 0
            const profit = profitKPI?.value || 0
            const expenses = revenue > 0 && profit !== 0 ? revenue - profit : 0
            
            kpiData[company.id] = {
              revenue: parseFloat(revenue),
              profit: parseFloat(profit),
              expenses: parseFloat(expenses)
            }
          } catch (e) {
            console.error(`Failed to fetch KPIs for ${company.name}:`, e)
            kpiData[company.id] = { revenue: 0, profit: 0, expenses: 0 }
          }
        }
      }
      
      return kpiData
    },
    enabled: companies.length > 0 && selectedChartCompanies.length > 0,
    staleTime: 60000, // Cache for 1 minute
  })
  
  // Fetch real risks from completed filings
  const { data: allRisks = [] } = useQuery({
    queryKey: ['dashboard-risks'],
    queryFn: async () => {
      const completedFilings = allFilings.filter(f => f.status === 'completed').slice(0, 5)
      const risks = []
      
      for (const filing of completedFilings) {
        try {
          const filingRisks = await getRisks(filing.id)
          const company = companies.find(c => c.id === filing.company_id)
          
          // Add company name and date to each risk
          filingRisks.forEach(risk => {
            risks.push({
              company: company?.name || 'Unknown',
              risk: risk.description,
              severity: risk.severity,
              date: new Date(filing.created_at).toLocaleString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                hour: 'numeric', 
                minute: '2-digit' 
              })
            })
          })
        } catch (e) {
          console.error(`Failed to fetch risks for filing ${filing.id}:`, e)
        }
      }
      
      // Sort by severity and return top 5
      const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 }
      return risks
        .sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity])
        .slice(0, 5)
    },
    enabled: allFilings.filter(f => f.status === 'completed').length > 0 && companies.length > 0,
    staleTime: 300000, // Cache for 5 minutes
  })

  // Loading state - AFTER all hooks
  if (lCo || lFi) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <Loader2 style={{ width: 24, height: 24, color: '#e8470a', animation: 'spin 1s linear infinite' }} />
    </div>
  )

  const completed = allFilings.filter(f => f.status === 'completed')
  const processing = allFilings.filter(f => f.status === 'processing' || f.status === 'pending')
  const failed = allFilings.filter(f => f.status === 'failed')
  const tracked = companies.filter(c => c.is_tracked)
  
  // Get selected company data for metrics
  const selectedCompanyData = companies.find(c => c.id === selectedCompany)
  const companyName = selectedCompanyData ? selectedCompanyData.name.toUpperCase() : 'PORTFOLIO'
  const kpiPrefix = selectedCompany === 'all' ? 'TOTAL PORTFOLIO' : `${companyName.split(' ')[0]}`
  
  // Calculate dynamic metrics based on selected company
  const getCompanyMetrics = () => {
    if (selectedCompany === 'all') {
      // Portfolio-wide metrics
      const totalCompaniesWithData = companies.filter(c => {
        const companyFilings = allFilings.filter(f => f.company_id === c.id && f.status === 'completed')
        return companyFilings.length > 0
      }).length
      
      // Get latest fiscal year across all filings
      const latestFiscalYear = completed.length > 0 
        ? Math.max(...completed.map(f => f.fiscal_year))
        : new Date().getFullYear()
      
      return {
        revenue: latestFiscalYear > 0 ? `FY${latestFiscalYear}` : 'No data',
        revenueChange: totalCompaniesWithData > 0 ? `${totalCompaniesWithData} companies` : 'Upload reports',
        profitMargin: completed.length > 0 ? 'INR' : '--',
        marginChange: completed.length > 0 ? 'crores' : 'No data',
        alerts: failed.length,
        filings: completed.length
      }
    } else {
      // Company-specific metrics
      const companyFilings = allFilings.filter(f => f.company_id === selectedCompany)
      const companyCompleted = companyFilings.filter(f => f.status === 'completed').sort((a, b) => b.fiscal_year - a.fiscal_year)
      
      if (companyCompleted.length === 0) {
        return {
          revenue: 'No data',
          revenueChange: 'Upload reports',
          profitMargin: '--',
          marginChange: 'No data',
          alerts: companyFilings.filter(f => f.status === 'failed').length,
          filings: 0
        }
      }
      
      const latest = companyCompleted[0]
      const yearsCount = companyCompleted.length
      
      return {
        revenue: `FY${latest.fiscal_year}`,
        revenueChange: yearsCount > 1 ? `${yearsCount} years tracked` : 'First year',
        profitMargin: latest.currency || 'INR',
        marginChange: latest.unit_scale || 'crores',
        alerts: companyFilings.filter(f => f.status === 'failed').length,
        filings: companyCompleted.length
      }
    }
  }

  const metrics = getCompanyMetrics()
  
  // Build chart data from real KPIs (fetched at top of component)
  const financialData = companies
    .filter(c => selectedChartCompanies.includes(c.id))
    .map(company => {
    const kpis = companyKPIs[company.id]
    return {
      name: company.name.split(' ')[0],
      revenue: kpis?.revenue || 0,
      expenses: kpis?.expenses || 0,
      profit: kpis?.profit || 0
    }
  }).filter(d => d.revenue > 0 || d.profit > 0) // Only show companies with data

  // Use risk feed data (fetched at top of component)
  const riskFeed = allRisks.length > 0 ? allRisks : [
    { company: 'No risks detected', risk: 'Upload and process reports to see AI-generated risk alerts', severity: 'medium', date: 'N/A' }
  ]

  const byCompany = {}
  for (const f of allFilings) { if (!byCompany[f.company_id]) byCompany[f.company_id] = []; byCompany[f.company_id].push(f) }
  const sorted = [...companies].sort((a, b) => {
    if (a.is_tracked !== b.is_tracked) return b.is_tracked - a.is_tracked
    return Math.max(...(byCompany[b.id]?.map(f => f.fiscal_year) || [0])) - Math.max(...(byCompany[a.id]?.map(f => f.fiscal_year) || [0]))
  })

  return (
    <div className="page-container" style={{ position: 'relative', maxWidth: 1600, margin: '0 auto' }}>

        {/* ── Background ── */}
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundImage: 'url(/images/Bakcground.png)',
          backgroundSize: 'cover', backgroundPosition: 'center', backgroundRepeat: 'no-repeat',
          opacity: 0.8, pointerEvents: 'none', zIndex: -2
        }} />
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'linear-gradient(to bottom, rgba(12, 12, 12, 0.3) 0%, rgba(35, 34, 34, 0.5) 100%)',
          pointerEvents: 'none', zIndex: -1
        }} />

        {/* ── Branding Header with Logo ── */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: isMobile ? 12 : 16,
            marginBottom: 12,
            marginLeft: 68
          }}>
            
            <img 
              src="/images/Logo.png" 
              alt="CorpIQ Logo" 
              style={{ 
                width: isMobile ? 48 : 64, 
                height: isMobile ? 48 : 64,
                objectFit: 'contain',
                filter: 'drop-shadow(0 4px 12px rgba(232, 71, 10, 0.3))'
              }} 
            />
            <div>
              <h1 style={{ 
                fontSize: isMobile ? 24 : 32, 
                fontWeight: 700, 
                color: '#F8FAFC', 
                lineHeight: 1.2, 
                letterSpacing: '-0.01em',
                marginBottom: 4,
                background: 'linear-gradient(135deg, #F8FAFC 0%, #CBD5E1 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text'
              }}>
                CorpIQ
              </h1>
              <p style={{ 
                fontSize: isMobile ? 11 : 12, 
                color: '#64748B', 
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.1em'
              }}>
                Corporate Intelligence Platform
              </p>
            </div>
          </div>
          <p style={{ 
            fontSize: 14, 
            color: '#94A3B8', 
            lineHeight: 1.5,
            marginLeft: isMobile ? 60 : 148
          }}>
            Understand and analyze every annual report, instantly.
          </p>
        </div>

      {/* ── Company Selector + Upload Button ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
        <select 
          className="select" 
          value={selectedCompany}
          onChange={(e) => setSelectedCompany(e.target.value)}
          style={{ 
            flex: 1, 
            minWidth: isMobile ? '100%' : 280, 
            maxWidth: 400, 
            height: 48,
            fontSize: 14,
            fontWeight: 600
          }}
        >
          <option value="all">All Companies (Portfolio)</option>
          {companies.map(company => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </select>

        <Link to="/upload" className="btn-primary" style={{ fontSize: 14, height: 48, padding: '0 24px', flexShrink: 0 }}>
          <Upload style={{ width: 18, height: 18 }} /> Upload Report
        </Link>
      </div>

      {/* ── Executive Metrics (4 Cards) ── */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: isMobile ? '1fr' : 'repeat(4, 1fr)',
        gap: 16,
        marginBottom: 32
      }}>
        <MetricCard 
          label={selectedCompany === 'all' ? 'ACTIVE COMPANIES' : 'LATEST FISCAL YEAR'}
          value={metrics.revenue}
          change={metrics.revenueChange}
          trend="0,8 15,5 30,9 45,4 60,6"
          icon={DollarSign}
          color="#34d399"
        />
        <MetricCard 
          label={selectedCompany === 'all' ? 'PORTFOLIO STATUS' : 'CURRENCY'} 
          value={metrics.profitMargin}
          change={metrics.marginChange}
          trend="0,10 15,8 30,12 45,7 60,9"
          icon={TrendingUp}
          color="#818cf8"
        />
        <MetricCard 
          label="HIGH-RISK ALERTS" 
          value={metrics.alerts}
          change="Critical"
          icon={AlertTriangle}
          color="#ef4444"
        />
        <MetricCard 
          label="PROCESSED FILINGS" 
          value={metrics.filings}
          change={processing.length > 0 ? `${processing.length} indexing...` : 'Up to date'}
          icon={FileText}
          color="#fbbf24"
        />
      </div>

      {/* ── Main Content: Chart (60%) + Risk Feed (40%) ── */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: isMobile ? '1fr' : '1.5fr 1fr',
        gap: 20,
        marginBottom: 32
      }}>
        
        {/* Financial Comparison Chart */}
        <div className="card" style={{ minHeight: 400 }}>
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 700, color: '#F8FAFC', marginBottom: 6 }}>Financial Comparison</h2>
                <p style={{ fontSize: 13, color: '#94A3B8' }}>
                  Compare revenue, expenses, and profit across selected companies
                </p>
              </div>
            </div>
            
            {/* Company Selector for Chart */}
            <div style={{ 
              display: 'flex', 
              flexWrap: 'wrap', 
              gap: 8, 
              marginTop: 16,
              padding: '12px',
              background: 'rgba(255, 255, 255, 0.02)',
              borderRadius: 8,
              border: '1px solid rgba(255, 255, 255, 0.05)'
            }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.1em', alignSelf: 'center' }}>
                Select 3 Companies:
              </span>
              {companies
                .filter(c => allFilings.some(f => f.company_id === c.id && f.status === 'completed'))
                .sort((a, b) => a.name.localeCompare(b.name))
                .map(company => {
                  const isSelected = selectedChartCompanies.includes(company.id)
                  return (
                    <button
                      key={company.id}
                      onClick={() => {
                        if (isSelected) {
                          // Deselect
                          setSelectedChartCompanies(prev => prev.filter(id => id !== company.id))
                        } else {
                          // Select (max 3)
                          if (selectedChartCompanies.length < 3) {
                            setSelectedChartCompanies(prev => [...prev, company.id])
                          }
                        }
                      }}
                      disabled={!isSelected && selectedChartCompanies.length >= 3}
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        padding: '6px 12px',
                        borderRadius: 6,
                        border: isSelected ? '1px solid #e8470a' : '1px solid rgba(255, 255, 255, 0.1)',
                        background: isSelected ? 'rgba(232, 71, 10, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                        color: isSelected ? '#e8470a' : '#94A3B8',
                        cursor: (!isSelected && selectedChartCompanies.length >= 3) ? 'not-allowed' : 'pointer',
                        opacity: (!isSelected && selectedChartCompanies.length >= 3) ? 0.5 : 1,
                        transition: 'all 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (!((!isSelected && selectedChartCompanies.length >= 3))) {
                          e.currentTarget.style.borderColor = '#e8470a'
                          e.currentTarget.style.background = 'rgba(232, 71, 10, 0.15)'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'
                        }
                      }}
                    >
                      {company.name.split(' ')[0]}
                      {company.ticker && <span style={{ opacity: 0.6, marginLeft: 4, fontFamily: 'monospace' }}>({company.ticker})</span>}
                    </button>
                  )
                })}
            </div>
          </div>
          
          {financialData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={financialData} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" vertical={false} />
                <XAxis 
                  dataKey="name" 
                  stroke="#94A3B8" 
                  style={{ fontSize: 13, fontWeight: 500 }}
                  tick={{ fill: '#94A3B8' }}
                  axisLine={{ stroke: '#2a2a2a' }}
                  tickLine={false}
                />
                <YAxis 
                  stroke="#94A3B8" 
                  style={{ fontSize: 12 }}
                  tick={{ fill: '#94A3B8' }}
                  axisLine={{ stroke: '#2a2a2a' }}
                  tickLine={false}
                  tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}K`}
                  label={{ 
                    value: 'Amount (₹ in Crores)', 
                    angle: -90, 
                    position: 'insideLeft',
                    style: { fill: '#94A3B8', fontSize: 12, fontWeight: 600 }
                  }}
                />
                <Tooltip 
                  cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                  contentStyle={{ 
                    backgroundColor: '#1a1a1a', 
                    borderColor: 'rgba(255,255,255,0.15)', 
                    color: '#F8FAFC', 
                    borderRadius: '10px',
                    border: '1px solid rgba(255,255,255,0.15)',
                    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
                    padding: '12px'
                  }}
                  itemStyle={{ color: '#e2e8f0', fontSize: 13, padding: '4px 0' }}
                  labelStyle={{ color: '#F8FAFC', fontWeight: 700, marginBottom: 8, fontSize: 14 }}
                  formatter={(value) => [`₹${Number(value).toLocaleString('en-IN')} Cr`, '']}
                />
                <Legend 
                  wrapperStyle={{ fontSize: 12, color: '#94A3B8', paddingTop: 16 }}
                  iconType="circle"
                />
                <Bar dataKey="revenue" fill="#34d399" radius={[8, 8, 0, 0]} name="Revenue" />
                <Bar dataKey="expenses" fill="#f87171" radius={[8, 8, 0, 0]} name="Expenses" />
                <Bar dataKey="profit" fill="#818cf8" radius={[8, 8, 0, 0]} name="Profit" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 300, color: '#666' }}>
              <PieChart style={{ width: 48, height: 48, marginBottom: 12, opacity: 0.5 }} />
              <p style={{ fontSize: 14, color: '#94A3B8' }}>Upload financial reports to see comparison</p>
            </div>
          )}
        </div>

        {/* AI Risk Feed */}
        <div className="card" style={{ minHeight: 400, maxHeight: 520, overflowY: 'auto' }}>
          <div style={{ marginBottom: 20 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: '#F8FAFC', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertTriangle style={{ width: 20, height: 20, color: '#e8470a' }} />
              AI Risk Feed
            </h2>
            <p style={{ fontSize: 13, color: '#64748B' }}>Real-time financial alerts from processed reports</p>
          </div>
          
          {completed.length > 0 ? (
            <div>
              {riskFeed.map((item, idx) => (
                <RiskFeedItem key={idx} {...item} />
              ))}
              <div style={{ textAlign: 'center', marginTop: 20, paddingTop: 16, borderTop: '1px solid #2a2a2a' }}>
                <Link 
                  to="/companies" 
                  style={{ 
                    fontSize: 13, 
                    color: '#e8470a', 
                    textDecoration: 'none', 
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.gap = '10px'}
                  onMouseLeave={(e) => e.currentTarget.style.gap = '6px'}
                >
                  View All Insights →
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 280, color: '#94A3B8', textAlign: 'center', padding: 20 }}>
              <div style={{ 
                width: 64, 
                height: 64, 
                borderRadius: 16, 
                background: 'rgba(148, 163, 184, 0.1)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                marginBottom: 16
              }}>
                <Bell style={{ width: 32, height: 32, opacity: 0.5 }} />
              </div>
              <p style={{ fontSize: 15, color: '#CBD5E1', fontWeight: 600, marginBottom: 8 }}>No reports processed yet</p>
              <p style={{ fontSize: 13, color: '#64748B', lineHeight: 1.5, maxWidth: 280 }}>
                Upload and process reports to see AI-generated risk alerts
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Processing/Failed Alerts ── */}
      {processing.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(129,140,248,0.06)', border: '1px solid rgba(129,140,248,0.18)', borderRadius: 12, padding: '10px 16px', marginBottom: 16 }}>
          <Loader2 style={{ width: 20, height: 20, color: '#818cf8', flexShrink: 0 }} className="animate-spin" />
          <p style={{ fontSize: isMobile ? 12 : 13, color: '#818cf8' }}>
            <strong>{processing.length}</strong> report{processing.length > 1 ? 's' : ''} processing — AI analysis in progress, results appear automatically.
          </p>
        </div>
      )}

      {failed.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.18)', borderRadius: 12, padding: '10px 16px', marginBottom: 16 }}>
          <XCircle style={{ width: 16, height: 16, color: '#f87171', flexShrink: 0 }} />
          <p style={{ fontSize: isMobile ? 12 : 13, color: '#f87171' }}><strong>{failed.length}</strong> report{failed.length > 1 ? 's' : ''} failed.</p>
        </div>
      )}

      {/* ── Company List ── */}
      {companies.length === 0 ? (
        <div style={{ textAlign: 'center', padding: isMobile ? '40px 20px' : '60px 20px', border: '1px dashed #1a1a1a', borderRadius: 16 }}>
          <Upload style={{ width: isMobile ? 48 : 64, height: isMobile ? 48 : 64, color: '#333', margin: '0 auto 16px' }} />
          <p style={{ fontSize: isMobile ? 18 : 20, fontWeight: 700, color: '#f5f5f0', marginBottom: 8 }}>No reports yet</p>
          <p style={{ fontSize: 13, color: '#444', maxWidth: 300, margin: '0 auto 24px', lineHeight: 1.7 }}>
            Upload an annual report PDF — company, year, and currency detected automatically.
          </p>
          <Link to="/upload" className="btn-primary">
            <Upload style={{ width: 14, height: 14 }} /> Upload your first report
          </Link>
        </div>
      ) : (
        <div>
          {tracked.length > 0 && (
            <div style={{ marginBottom: 32 }}>
              <p className="section-heading"><Bell style={{ width: 10, height: 10 }} /> Tracked Companies</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {sorted.filter(c => c.is_tracked).map(c => <CompanyRow key={c.id} company={c} filings={byCompany[c.id] || []} />)}
              </div>
            </div>
          )}
          <div>
            <p className="section-heading"><Building2 style={{ width: 10, height: 10 }} /> All Companies</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {sorted.filter(c => !c.is_tracked).map(c => <CompanyRow key={c.id} company={c} filings={byCompany[c.id] || []} />)}
            </div>
          </div>
        </div>
      )}

      <div className="mobile-hidden" style={{ position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)', width: 700, height: 260, background: 'radial-gradient(ellipse at bottom, rgba(232,71,10,0.05) 0%, transparent 70%)', pointerEvents: 'none', zIndex: 0 }} />
    </div>
  )
}
