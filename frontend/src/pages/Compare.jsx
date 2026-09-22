import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LineChart, Line, ResponsiveContainer, Legend } from 'recharts'
import { GitCompare, Loader2, FileText, X, BarChart3, LineChart as LineChartIcon } from 'lucide-react'
import { compareFilings, getFilings, getCompanies } from '../services/api'

const COLORS = ['#10b981','#3b82f6','#f97316','#a855f7']

export default function Compare() {
  const [selected, setSelected] = useState([])
  const [type, setType] = useState('bar')

  const { data: companies=[] } = useQuery({ queryKey:['companies'], queryFn:getCompanies })
  const { data: allFilings=[] } = useQuery({ queryKey:['filings-all'], queryFn:()=>getFilings() })
  const completed = allFilings.filter(f=>f.status==='completed')
  const compareMut = useMutation({ mutationFn:()=>compareFilings(selected,null) })

  const getFilingLabel = f => { 
    const c=companies.find(c=>c.id===f.company_id)
    return { company: c?.name || 'Unknown', year: f.fiscal_year, full: `${c?.name || 'Unknown'} FY${f.fiscal_year}` }
  }
  const toggle = id => setSelected(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id])
  const remove = id => setSelected(s=>s.filter(x=>x!==id))

  const selectedFilings = completed.filter(f => selected.includes(f.id))

  // Generate mock financial data based on selected filings
  const generateMockData = () => {
    const allMockData = {
      'Adarsh FY26': { revenue: 52155, margin: 15640, income: 9341, marginPct: '30.0%', debt: '1.2x' },
      'Adani FY26': { revenue: 35486, margin: 10645, income: 7246, marginPct: '30.0%', debt: '1.8x' },
      'Bharti FY26': { revenue: 142000, margin: 42600, income: 20100, marginPct: '30.0%', debt: '2.1x' },
      'Adani FY25': { revenue: 31240, margin: 9372, income: 6240, marginPct: '30.0%', debt: '1.6x' }
    }

    const chartData = []
    const tableData = []
    
    if (selectedFilings.length === 0) return { chartData: [], tableData: [] }

    // Build data for selected filings only
    const metrics = ['Revenue', 'Gross Margin', 'Net Income']
    const tableMetrics = ['Revenue', 'Gross Margin', 'Net Income', 'Debt-to-Equity']

    metrics.forEach((metric, idx) => {
      const row = { metric }
      selectedFilings.forEach(f => {
        const label = getFilingLabel(f)
        const key = label.full
        const mockKey = key // Try to match with mock data
        const data = allMockData[mockKey] || { revenue: 25000, margin: 7500, income: 5000 }
        
        if (idx === 0) row[key] = data.revenue
        else if (idx === 1) row[key] = data.margin
        else if (idx === 2) row[key] = data.income
      })
      chartData.push(row)
    })

    tableMetrics.forEach((metric, idx) => {
      const row = { metric }
      selectedFilings.forEach(f => {
        const label = getFilingLabel(f)
        const key = label.full
        const mockKey = key
        const data = allMockData[mockKey] || { revenue: 25000, margin: 7500, income: 5000, marginPct: '30.0%', debt: '1.5x' }
        
        if (idx === 0) row[key] = `₹${data.revenue.toLocaleString('en-IN')} Cr`
        else if (idx === 1) row[key] = data.marginPct
        else if (idx === 2) row[key] = `₹${data.income.toLocaleString('en-IN')} Cr`
        else if (idx === 3) row[key] = data.debt
      })
      tableData.push(row)
    })

    return { chartData, tableData }
  }

  const mockFinancialData = generateMockData()

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
          maskImage: 'radial-gradient(ellipse 80% 50% at 50% 0%, #000 70%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 50% at 50% 0%, #000 70%, transparent 100%)',
          pointerEvents: 'none',
          zIndex: -10
        }}
      />

      {/* ── Top Glow Effect ── */}
      <div 
        style={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '1000px',
          height: '400px',
          background: 'rgba(255, 85, 0, 0.1)',
          filter: 'blur(120px)',
          borderRadius: '50%',
          pointerEvents: 'none',
          zIndex: -10
        }}
      />

      {/* ── Main Content ── */}
      <div style={{ 
        position: 'relative', 
        zIndex: 1, 
        padding: '40px 32px 80px 96px', 
        maxWidth: '1600px', 
        width: '100%', 
        margin: '0 auto' 
      }}>
        {/* ── Page Header ── */}
        <div style={{ marginBottom: '2rem' }}>
          <p style={{ 
            fontSize: 11, 
            fontWeight: 700, 
            color: '#f97316', 
            textTransform: 'uppercase', 
            letterSpacing: '0.15em', 
            marginBottom: 12 
          }}>
            COMPARISON
          </p>
          <h1 style={{ 
            fontSize: 36, 
            fontWeight: 700, 
            color: '#F1F5F9', 
            letterSpacing: '-0.02em', 
            marginBottom: 8,
            background: 'linear-gradient(135deg, #F8FAFC 0%, #CBD5E1 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>
            Compare Filings
          </h1>
          <p style={{ fontSize: 15, color: '#94A3B8', lineHeight: 1.6 }}>
            Cross-company and cross-year analysis — values normalized to USD
          </p>
        </div>

        {/* ── Glassmorphism Toolbar ── */}
        <div style={{ 
          width: '100%', 
          maxWidth: '100%', 
          margin: '0 auto 2rem', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between', 
          padding: '1rem 1.5rem',
          background: 'rgba(255, 255, 255, 0.02)', 
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.1)', 
          borderRadius: '0.75rem',
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
          flexWrap: 'wrap',
          gap: 16
        }}>
          {/* Left Side - Selected Chips */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', flex: 1 }}>
            {selectedFilings.length > 0 ? (
              selectedFilings.map(f => {
                const label = getFilingLabel(f)
                return (
                  <div 
                    key={f.id} 
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 6, 
                      background: '#18181b', 
                      border: '1px solid rgba(255, 255, 255, 0.1)', 
                      padding: '6px 10px', 
                      borderRadius: '0.5rem',
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#F1F5F9'
                    }}
                  >
                    <FileText style={{ width: 12, height: 12, color: '#f97316' }} />
                    <span>{label.company} FY{label.year}</span>
                    <button
                      onClick={() => remove(f.id)}
                      style={{
                        padding: 2,
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#64748B',
                        display: 'flex',
                        alignItems: 'center',
                        transition: 'color 0.2s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.color = '#f87171'}
                      onMouseLeave={(e) => e.currentTarget.style.color = '#64748B'}
                    >
                      <X style={{ width: 14, height: 14 }} />
                    </button>
                  </div>
                )
              })
            ) : (
              <p style={{ fontSize: 13, color: '#64748B', fontStyle: 'italic' }}>
                Select 2+ filings to compare
              </p>
            )}
          </div>

          {/* Right Side - Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Chart Type Toggle */}
            <div style={{ 
              display: 'flex', 
              background: 'rgba(255, 255, 255, 0.05)', 
              borderRadius: 8, 
              padding: 3, 
              gap: 3,
              border: '1px solid rgba(255, 255, 255, 0.1)'
            }}>
              {[
                { value: 'bar', icon: BarChart3, label: 'BAR' },
                { value: 'line', icon: LineChartIcon, label: 'LINE' }
              ].map(t => (
                <button 
                  key={t.value} 
                  onClick={() => setType(t.value)} 
                  style={{ 
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 11, 
                    fontWeight: 700, 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.06em', 
                    padding: '6px 12px', 
                    borderRadius: 6, 
                    border: 'none', 
                    cursor: 'pointer', 
                    transition: 'all 0.2s', 
                    background: type === t.value ? '#1e293b' : 'transparent', 
                    color: type === t.value ? '#F1F5F9' : '#64748B' 
                  }}
                >
                  <t.icon style={{ width: 14, height: 14 }} />
                  {t.label}
                </button>
              ))}
            </div>

            {/* Compare Button */}
            <button 
              disabled={selected.length < 2 || compareMut.isPending} 
              onClick={() => compareMut.mutate()}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 20px',
                borderRadius: 8,
                border: 'none',
                fontWeight: 700,
                fontSize: 12,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                cursor: selected.length >= 2 && !compareMut.isPending ? 'pointer' : 'not-allowed',
                background: selected.length >= 2 && !compareMut.isPending 
                  ? 'linear-gradient(135deg, #e8470a 0%, #f97316 100%)' 
                  : 'rgba(255, 255, 255, 0.05)',
                color: selected.length >= 2 && !compareMut.isPending ? '#ffffff' : '#64748B',
                boxShadow: selected.length >= 2 && !compareMut.isPending 
                  ? '0 0 20px rgba(255, 85, 0, 0.3)' 
                  : 'none',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                if (selected.length >= 2 && !compareMut.isPending) {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #d13d08 0%, #e8470a 100%)'
                  e.currentTarget.style.boxShadow = '0 0 30px rgba(255, 85, 0, 0.4)'
                }
              }}
              onMouseLeave={(e) => {
                if (selected.length >= 2 && !compareMut.isPending) {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #e8470a 0%, #f97316 100%)'
                  e.currentTarget.style.boxShadow = '0 0 20px rgba(255, 85, 0, 0.3)'
                }
              }}
            >
              {compareMut.isPending ? (
                <>
                  <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} />
                  Comparing...
                </>
              ) : (
                <>
                  <GitCompare style={{ width: 16, height: 16 }} />
                  Compare
                </>
              )}
            </button>
          </div>
        </div>

        {/* ── Filing Selector ── */}
        <div style={{ 
          background: 'rgba(16, 18, 26, 0.8)', 
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.1)', 
          borderRadius: '1rem', 
          padding: '1.5rem',
          marginBottom: '2rem',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)'
        }}>
          <p style={{ 
            fontSize: 11, 
            fontWeight: 700, 
            color: '#64748B', 
            textTransform: 'uppercase', 
            letterSpacing: '0.12em', 
            marginBottom: 16 
          }}>
            Select 2+ filings to compare
          </p>
          {completed.length === 0 ? (
            <p style={{ fontSize: 13, color: '#64748B' }}>No completed filings yet.</p>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {completed.map(f => {
                const label = getFilingLabel(f)
                return (
                  <button 
                    key={f.id} 
                    onClick={() => toggle(f.id)}
                    style={{ 
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: 12, 
                      fontWeight: 600, 
                      padding: '8px 14px', 
                      borderRadius: 8, 
                      border: selected.includes(f.id) ? '1px solid rgba(249, 115, 34, 0.5)' : '1px solid rgba(255, 255, 255, 0.1)', 
                      cursor: 'pointer', 
                      transition: 'all 0.2s',
                      background: selected.includes(f.id) ? 'rgba(249, 115, 34, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                      color: selected.includes(f.id) ? '#f97316' : '#94A3B8'
                    }}
                    onMouseEnter={(e) => {
                      if (!selected.includes(f.id)) {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)'
                        e.currentTarget.style.color = '#F1F5F9'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!selected.includes(f.id)) {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'
                        e.currentTarget.style.color = '#94A3B8'
                      }
                    }}
                  >
                    <FileText style={{ width: 14, height: 14 }} />
                    {label.full}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* ── Row 1: The Visualizer (Chart) ── */}
        {selected.length >= 2 && !compareMut.isPending && (
          <div style={{ 
            background: 'rgba(16, 18, 26, 0.8)', 
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.1)', 
            padding: '2rem', 
            borderRadius: '1rem',
            width: '100%',
            marginBottom: '1.5rem',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)'
          }}>
            <h2 style={{ 
              fontSize: 18, 
              fontWeight: 700, 
              color: '#F1F5F9', 
              marginBottom: 20,
              display: 'flex',
              alignItems: 'center',
              gap: 10
            }}>
              <BarChart3 style={{ width: 20, height: 20, color: '#f97316' }} />
              Financial Comparison
            </h2>
            <ResponsiveContainer width="100%" height={400}>
              {type === 'bar' ? (
                <BarChart data={mockFinancialData.chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis 
                    dataKey="metric" 
                    tick={{ fill: '#94A3B8', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                  />
                  <YAxis 
                    tick={{ fill: '#94A3B8', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                    width={60}
                    tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}K`}
                  />
                  <Tooltip 
                    cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                    contentStyle={{ 
                      backgroundColor: '#10121A', 
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
                    wrapperStyle={{ fontSize: 12, color: '#94A3B8', paddingTop: 20 }}
                    iconType="circle"
                  />
                  {selectedFilings.map((f, idx) => {
                    const label = getFilingLabel(f)
                    return (
                      <Bar 
                        key={f.id} 
                        dataKey={label.full} 
                        fill={COLORS[idx % COLORS.length]} 
                        radius={[6, 6, 0, 0]} 
                      />
                    )
                  })}
                </BarChart>
              ) : (
                <LineChart data={mockFinancialData.chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis 
                    dataKey="metric" 
                    tick={{ fill: '#94A3B8', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                  />
                  <YAxis 
                    tick={{ fill: '#94A3B8', fontSize: 12 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                    width={60}
                    tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}K`}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#10121A', 
                      borderColor: 'rgba(255,255,255,0.15)', 
                      color: '#F8FAFC', 
                      borderRadius: '10px',
                      border: '1px solid rgba(255,255,255,0.15)',
                      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
                      padding: '12px'
                    }}
                    itemStyle={{ color: '#e2e8f0', fontSize: 13 }}
                    labelStyle={{ color: '#F8FAFC', fontWeight: 700, marginBottom: 8 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12, paddingTop: 20 }} />
                  {selectedFilings.map((f, idx) => {
                    const label = getFilingLabel(f)
                    return (
                      <Line 
                        key={f.id}
                        type="monotone" 
                        dataKey={label.full} 
                        stroke={COLORS[idx % COLORS.length]} 
                        strokeWidth={2} 
                        dot={{ r: 4, fill: COLORS[idx % COLORS.length] }} 
                      />
                    )
                  })}
                </LineChart>
              )}
            </ResponsiveContainer>
          </div>
        )}

        {/* ── Row 2: Side-by-Side Data Table ── */}
        {selected.length >= 2 && !compareMut.isPending && (
          <div style={{ 
            background: 'rgba(16, 18, 26, 0.8)', 
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.1)', 
            padding: '2rem', 
            borderRadius: '1rem',
            width: '100%',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
            overflowX: 'auto'
          }}>
            <h2 style={{ 
              fontSize: 18, 
              fontWeight: 700, 
              color: '#F1F5F9', 
              marginBottom: 20,
              display: 'flex',
              alignItems: 'center',
              gap: 10
            }}>
              <FileText style={{ width: 20, height: 20, color: '#f97316' }} />
              Detailed Comparison
            </h2>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid rgba(255, 255, 255, 0.1)' }}>
                  <th style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    fontSize: 11, 
                    fontWeight: 700, 
                    color: '#64748B', 
                    textTransform: 'uppercase', 
                    letterSpacing: '0.08em' 
                  }}>
                    Metric
                  </th>
                  {selectedFilings.map(f => {
                    const label = getFilingLabel(f)
                    return (
                      <th 
                        key={f.id}
                        style={{ 
                          textAlign: 'right', 
                          padding: '12px 16px', 
                          fontSize: 11, 
                          fontWeight: 700, 
                          color: '#64748B', 
                          textTransform: 'uppercase', 
                          letterSpacing: '0.08em' 
                        }}
                      >
                        {label.full}
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {mockFinancialData.tableData.map((row, idx) => (
                  <tr 
                    key={row.metric}
                    style={{ 
                      background: idx % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.02)',
                      transition: 'background 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.02)'}
                  >
                    <td style={{ 
                      padding: '14px 16px', 
                      fontSize: 14, 
                      fontWeight: 600, 
                      color: '#F1F5F9',
                      borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
                    }}>
                      {row.metric}
                    </td>
                    {selectedFilings.map(f => {
                      const label = getFilingLabel(f)
                      return (
                        <td 
                          key={f.id}
                          style={{ 
                            padding: '14px 16px', 
                            fontSize: 14, 
                            fontWeight: 600, 
                            color: '#CBD5E1', 
                            textAlign: 'right',
                            fontFamily: 'JetBrains Mono, monospace',
                            fontVariantNumeric: 'tabular-nums',
                            borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
                          }}
                        >
                          {row[label.full]}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Loading State ── */}
        {compareMut.isPending && (
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center', 
            justifyContent: 'center', 
            padding: '100px 20px', 
            gap: 16
          }}>
            <Loader2 style={{ width: 48, height: 48, color: '#f97316', animation: 'spin 1s linear infinite' }} />
            <p style={{ fontSize: 16, color: '#94A3B8', fontWeight: 600 }}>Running comparison analysis...</p>
          </div>
        )}
      </div>
    </div>
  )
}
