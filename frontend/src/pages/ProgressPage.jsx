import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { learnerApi } from '../services/api';
import { TrendingUp, Award, Clock } from 'lucide-react';

export default function ProgressPage() {
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    learnerApi.progress()
      .then(setProgress)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <div className="loading-dots"><span></span><span></span><span></span></div>
      </div>
    );
  }

  const nodes = progress?.nodes ?? [];
  const avgMastery = progress?.average_mastery ?? 0;
  const totalTracked = progress?.tracked_nodes ?? 0;
  const masteredCount = nodes.filter((n) => n.mastery >= 0.8).length;
  const learningCount = nodes.filter((n) => n.mastery >= 0.5 && n.mastery < 0.8).length;
  const needsWorkCount = nodes.filter((n) => n.mastery < 0.5).length;

  // Sort nodes by mastery descending for the leaderboard view
  const sortedNodes = [...nodes].sort((a, b) => b.mastery - a.mastery);

  const getMasteryColor = (m) => {
    if (m >= 0.8) return 'var(--accent-secondary)';
    if (m >= 0.5) return 'var(--accent-gold)';
    return 'var(--accent-warning)';
  };

  const getMasteryBadge = (m) => {
    if (m >= 0.8) return { text: 'Mastered', cls: 'badge-success' };
    if (m >= 0.5) return { text: 'Learning', cls: 'badge-warning' };
    return { text: 'Needs Work', cls: 'badge-danger' };
  };

  return (
    <div>
      <div className="page-header">
        <motion.h1 className="page-title" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          Learning Progress
        </motion.h1>
        <p className="page-subtitle">Your concept mastery overview across all studied topics</p>
      </div>

      {/* Summary stats */}
      <div className="stats-grid" style={{ marginBottom: 'var(--space-2xl)' }}>
        <motion.div className="stat-card glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-label">Total Topics</div>
              <div className="stat-value">{totalTracked}</div>
            </div>
            <div style={{ width: 40, height: 40, borderRadius: 'var(--radius-md)', background: 'rgba(108, 99, 255, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <TrendingUp size={20} color="var(--accent-primary)" />
            </div>
          </div>
        </motion.div>

        <motion.div className="stat-card glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-label">Average Mastery</div>
              <div className="stat-value">{(avgMastery * 100).toFixed(0)}%</div>
            </div>
            <div style={{ width: 40, height: 40, borderRadius: 'var(--radius-md)', background: 'rgba(0, 212, 170, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Award size={20} color="var(--accent-secondary)" />
            </div>
          </div>
        </motion.div>

        <motion.div className="stat-card glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-label">Mastered (&ge;80%)</div>
              <div className="stat-value">{masteredCount}</div>
            </div>
            <div style={{ width: 40, height: 40, borderRadius: 'var(--radius-md)', background: 'rgba(255, 215, 0, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Clock size={20} color="var(--accent-gold)" />
            </div>
          </div>
        </motion.div>
      </div>

      <motion.div
        className="glass-card"
        style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
      >
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
          Mastery Distribution
        </h2>
        <div className="pill-row">
          <span className="metric-pill">Mastered: {masteredCount}</span>
          <span className="metric-pill">Learning: {learningCount}</span>
          <span className="metric-pill">Needs work: {needsWorkCount}</span>
        </div>
      </motion.div>

      {/* Node List */}
      <motion.div
        className="glass-card"
        style={{ padding: 'var(--space-lg)' }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
          All Studied Topics
        </h2>

        {sortedNodes.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            No topics studied yet. Head to the Socratic Chat to begin!
          </p>
        ) : (
          <div className="node-list">
            {sortedNodes.map((node, i) => {
              const { text: badgeText, cls: badgeCls } = getMasteryBadge(node.mastery);
              return (
                <motion.div
                  key={node.node_id}
                  className="node-item"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + i * 0.03 }}
                >
                  <div style={{ flex: 1 }}>
                    <span className="node-item-name">{node.node_id}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginTop: 'var(--space-xs)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      <span>Attempts: {node.attempts}</span>
                      <span>-</span>
                      <span>Correct: {node.correct_attempts}</span>
                      <span>-</span>
                      <span>Trend: {(node.trend * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
                    <div className="mastery-bar" style={{ width: 120 }}>
                      <div
                        className="mastery-bar-fill"
                        style={{
                          width: `${(node.mastery * 100).toFixed(0)}%`,
                          background: `linear-gradient(90deg, ${getMasteryColor(node.mastery)}, ${getMasteryColor(node.mastery)}88)`,
                        }}
                      />
                    </div>
                    <span className="node-item-mastery" style={{ color: getMasteryColor(node.mastery), minWidth: 40, textAlign: 'right' }}>
                      {(node.mastery * 100).toFixed(0)}%
                    </span>
                    <span className={`badge ${badgeCls}`}>{badgeText}</span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>
    </div>
  );
}

