'use client'

import React, { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import dynamic from 'next/dynamic'

const Sidebar = dynamic(() => import('@/components/Sidebar').then(mod => mod.default), {
  ssr: false,
  loading: () => null
})
import { Menu } from 'lucide-react'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const pathname = usePathname()

  // Don't show sidebar on auth pages
  const isAuthPage = pathname.startsWith('/auth')

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      if (!mobile) setMobileOpen(false)
    }
    handleResize()
    setMounted(true)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  if (isAuthPage) {
    return <>{children}</>
  }

  // Prevent hydration mismatch by only rendering after mounting
  if (!mounted) {
    return <div className="app-layout"><main className="main-content">{children}</main></div>
  }

  const sidebarWidth = collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)'

  return (
    <div className="app-layout">
      <Sidebar 
        collapsed={collapsed} 
        onToggle={() => setCollapsed(!collapsed)} 
        isMobile={isMobile}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />
      
      {/* Mobile Header */}
      {isMobile && (
        <header className="mobile-header">
          <button
            type="button"
            className="mobile-menu-btn"
            title="Open menu"
            aria-label="Open menu"
            onClick={() => setMobileOpen(true)} 
            style={styles.mobileMenuBtn as React.CSSProperties}
          >
            <Menu size={24} />
          </button>
          <div style={styles.mobileBrand as React.CSSProperties}>AI Tutor</div>
        </header>
      )}

      <main 
        className="main-content"
        style={{
          marginLeft: isMobile ? 0 : sidebarWidth,
          maxWidth: isMobile ? '100vw' : `calc(100vw - ${sidebarWidth})`,
          paddingTop: isMobile ? 'calc(var(--space-xl) + 60px)' : 'var(--space-xl)',
          transition: 'all var(--transition-normal)',
          flex: 1,
        } as React.CSSProperties}
      >
        {children}
      </main>
    </div>
  )
}

const styles = {
  mobileHeader: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    height: 60,
    background: 'var(--bg-secondary)',
    borderBottom: '1px solid var(--border-subtle)',
    display: 'flex',
    alignItems: 'center',
    padding: '0 var(--space-lg)',
    gap: 'var(--space-md)',
    zIndex: 900,
    backdropFilter: 'blur(10px)',
  },
  mobileMenuBtn: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-primary)',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 'var(--space-xs)',
  },
  mobileBrand: {
    fontSize: '1.125rem',
    fontWeight: 700,
    background: 'var(--gradient-primary)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  }
}
