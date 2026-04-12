import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { learnerApi, healthApi } from '../services/api';
import { BookOpen, Brain, Target, Zap, AlertTriangle } from 'lucide-react';

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.4, ease: [0.4, 0, 0.2, 1] },
  }),
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [progress, setProgress] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      learnerApi.progress().catch(() => null),
      healthApi.check().catch(() => null),
    ]).then(([p, h]) => {
      setProgress(p);
      setHealth(h);
    }).catch(() => setError('Failed to load dashboard data'));
  }, []);

  const trackedNodes = progress?.tracked_nodes ?? 0;
  const avgMastery = progress?.average_mastery ?? 0;
  const weakNodes = progress?.weak_nodes ?? [];
  const dueReview = progress?.due_for_review ?? [];
  const graphNodes = health?.nodes ?? 0;
  const weakest = weakNodes[0]?.node_id || '';

  const stats = [
    { label: 'Knowledge Nodes', value: graphNodes, icon: Brain, color: '#6c63ff' },
    { label: 'Topics Studied', value: trackedNodes, icon: BookOpen, color: '#00d4aa' },
    { label: 'Avg Mastery', value: `${(avgMastery * 100).toFixed(0)}%`, icon: Target, color: '#ffd700' },
    { label: 'Due for Review', value: dueReview.length, icon: Zap, color: '#ff6b6b' },
  ];

  return (
    <div>
      <div className="page-header">
        <motion.h1 className="page-title" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          Welcome back, {user?.display_name || 'Learner'}
        </motion.h1>
        <p className="page-subtitle">Your adaptive learning overview</p>
      </div>

      {error && <div className="auth-error">{error}</div>}

      {/* Stats Grid */}
      <div className="stats-grid">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            className="stat-card glass-card"
            custom={i}
            initial="hidden"
            animate="visible"
            variants={fadeUp}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div className="stat-label">{stat.label}</div>
                <div className="stat-value">{stat.value}</div>
              </div>
              <div style={{
                width: 40, height: 40, borderRadius: 'var(--radius-md)',
                background: `${stat.color}15`, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}>
                <stat.icon size={20} color={stat.color} />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid-2">
        <motion.div
          className="glass-card action-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: 0.4 }}
        >
          <h2 className="section-title">Quick Actions</h2>
          <p className="section-subtitle">Jump back into active learning in one click.</p>
          <div className="action-row">
            <Link to="/chat" className="btn btn-primary">Start Socratic Chat</Link>
            <Link to="/progress" className="btn btn-ghost">View Progress</Link>
          </div>
        </motion.div>

        <motion.div
          className="glass-card action-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.4 }}
        >
          <h2 className="section-title">Learning Pulse</h2>
          <p className="section-subtitle">A quick read on your current trajectory.</p>
          <div className="pill-row">
            <span className="metric-pill">Avg mastery {(avgMastery * 100).toFixed(0)}%</span>
            <span className="metric-pill">{dueReview.length} reviews due</span>
          </div>
          <div className="pulse-text">
            {weakest
              ? `Next focus: ${weakest}`
              : 'No weak topics yet. Keep exploring new concepts.'}
          </div>
        </motion.div>
      </div>

      {/* Weak Topics */}
      <motion.div
        className="glass-card"
        style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4 }}
      >
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          <AlertTriangle size={18} color="var(--accent-warning)" />
          Weak Topics
        </h2>
        {weakNodes.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            No weak topics yet. Start a Socratic chat session to begin learning!
          </p>
        ) : (
          <div className="node-list">
            {weakNodes.slice(0, 8).map((node) => (
              <div key={node.node_id} className="node-item">
                <span className="node-item-name">{node.node_id}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
                  <div className="mastery-bar" style={{ width: 100 }}>
                    <div
                      className="mastery-bar-fill"
                      style={{
                        width: `${(node.mastery * 100).toFixed(0)}%`,
                        background: node.mastery < 0.3 ? 'var(--accent-warning)' : 'var(--gradient-primary)',
                      }}
                    />
                  </div>
                  <span className="node-item-mastery" style={{
                    color: node.mastery < 0.3 ? 'var(--accent-warning)' : 'var(--accent-secondary)',
                  }}>
                    {(node.mastery * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Due for Review */}
      {dueReview.length > 0 && (
        <motion.div
          className="glass-card"
          style={{ padding: 'var(--space-lg)' }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.4 }}
        >
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <Zap size={18} color="var(--accent-gold)" />
            Due for Review
          </h2>
          <div className="node-list">
            {dueReview.map((node) => (
              <div key={node.node_id} className="node-item">
                <span className="node-item-name">{node.node_id}</span>
                <span className="badge badge-warning">Review Now</span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
