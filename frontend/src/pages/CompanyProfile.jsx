import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { FileText, Bell, BellOff, Upload, Loader2, TrendingUp, ChevronRight, ArrowLeft, Trash2, AlertTriangle, MessageSquare, DollarSign, PieChart, Shield } from 'lucide-react'
import toast from 'react-hot-toast'
import { getCompanyProfile, updateCompany, deleteCompany } from '../services/api'
import { StatusBadge } from '../components/StatusBadge'

const COLORS = ['#10b981','#3b82f6','#f97316','#a855f7','#f472b6','#60a5fa']

const FEATURED = ['Total Revenue','Revenue from Operations','Profit After Tax (PAT) / Net Profit','EBITDA','Operating Profit (EBIT)','Total Assets','Return on Equity (ROE) %','Earnings Per Share (EPS)']

// Executive KPI Card Component
function ExecutiveKPI({ label, value, change, icon: Icon, color = '#10b981', year }) {
  return (
    <div className="bg-[#0A0B0F] backdrop-blur-md border border-white/[0.08] p-5 rounded-xl hover:border-orange-500/30 transition-all duration-300 group relative overflow-hidden">
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      
      <div className="relative">
        <div className="flex justify-between items-start mb-3">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{label}</p>
          {Icon && <Icon className="w-4 h-4 text-slate-600" />}
        </div>
        <p className="text-3xl font-bold font-mono tabular-nums mb-2" style={{ color }}>
          {value}
        </p>
        <div className="flex items-center justify-between">
          {change && (
            <p className="text-xs text-slate-500 font-medium">{change}</p>
          )}
          {year && (
            <span className="text-[10px] font-bold text-orange-500 bg-orange-500/10 px-2 py-0.5 rounded uppercase tracking-wider">
              FY{year}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// AI Insight Bullet Point
function InsightBullet({ text, type = 'neutral' }) {
  const colors = {
    positive: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/5',
    negative: 'text-red-400 border-red-500/30 bg-red-500/5',
    neutral: 'text-blue-400 border-blue-500/30 bg-blue-500/5',
    warning: 'text-amber-400 border-amber-500/30 bg-amber-500/5'
  }
  
  return (
    <div className={`flex gap-3 p-3 rounded-lg border-l-2 ${colors[type]} backdrop-blur-sm`}>
      <div className={`w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0 ${colors[type].split(' ')[0].replace('text-', 'bg-')}`} />
      <p className="text-sm text-slate-300 leading-relaxed">{text}</p>
    </div>
  )
}

export default function CompanyProfile() {
  const { companyId } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({ queryKey:['company-profile',companyId], queryFn:()=>getCompanyProfile(companyId) })
  const toggleTrack = useMutation({ mutationFn:c=>updateCompany(c.id,{...c,is_tracked:!c.is_tracked}), onSuccess:()=>{qc.invalidateQueries(['company-profile',companyId]);qc.invalidateQueries(['companies'])} })
  const deleteMut = useMutation({ mutationFn:()=>deleteCompany(companyId), onSuccess:()=>{qc.invalidateQueries(['companies']);toast.success('Deleted');navigate('/')} })

  if (isLoading) return (
    <div className="flex items-center justify-center h-screen">
      <Loader2 className="w-8 h-8 text-orange-500 animate-spin" />
    </div>
  )
  
  if (!data) return null

  const { company, filings, kpi_trends, peers } = data
  const completed = filings.filter(f=>f.status==='completed')
  const latestFiling = completed.sort((a,b) => b.fiscal_year - a.fiscal_year)[0]
  
  // Extract key financial metrics from the latest filing
  const getKPIValue = (kpiName) => {
    const trend = kpi_trends[kpiName]
    if (!trend || trend.length === 0) return null
    const latest = [...trend].sort((a,b) => b.fiscal_year - a.fiscal_year)[0]
    return latest
  }
  
  const totalRevenue = getKPIValue('Total Revenue') || getKPIValue('Revenue from Operations')
  const profitAfterTax = getKPIValue('Profit After Tax (PAT) / Net Profit')
  const totalAssets = getKPIValue('Total Assets')
  
  // Calculate risk score based on risk and flag counts
  const calculateRiskScore = () => {
    if (!latestFiling) return { label: 'No Data', color: '#64748B', level: 'unknown' }
    const totalRisks = latestFiling.risk_count + latestFiling.flag_count
    if (totalRisks === 0) return { label: 'Low Risk', color: '#10b981', level: 'low' }
    if (totalRisks <= 3) return { label: 'Medium Risk', color: '#f59e0b', level: 'medium' }
    return { label: 'High Risk', color: '#ef4444', level: 'high' }
  }
  
  const riskScore = calculateRiskScore()
  
  // Prepare data for unified financial chart
  const prepareFinancialChartData = () => {
    const revenueData = kpi_trends['Total Revenue'] || kpi_trends['Revenue from Operations'] || []
    const profitData = kpi_trends['Profit After Tax (PAT) / Net Profit'] || []
    
    const years = [...new Set([...revenueData.map(d => d.fiscal_year), ...profitData.map(d => d.fiscal_year)])].sort()
    
    return years.map(year => {
      const revenue = revenueData.find(d => d.fiscal_year === year)
      const profit = profitData.find(d => d.fiscal_year === year)
      return {
        year: `FY${year}`,
        Revenue: revenue?.value || 0,
        'Net Profit': profit?.value || 0
      }
    })
  }
  
  const financialChartData = prepareFinancialChartData()
  const shouldUseBarChart = financialChartData.length <= 2
  
  // Prepare detailed financial metrics table
  const prepareMetricsTable = () => {
    const metrics = ['Total Revenue', 'EBITDA', 'Operating Profit (EBIT)', 'Profit After Tax (PAT) / Net Profit', 'Total Assets', 'Finance Costs']
    return metrics.map(metric => {
      const trend = kpi_trends[metric]
      if (!trend || trend.length === 0) return null
      const latest = [...trend].sort((a,b) => b.fiscal_year - a.fiscal_year)[0]
      return {
        metric,
        value: latest.value,
        currency: latest.currency,
        unit: latest.unit_scale,
        year: latest.fiscal_year
      }
    }).filter(Boolean)
  }
  
  const metricsTable = prepareMetricsTable()
  
  // Generate AI insights
  const generateInsights = () => {
    if (!latestFiling || completed.length === 0) {
      return [
        { text: 'Upload and process annual reports to see AI-generated insights', type: 'neutral' }
      ]
    }
    
    const insights = []
    
    // Revenue insight
    if (totalRevenue) {
      const unit = totalRevenue.unit_scale || 'Cr'
      const formattedValue = `₹${Number(totalRevenue.value).toLocaleString('en-IN')} ${unit}`
      insights.push({
        text: `Total revenue of ${formattedValue} reported in FY${totalRevenue.fiscal_year}`,
        type: 'neutral'
      })
    }
    
    // Profitability insight
    if (profitAfterTax && totalRevenue) {
      const margin = ((profitAfterTax.value / totalRevenue.value) * 100).toFixed(1)
      const type = margin > 15 ? 'positive' : margin > 5 ? 'neutral' : 'warning'
      insights.push({
        text: `Net profit margin of ${margin}% indicates ${margin > 15 ? 'strong' : margin > 5 ? 'moderate' : 'low'} profitability`,
        type
      })
    }
    
    // Risk insight
    if (latestFiling.risk_count > 0) {
      insights.push({
        text: `${latestFiling.risk_count} risk factor${latestFiling.risk_count > 1 ? 's' : ''} identified in latest filing`,
        type: latestFiling.risk_count > 3 ? 'negative' : 'warning'
      })
    }
    
    // KPI coverage insight
    const kpiCount = Object.keys(kpi_trends).length
    if (kpiCount > 0) {
      insights.push({
        text: `${kpiCount} key performance indicators tracked across ${completed.length} fiscal year${completed.length > 1 ? 's' : ''}`,
        type: 'positive'
      })
    }
    
    return insights.length > 0 ? insights : [
      { text: 'Processing financial data to generate insights...', type: 'neutral' }
    ]
  }
  
  const aiInsights = generateInsights()

  return (
    <div className="bg-[#08090C] relative min-h-screen overflow-hidden">
      {/* 3D Grid Background */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff0a_1px,transparent_1px),linear-gradient(to_bottom,#ffffff0a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none -z-10" />
      
      {/* Orange Glow */}
      <div className="absolute top-0 left-1/4 w-[800px] h-[500px] bg-orange-500/10 blur-[150px] rounded-full pointer-events-none -z-10" />
      
      {/* Main Content */}
      <div className="relative w-full max-w-[90rem] mx-auto px-6 py-10">
        
        {/* Breadcrumb - Fixed pl-16 to avoid hamburger overlap */}
        <div className="pl-16 mb-8">
          <Link 
            to="/" 
            className="inline-flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-orange-500 transition-colors uppercase tracking-wider"
          >
            <ArrowLeft className="w-3 h-3" />
            Back to Dashboard
          </Link>
        </div>

        {/* Executive Header */}
        <div className="flex items-start justify-between mb-8 pl-16">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center text-2xl font-bold text-white shadow-lg shadow-orange-500/20">
              {(company.ticker || company.name).slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl font-bold text-slate-100 tracking-tight">
                  {company.name.toUpperCase()}
                </h1>
                {company.ticker && (
                  <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-3 py-1 rounded-md font-mono">
                    {company.ticker}
                  </span>
                )}
              </div>
              {(company.sector || company.industry) && (
                <p className="text-sm text-slate-400 mb-1">
                  {company.sector}{company.industry && ` · ${company.industry}`}
                </p>
              )}
              {company.description && (
                <p className="text-xs text-slate-500 max-w-2xl leading-relaxed">
                  {company.description}
                </p>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <Link 
              to="/upload" 
              className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-500 to-orange-600 text-white text-xs font-bold rounded-lg hover:from-orange-600 hover:to-orange-700 transition-all shadow-lg shadow-orange-500/20"
            >
              <Upload className="w-4 h-4" />
              Upload
            </Link>
            <button 
              onClick={() => toggleTrack.mutate(company)}
              className="p-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-all"
              title={company.is_tracked ? 'Stop tracking' : 'Track company'}
            >
              {company.is_tracked ? (
                <Bell className="w-4 h-4 text-orange-500" />
              ) : (
                <BellOff className="w-4 h-4 text-slate-400" />
              )}
            </button>
            <button 
              onClick={() => {
                if (confirm(`Delete ${company.name}?`)) deleteMut.mutate()
              }}
              className="p-2.5 bg-white/5 hover:bg-red-500/20 border border-white/10 hover:border-red-500/30 rounded-lg transition-all"
            >
              <Trash2 className="w-4 h-4 text-red-400" />
            </button>
          </div>
        </div>

        {/* Executive KPI Row */}
        <div className="grid grid-cols-4 gap-4 mb-8 pl-16">
          <ExecutiveKPI 
            label="Total Revenue"
            value={totalRevenue ? `₹${Number(totalRevenue.value).toLocaleString('en-IN')} ${totalRevenue.unit_scale || 'Cr'}` : 'No data'}
            change={totalRevenue ? totalRevenue.currency : 'Upload reports'}
            year={totalRevenue?.fiscal_year}
            icon={DollarSign}
            color="#10b981"
          />
          <ExecutiveKPI 
            label="Profit After Tax"
            value={profitAfterTax ? `₹${Number(profitAfterTax.value).toLocaleString('en-IN')} ${profitAfterTax.unit_scale || 'Cr'}` : 'No data'}
            change={profitAfterTax ? profitAfterTax.currency : 'Upload reports'}
            year={profitAfterTax?.fiscal_year}
            icon={TrendingUp}
            color="#3b82f6"
          />
          <ExecutiveKPI 
            label="Total Assets"
            value={totalAssets ? `₹${Number(totalAssets.value).toLocaleString('en-IN')} ${totalAssets.unit_scale || 'Cr'}` : 'No data'}
            change={totalAssets ? totalAssets.currency : 'Upload reports'}
            year={totalAssets?.fiscal_year}
            icon={PieChart}
            color="#a855f7"
          />
          <ExecutiveKPI 
            label="AI Risk Score"
            value={riskScore.label}
            change={latestFiling ? `${latestFiling.risk_count + latestFiling.flag_count} items flagged` : 'No filings'}
            year={latestFiling?.fiscal_year}
            icon={Shield}
            color={riskScore.color}
          />
        </div>

        {/* Two-Column Layout */}
        <div className="grid grid-cols-12 gap-6 pl-16">
          
          {/* Left Column - Financial Visualizer */}
          <div className="col-span-8 space-y-6">
            
            {/* Main Financial Chart */}
            <div className="bg-[#0A0B0F]/80 backdrop-blur-xl border border-white/[0.08] rounded-2xl p-6 shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500/20 to-orange-600/20 border border-orange-500/30 flex items-center justify-center">
                    <TrendingUp className="w-5 h-5 text-orange-500" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-slate-100">Revenue vs Net Profit</h2>
                    <p className="text-xs text-slate-500 mt-0.5">Financial performance trend</p>
                  </div>
                </div>
                {latestFiling && (
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 font-mono bg-slate-800/50 px-3 py-1.5 rounded-lg border border-slate-700/50">
                      {latestFiling.currency} {totalRevenue?.unit_scale || 'Cr'}
                    </span>
                    <span className="text-xs font-bold text-orange-500 bg-orange-500/10 px-3 py-1.5 rounded-lg border border-orange-500/20">
                      Latest: FY{latestFiling.fiscal_year}
                    </span>
                  </div>
                )}
              </div>
              
              {financialChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={320}>
                  {shouldUseBarChart ? (
                    <BarChart data={financialChartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                      <defs>
                        <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10b981" stopOpacity={0.8} />
                          <stop offset="100%" stopColor="#10b981" stopOpacity={0.3} />
                        </linearGradient>
                        <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.8} />
                          <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.3} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                      <XAxis 
                        dataKey="year" 
                        tick={{ fill: '#64748B', fontSize: 12, fontWeight: 600 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
                        tickLine={false}
                      />
                      <YAxis 
                        tick={{ fill: '#64748B', fontSize: 12 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
                        tickLine={false}
                        width={70}
                        tickFormatter={(value) => value >= 1000 ? `₹${(value/1000).toFixed(0)}K` : `₹${value}`}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: '#0F1419', 
                          borderColor: 'rgba(249,115,34,0.3)', 
                          color: '#F8FAFC', 
                          borderRadius: '12px',
                          border: '1px solid rgba(249,115,34,0.3)',
                          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8)',
                          padding: '12px 16px'
                        }}
                        itemStyle={{ color: '#e2e8f0', fontSize: 13, fontWeight: 600, padding: '4px 0' }}
                        labelStyle={{ color: '#F8FAFC', fontWeight: 700, marginBottom: 8, fontSize: 14 }}
                        formatter={(value) => [`₹${Number(value).toLocaleString('en-IN')}`, '']}
                      />
                      <Legend 
                        wrapperStyle={{ fontSize: 12, color: '#94A3B8', paddingTop: 16, fontWeight: 600 }}
                        iconType="circle"
                      />
                      <Bar dataKey="Revenue" fill="url(#revenueGradient)" radius={[8, 8, 0, 0]} />
                      <Bar dataKey="Net Profit" fill="url(#profitGradient)" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  ) : (
                    <LineChart data={financialChartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                      <defs>
                        <linearGradient id="revenueLineGlow" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="profitLineGlow" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                      <XAxis 
                        dataKey="year" 
                        tick={{ fill: '#64748B', fontSize: 12, fontWeight: 600 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
                        tickLine={false}
                      />
                      <YAxis 
                        tick={{ fill: '#64748B', fontSize: 12 }}
                        axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
                        tickLine={false}
                        width={70}
                        tickFormatter={(value) => value >= 1000 ? `₹${(value/1000).toFixed(0)}K` : `₹${value}`}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: '#0F1419', 
                          borderColor: 'rgba(249,115,34,0.3)', 
                          color: '#F8FAFC', 
                          borderRadius: '12px',
                          border: '1px solid rgba(249,115,34,0.3)',
                          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.8)',
                          padding: '12px 16px'
                        }}
                        itemStyle={{ color: '#e2e8f0', fontSize: 13, fontWeight: 600 }}
                        labelStyle={{ color: '#F8FAFC', fontWeight: 700, marginBottom: 8 }}
                        formatter={(value) => [`₹${Number(value).toLocaleString('en-IN')}`, '']}
                      />
                      <Legend wrapperStyle={{ fontSize: 12, color: '#94A3B8', paddingTop: 16, fontWeight: 600 }} />
                      <Line 
                        type="monotone" 
                        dataKey="Revenue" 
                        stroke="#10b981" 
                        strokeWidth={3} 
                        dot={{ r: 5, fill: '#10b981', strokeWidth: 2, stroke: '#0A0B0F' }} 
                        activeDot={{ r: 7, fill: '#10b981', strokeWidth: 3, stroke: '#0A0B0F' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="Net Profit" 
                        stroke="#3b82f6" 
                        strokeWidth={3} 
                        dot={{ r: 5, fill: '#3b82f6', strokeWidth: 2, stroke: '#0A0B0F' }} 
                        activeDot={{ r: 7, fill: '#3b82f6', strokeWidth: 3, stroke: '#0A0B0F' }}
                      />
                    </LineChart>
                  )}
                </ResponsiveContainer>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-slate-500">
                  <TrendingUp className="w-12 h-12 mb-4 opacity-20" />
                  <p className="text-sm">No financial data available yet</p>
                  <p className="text-xs mt-1">Upload annual reports to see trends</p>
                </div>
              )}
            </div>

            {/* Financial Metrics Table */}
            {metricsTable.length > 0 && (
              <div className="bg-[#0A0B0F]/80 backdrop-blur-xl border border-white/[0.08] rounded-2xl p-6 shadow-2xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                    Extracted Financial Metrics
                  </h3>
                  {metricsTable[0] && (
                    <span className="text-xs font-bold text-orange-500 bg-orange-500/10 px-3 py-1 rounded-lg border border-orange-500/20">
                      FY{metricsTable[0].year}
                    </span>
                  )}
                </div>
                <div className="space-y-1">
                  {metricsTable.map((metric, idx) => (
                    <div 
                      key={idx}
                      className="flex justify-between items-center p-4 bg-slate-900/30 hover:bg-slate-800/40 rounded-lg transition-all border border-transparent hover:border-slate-700/50"
                    >
                      <span className="text-sm text-slate-300 font-medium">{metric.metric}</span>
                      <span className="text-sm text-slate-100 font-mono font-semibold tabular-nums">
                        {metric.currency} {Number(metric.value).toLocaleString('en-IN')} {metric.unit}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Filing History */}
            <div className="bg-[#0A0B0F]/80 backdrop-blur-xl border border-white/[0.08] rounded-2xl p-6 shadow-2xl">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded-lg bg-slate-800/50 border border-slate-700/50 flex items-center justify-center">
                  <FileText className="w-4 h-4 text-slate-400" />
                </div>
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                  Filing History
                </h3>
              </div>
              
              {filings.length === 0 ? (
                <div className="text-center py-8 text-slate-500 text-sm">
                  No filings uploaded yet
                </div>
              ) : (
                <div className="space-y-2">
                  {[...filings].reverse().map(filing => (
                    <Link
                      key={filing.filing_id}
                      to={`/filings/${filing.filing_id}`}
                      className="flex items-center justify-between p-4 bg-slate-900/30 hover:bg-slate-800/50 rounded-lg border border-transparent hover:border-orange-500/30 transition-all group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center group-hover:bg-orange-500/20 transition-colors">
                          <FileText className="w-4 h-4 text-orange-500" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-slate-200">FY {filing.fiscal_year}</span>
                            <StatusBadge status={filing.status} />
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5 max-w-md truncate">{filing.file_name}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-xs font-mono text-slate-500 font-semibold">
                        {filing.status === 'completed' && (
                          <>
                            <span className="text-indigo-400 bg-indigo-500/10 px-2 py-1 rounded">{filing.kpi_count} KPIs</span>
                            <span className="text-red-400 bg-red-500/10 px-2 py-1 rounded">{filing.risk_count} risks</span>
                          </>
                        )}
                        <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-orange-500 transition-colors" />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column - AI Insights Sidebar */}
          <div className="col-span-4">
            <div className="sticky top-6 bg-[#0A0B0F]/90 backdrop-blur-xl border border-white/[0.08] rounded-2xl p-6 space-y-6 shadow-2xl">
              
              {/* Header */}
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500/20 to-red-600/20 border border-orange-500/30 flex items-center justify-center">
                    <AlertTriangle className="w-5 h-5 text-orange-500" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-slate-100">AI Financial Highlights</h2>
                    <p className="text-xs text-slate-500">
                      {latestFiling ? `Based on FY${latestFiling.fiscal_year} analysis` : 'Upload reports to see insights'}
                    </p>
                  </div>
                </div>
              </div>

              {/* AI Insights */}
              <div className="space-y-3">
                {aiInsights.map((insight, idx) => (
                  <InsightBullet key={idx} text={insight.text} type={insight.type} />
                ))}
              </div>

              {/* Chat CTA */}
              {completed.length > 0 && (
                <Link
                  to={`/chat?company=${company.id}`}
                  className="flex items-center justify-center gap-2 w-full px-4 py-3.5 bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white text-sm font-bold rounded-lg transition-all shadow-lg shadow-orange-500/30 hover:shadow-orange-500/40 hover:scale-[1.02]"
                >
                  <MessageSquare className="w-4 h-4" />
                  Chat with this Report
                </Link>
              )}

              {/* Peer Companies */}
              {peers.length > 0 && (
                <div className="pt-6 border-t border-white/[0.08]">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <div className="w-1 h-3 bg-gradient-to-b from-indigo-500 to-purple-500 rounded-full" />
                    Similar Companies
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {peers.slice(0, 4).map(peer => (
                      <span 
                        key={peer.company_id}
                        className="text-xs font-semibold text-indigo-400 bg-indigo-500/10 px-3 py-2 rounded-lg border border-indigo-500/20 hover:bg-indigo-500/20 transition-colors cursor-pointer"
                      >
                        {peer.name}
                        <span className="ml-1.5 opacity-50 text-[10px]">{(peer.score * 100).toFixed(0)}%</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="pt-6 border-t border-white/[0.08] grid grid-cols-2 gap-3">
                <div className="text-center p-4 bg-slate-900/30 rounded-xl border border-slate-800/50">
                  <p className="text-3xl font-bold text-slate-100 font-mono tabular-nums">{filings.length}</p>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1.5 font-bold">Total Filings</p>
                </div>
                <div className="text-center p-4 bg-emerald-500/5 rounded-xl border border-emerald-500/20">
                  <p className="text-3xl font-bold text-emerald-400 font-mono tabular-nums">{completed.length}</p>
                  <p className="text-[10px] text-emerald-500/70 uppercase tracking-wider mt-1.5 font-bold">Processed</p>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
