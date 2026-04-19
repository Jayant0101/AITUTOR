'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { User, SidebarProps } from '@/lib/types'
import { LayoutDashboard, MessageSquare, BarChart3, LogOut, Brain, ChevronLeft, ChevronRight, CheckSquare } from 'lucide-react'

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/todos', label: 'Todos', icon: CheckSquare },
  { path: '/chat', label: 'Socratic Chat', icon: MessageSquare },
  { path: '/progress', label: 'Progress', icon: BarChart3 },
]

export default function Sidebar({ collapsed, onToggle, isMobile, mobileOpen, onMobileClose }: SidebarProps) {
  const [user, setUser] = useState<User | null>(null)
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
    }
    getUser()
  }, [])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/auth/login')
    router.refresh()
  }

  const sidebarStyle = {
    ...styles.sidebar,
    width: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
    transform: isMobile ? (mobileOpen ? 'translateX(0)' : 'translateX(-100%)') : 'none',
    transition: 'all var(--transition-normal)',
  }

  return (
    <>
      {/* Mobile Overlay */}
      {isMobile && mobileOpen && (
        <div 
          style={styles.overlay as any} 
          onClick={onMobileClose}
        />
      )}

      <aside style={sidebarStyle as any}>
        {/* Toggle Button - Desktop Only */}
        {!isMobile && (
          <button 
            type="button"
            onClick={onToggle} 
            style={styles.toggleBtn as any}
            title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            aria-label={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        )}

        {/* Brand */}
        <div style={{ ...styles.brand, padding: collapsed ? '0 var(--space-sm)' : '0 var(--space-lg)', justifyContent: collapsed ? 'center' : 'flex-start' } as any}>
          <div style={styles.brandIcon as any}><Brain size={24} /></div>
          {!collapsed && (
            <div style={{ opacity: 1, transition: 'opacity var(--transition-normal)' }}>
              <div style={styles.brandName as any}>AI Tutor</div>
              <div style={styles.brandTag as any}>Learning Assistant</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav style={styles.nav as any}>
          {navItems.map(({ path, label, icon: Icon }) => {
            const isActive = pathname === path
            return (
              <Link 
                key={path} 
                href={path} 
                style={{ textDecoration: 'none' }}
                onClick={isMobile ? onMobileClose : undefined}
              >
                <div style={{ 
                  ...styles.navItem, 
                  ...(isActive ? styles.navItemActive : {}),
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  padding: collapsed ? 'var(--space-md) 0' : 'var(--space-md) var(--space-md)',
                } as any}>
                  <Icon size={18} style={{ opacity: isActive ? 1 : 0.5 }} />
                  {!collapsed && <span>{label}</span>}
                  {isActive && <div style={styles.activeBar as any} />}
                </div>
              </Link>
            )
          })}
        </nav>

        {/* User Footer */}
        <div style={{ ...styles.footer, padding: collapsed ? 'var(--space-md) var(--space-sm)' : 'var(--space-md) var(--space-lg)', justifyContent: collapsed ? 'center' : 'space-between' } as any}>
          <div style={styles.userInfo as any}>
            <div style={styles.avatar as any}>{(user?.user_metadata?.display_name || user?.email || 'U')[0].toUpperCase()}</div>
            {!collapsed && <div style={styles.userName as any}>{user?.user_metadata?.display_name || user?.email?.split('@')[0] || 'User'}</div>}
          </div>
          {!collapsed && (
            <button 
              type="button"
              onClick={handleLogout} 
              style={styles.logoutBtn as any} 
              title="Logout"
              aria-label="Logout"
            >
              <LogOut size={16} />
            </button>
          )}
        </div>
      </aside>
    </>
  )
}

const styles = {
  sidebar: {
    position: 'fixed',
    top: 0,
    left: 0,
    height: '100vh',
    background: 'var(--gradient-sidebar)',
    borderRight: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 1000,
    padding: 'var(--space-lg) 0',
  },
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.5)',
    backdropFilter: 'blur(4px)',
    zIndex: 999,
  },
  toggleBtn: {
    position: 'absolute',
    right: -12,
    top: 32,
    width: 24,
    height: 24,
    borderRadius: '50%',
    background: 'var(--accent-primary)',
    border: 'none',
    color: 'white',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    boxShadow: 'var(--shadow-card)',
    zIndex: 1001,
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-md)',
    marginBottom: 'var(--space-2xl)',
    overflow: 'hidden',
  },
  brandIcon: {
    width: 40,
    height: 40,
    borderRadius: 'var(--radius-md)',
    background: 'var(--gradient-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'white',
    boxShadow: 'var(--shadow-glow)',
    flexShrink: 0,
  },
  brandName: {
    fontSize: '1.125rem',
    fontWeight: 700,
    letterSpacing: '-0.02em',
    color: 'var(--text-primary)',
    whiteSpace: 'nowrap',
  },
  brandTag: {
    fontSize: '0.6875rem',
    color: 'var(--text-muted)',
    fontWeight: 500,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    whiteSpace: 'nowrap',
  },
  nav: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    padding: '0 var(--space-sm)',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-md)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--text-secondary)',
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
    position: 'relative',
    overflow: 'hidden',
  },
  navItemActive: {
    background: 'rgba(108, 99, 255, 0.1)',
    color: 'var(--accent-primary-light)',
    fontWeight: 600,
  },
  activeBar: {
    position: 'absolute',
    left: 0,
    top: '50%',
    transform: 'translateY(-50%)',
    width: 3,
    height: 20,
    borderRadius: '0 3px 3px 0',
    background: 'var(--accent-primary)',
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    borderTop: '1px solid var(--border-subtle)',
  },
  userInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-sm)',
    overflow: 'hidden',
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 'var(--radius-full)',
    background: 'var(--gradient-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '0.75rem',
    fontWeight: 700,
    color: 'white',
    flexShrink: 0,
  },
  userName: {
    fontSize: '0.8125rem',
    fontWeight: 500,
    color: 'var(--text-secondary)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  logoutBtn: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    padding: 'var(--space-sm)',
    borderRadius: 'var(--radius-sm)',
    display: 'flex',
    alignItems: 'center',
    transition: 'all var(--transition-fast)',
  },
}
