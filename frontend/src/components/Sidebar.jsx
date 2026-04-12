import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LayoutDashboard, MessageSquare, BarChart3, LogOut, Brain } from 'lucide-react';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/chat', label: 'Socratic Chat', icon: MessageSquare },
  { path: '/progress', label: 'Progress', icon: BarChart3 },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <aside style={styles.sidebar}>
      {/* Brand */}
      <div style={styles.brand}>
        <div style={styles.brandIcon}><Brain size={24} /></div>
        <div>
          <div style={styles.brandName}>SocratiQ</div>
          <div style={styles.brandTag}>AI Tutor</div>
        </div>
      </div>

      {/* Nav */}
      <nav style={styles.nav}>
        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path;
          return (
            <NavLink key={path} to={path} style={{ textDecoration: 'none' }}>
              <div style={{ ...styles.navItem, ...(isActive ? styles.navItemActive : {}) }}>
                <Icon size={18} style={{ opacity: isActive ? 1 : 0.5 }} />
                <span>{label}</span>
                {isActive && <div style={styles.activeBar} />}
              </div>
            </NavLink>
          );
        })}
      </nav>

      {/* User Footer */}
      <div style={styles.footer}>
        <div style={styles.userInfo}>
          <div style={styles.avatar}>{(user?.display_name || user?.email || 'U')[0].toUpperCase()}</div>
          <div style={styles.userName}>{user?.display_name || user?.email || 'User'}</div>
        </div>
        <button onClick={logout} style={styles.logoutBtn} title="Logout">
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}

const styles = {
  sidebar: {
    position: 'fixed',
    top: 0,
    left: 0,
    width: 'var(--sidebar-width)',
    height: '100vh',
    background: 'var(--gradient-sidebar)',
    borderRight: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 100,
    padding: 'var(--space-lg) 0',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-md)',
    padding: '0 var(--space-lg)',
    marginBottom: 'var(--space-2xl)',
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
  },
  brandName: {
    fontSize: '1.125rem',
    fontWeight: 700,
    letterSpacing: '-0.02em',
    color: 'var(--text-primary)',
  },
  brandTag: {
    fontSize: '0.6875rem',
    color: 'var(--text-muted)',
    fontWeight: 500,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
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
    padding: 'var(--space-md) var(--space-md)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--text-secondary)',
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all var(--transition-fast)',
    position: 'relative',
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
    justifyContent: 'space-between',
    padding: 'var(--space-md) var(--space-lg)',
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
};
