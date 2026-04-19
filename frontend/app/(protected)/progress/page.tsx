'use client'

import { useState, useEffect } from 'react'
import { learnerApi } from '@/lib/services/api'
import { motion } from 'framer-motion'
import { Brain, TrendingUp, Target, Award, Calendar, Loader2 } from 'lucide-react'

export default function ProgressPage() {
  const [progress, setProgress] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchProgress()
  }, [])

  const fetchProgress = async () => {
    try {
      const data = await learnerApi.progress()
      setProgress(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <Loader2 className="animate-spin" size={32} />
    </div>
  )

  const stats = [
    { label: 'Mastery Rate', value: `${Math.round((progress?.mastery_avg || 0) * 100)}%`, icon: Target, color: '#00d4aa' },
    { label: 'Topics Explored', value: progress?.topics_count || 0, icon: Brain, color: '#6c63ff' },
    { label: 'Learning Gain', value: `+${Math.round((progress?.learning_gain || 0) * 100)}%`, icon: TrendingUp, color: '#ffd700' },
    { label: 'Study Streak', value: `${progress?.streak || 0} Days`, icon: Award, color: '#ff6b6b' },
  ]

  return (
    <div className="main-content">
      <header className="page-header">
        <h1 className="page-title">Learning Progress</h1>
        <p className="page-subtitle">Detailed analytics of your knowledge mastery and learning journey.</p>
      </header>

      <div className="stats-grid">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            className="stat-card glass-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <div className="stat-icon" style={{ background: `${stat.color}15`, color: stat.color }}>
              <stat.icon size={20} />
            </div>
            <div className="stat-label">{stat.label}</div>
            <div className="stat-value">{stat.value}</div>
          </motion.div>
        ))}
      </div>

      <div className="grid-2">
        <div className="glass-card topic-card">
          <h2 className="section-title">Topic Mastery</h2>
          <div className="topic-list">
            {progress?.topics?.map((topic: any) => (
              <div key={topic.name} className="topic-item">
                <div className="topic-info">
                  <span className="topic-name">{topic.name}</span>
                  <span className="topic-percent">{Math.round(topic.mastery * 100)}%</span>
                </div>
                <div className="mastery-bar">
                  <div className="mastery-bar-fill" style={{ width: `${topic.mastery * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card activity-card">
          <h2 className="section-title">Recent Activity</h2>
          <div className="activity-list">
            {progress?.recent_activity?.map((activity: any, i: number) => (
              <div key={i} className="activity-item">
                <div className="activity-icon">
                  <Calendar size={14} />
                </div>
                <div className="activity-details">
                  <div className="activity-text">{activity.action}</div>
                  <div className="activity-time">{activity.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: var(--space-lg);
          margin-bottom: var(--space-2xl);
        }
        .stat-card {
          padding: var(--space-xl);
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: var(--space-sm);
        }
        .stat-icon {
          width: 48px;
          height: 48px;
          border-radius: 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 8px;
        }
        .stat-label {
          font-size: 0.8125rem;
          color: var(--text-muted);
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .stat-value {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
        }
        .topic-card, .activity-card {
          padding: var(--space-xl);
        }
        .topic-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-lg);
          margin-top: var(--space-xl);
        }
        .topic-info {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          font-size: 0.875rem;
        }
        .topic-name { font-weight: 600; color: var(--text-primary); }
        .topic-percent { color: var(--accent-secondary); font-weight: 700; }
        .activity-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
          margin-top: var(--space-xl);
        }
        .activity-item {
          display: flex;
          gap: var(--space-md);
          padding-bottom: var(--space-md);
          border-bottom: 1px solid var(--border-subtle);
        }
        .activity-icon {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: var(--bg-glass);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-muted);
          flex-shrink: 0;
        }
        .activity-text { font-size: 0.875rem; font-weight: 500; }
        .activity-time { font-size: 0.75rem; color: var(--text-muted); margin-top: 2px; }
      `}</style>
    </div>
  )
}
