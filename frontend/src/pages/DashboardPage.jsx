import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { learnerApi, healthApi, feedbackApi } from '../services/api';
import { BookOpen, Brain, Target, Zap, AlertTriangle, Send, Star, CheckCircle2, TrendingUp } from 'lucide-react';

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
  const [analytics, setAnalytics] = useState(null);
  const [userAnalytics, setUserAnalytics] = useState(null);
  const [error, setError] = useState('');
  
  // Feedback state
  const [feedback, setFeedback] = useState('');
  const [rating, setRating] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!user?.user_id) return;
    
    Promise.all([
      learnerApi.progress().catch(() => null),
      healthApi.check().catch(() => null),
      healthApi.analytics().catch(() => null),
      healthApi.userAnalytics(user.user_id).catch(() => null),
    ]).then(([p, h, a, ua]) => {
      setProgress(p);
      setHealth(h);
      setAnalytics(a?.data);
      setUserAnalytics(ua?.data);
    }).catch(() => setError('Failed to load dashboard data'));
  }, [user?.user_id]);

  const handleFeedbackSubmit = async (e) => {
    e.preventDefault();
    if (!feedback.trim()) return;
    setSubmitting(true);
    try {
      await feedbackApi.submit(feedback, rating);
      setSubmitted(true);
      setFeedback('');
      setRating(0);
      setTimeout(() => setSubmitted(false), 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

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

      {/* Learning Insights (Phase 4) */}
      {userAnalytics && (
        <div className="grid-2" style={{ marginBottom: 'var(--space-lg)' }}>
          <motion.div
            className="glass-card"
            style={{ padding: 'var(--space-lg)' }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.4 }}
          >
            <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
              <TrendingUp size={18} color="var(--accent-primary)" />
              Score History
            </h2>
            {userAnalytics.score_history?.length > 0 ? (
              <div style={{ height: 120, display: 'flex', alignItems: 'flex-end', gap: 4, paddingBottom: 20 }}>
                {userAnalytics.score_history.slice(-15).map((h, i) => (
                  <div 
                    key={i} 
                    style={{ 
                      flex: 1, 
                      height: `${h.percentage}%`, 
                      background: 'var(--gradient-primary)',
                      borderRadius: '2px 2px 0 0',
                      minWidth: 4
                    }} 
                    title={`${h.percentage}% on ${new Date(h.taken_at).toLocaleDateString()}`}
                  />
                ))}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No quiz history yet.</p>
            )}
          </motion.div>

          <motion.div
            className="glass-card"
            style={{ padding: 'var(--space-lg)' }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55, duration: 0.4 }}
          >
            <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
              <Target size={18} color="var(--accent-secondary)" />
              Top Weak Topics
            </h2>
            {userAnalytics.weak_topics?.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {userAnalytics.weak_topics.slice(0, 5).map((t, i) => (
                  <span key={i} className="metric-pill" style={{ background: 'rgba(255, 107, 107, 0.1)', color: '#ff6b6b', border: '1px solid rgba(255, 107, 107, 0.2)' }}>
                    {t.topic} ({t.mastery_score.toFixed(0)}%)
                  </span>
                ))}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No weak topics identified yet.</p>
            )}
          </motion.div>
        </div>
      )}

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
              <Link 
                to={`/quiz?topic=${encodeURIComponent(node.node_id)}&difficulty=medium`}
                key={node.node_id} 
                className="node-item"
                style={{ textDecoration: 'none', cursor: 'pointer' }}
                title="Start a quiz on this topic"
              >
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
              </Link>
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
              <Link 
                to={`/quiz?topic=${encodeURIComponent(node.node_id)}&difficulty=hard`}
                key={node.node_id} 
                className="node-item"
                style={{ textDecoration: 'none', cursor: 'pointer' }}
              >
                <span className="node-item-name">{node.node_id}</span>
                <span className="badge badge-warning">Review Now</span>
              </Link>
            ))}
          </div>
        </motion.div>
      )}

      {/* Analytics & Feedback (Phase 4 & 5) */}
      <div className="grid-2" style={{ marginTop: 'var(--space-lg)' }}>
        {/* Operational Stats (Visible to User in Soft Launch) */}
        <motion.div
          className="glass-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.4 }}
        >
          <h2 className="section-title">System Pulse</h2>
          <p className="section-subtitle">Real-time stats from the SocratiQ network.</p>
          <div className="stats-mini-grid">
            <div className="mini-stat">
              <span className="mini-stat-label">Total Users</span>
              <span className="mini-stat-value">{analytics?.total_users || 0}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Quizzes Taken</span>
              <span className="mini-stat-value">{analytics?.total_quizzes_taken || 0}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Active (24h)</span>
              <span className="mini-stat-value">{analytics?.active_users_24h || 0}</span>
            </div>
          </div>
        </motion.div>

        {/* User Feedback Form */}
        <motion.div
          className="glass-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.4 }}
        >
          <h2 className="section-title">Share Feedback</h2>
          <p className="section-subtitle">Help us improve the learning experience.</p>
          
          <AnimatePresence mode="wait">
            {submitted ? (
              <motion.div 
                key="success"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-sm)', padding: 'var(--space-md)' }}
              >
                <CheckCircle2 size={40} color="var(--accent-secondary)" />
                <span style={{ fontWeight: 600 }}>Feedback Received!</span>
              </motion.div>
            ) : (
              <motion.form key="form" onSubmit={handleFeedbackSubmit} className="feedback-form">
                <div className="rating-row">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setRating(s)}
                      className={`rating-star ${rating >= s ? 'active' : ''}`}
                    >
                      <Star size={18} fill={rating >= s ? "currentColor" : "none"} />
                    </button>
                  ))}
                </div>
                <textarea
                  placeholder="What can we improve?"
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  className="feedback-textarea"
                />
                <button 
                  type="submit" 
                  disabled={submitting || !feedback.trim()} 
                  className="btn btn-primary btn-sm"
                  style={{ alignSelf: 'flex-end', display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}
                >
                  {submitting ? 'Sending...' : <><Send size={14} /> Send Feedback</>}
                </button>
              </motion.form>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
}
