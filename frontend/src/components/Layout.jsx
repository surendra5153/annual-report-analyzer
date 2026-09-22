import { Outlet, Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Upload, GitCompare, MessageSquare, Building2, Menu, X } from 'lucide-react'
import { useState, useEffect } from 'react'

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

// ── Floating Slide-Out Sidebar Component ─────────────────────────────────────
function FloatingSidebar({ isOpen, onClose }) {
  const location = useLocation()
  const isMobile = useIsMobile()
  
  const navItems = [
    { label: 'Dashboard', path: '/', icon: LayoutDashboard },
    { label: 'Companies', path: '/companies', icon: Building2 },
    { label: 'Upload Report', path: '/upload', icon: Upload },
    { label: 'Compare Filings', path: '/compare', icon: GitCompare },
    { label: 'AI Chat', path: '/chat', icon: MessageSquare }
  ]
  
  return (
    <>
      {/* Backdrop Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity duration-300"
          onClick={onClose}
          style={{ animation: 'fadeIn 0.3s ease-out' }}
        />
      )}
      
      {/* Slide-Out Drawer */}
      <div 
        className={`fixed top-0 left-0 h-full w-64 z-50 transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          background: 'linear-gradient(180deg, #08090C 0%, #10121A 100%)',
          borderRight: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '4px 0 24px rgba(0, 0, 0, 0.5)'
        }}
      >
        {/* Sidebar Header */}
        <div style={{
          padding: '20px 20px 24px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <img 
              src="/images/Logo.png" 
              alt="CorpIQ" 
              style={{ 
                width: 40, 
                height: 40,
                objectFit: 'contain',
                filter: 'drop-shadow(0 2px 8px rgba(232, 71, 10, 0.4))'
              }} 
            />
            <div>
              <h2 style={{ 
                fontSize: 18, 
                fontWeight: 700, 
                color: '#F8FAFC',
                lineHeight: 1,
                marginBottom: 2
              }}>
                CorpIQ
              </h2>
              <p style={{ 
                fontSize: 9, 
                color: '#64748B',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.08em'
              }}>
                Intelligence
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 8,
              border: 'none',
              background: 'transparent',
              color: '#94A3B8',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
              e.currentTarget.style.color = '#F8FAFC'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = '#94A3B8'
            }}
          >
            <X style={{ width: 20, height: 20 }} />
          </button>
        </div>
        
        {/* Navigation Links */}
        <nav style={{ padding: '24px 16px' }}>
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            const Icon = item.icon
            
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onClose}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '12px 16px',
                  marginBottom: 6,
                  borderRadius: 10,
                  textDecoration: 'none',
                  fontSize: 14,
                  fontWeight: 600,
                  transition: 'all 0.2s ease',
                  background: isActive ? 'rgba(232, 71, 10, 0.12)' : 'transparent',
                  color: isActive ? '#f97316' : '#94A3B8',
                  border: isActive ? '1px solid rgba(232, 71, 10, 0.2)' : '1px solid transparent'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                    e.currentTarget.style.color = '#F8FAFC'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = '#94A3B8'
                  }
                }}
              >
                <Icon style={{ 
                  width: 20, 
                  height: 20,
                  opacity: isActive ? 1 : 0.8
                }} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>
        
        {/* Sidebar Footer */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '20px',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          background: 'rgba(0, 0, 0, 0.2)'
        }}>
          <p style={{ 
            fontSize: 11, 
            color: '#64748B', 
            textAlign: 'center',
            lineHeight: 1.5
          }}>
            Corporate Intelligence Platform<br/>
            <span style={{ color: '#475569' }}>v1.0.0</span>
          </p>
        </div>
      </div>
    </>
  )
}

export default function Layout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  return (
    <>
      {/* ── Floating Slide-Out Sidebar ── */}
      <FloatingSidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      
      {/* ── Main Content ── */}
      <div style={{ minHeight: '100vh', background: '#232222' }}>
        {/* Hamburger Menu Button - Fixed Position */}
        <button
          onClick={() => setIsSidebarOpen(true)}
          style={{
            position: 'fixed',
            top: 20,
            left: 20,
            width: 48,
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 12,
            border: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(35, 34, 34, 0.8)',
            backdropFilter: 'blur(12px)',
            color: '#94A3B8',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            zIndex: 30,
            flexShrink: 0,
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'
            e.currentTarget.style.color = '#F8FAFC'
            e.currentTarget.style.borderColor = 'rgba(232, 71, 10, 0.3)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(35, 34, 34, 0.8)'
            e.currentTarget.style.color = '#94A3B8'
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)'
          }}
        >
          <Menu style={{ width: 24, height: 24 }} />
        </button>

        <main>
          <Outlet />
        </main>
      </div>
    </>
  )
}
