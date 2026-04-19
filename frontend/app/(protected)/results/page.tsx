'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { quizApi } from '@/lib/services/api'
import { QuizResult } from '@/lib/types'
import { motion } from 'framer-motion'
import { CheckCircle2, XCircle, Award, Clock, Target, ArrowRight, Loader2, Brain } from 'lucide-react'

export default function ResultsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const quizId = searchParams.get('id')

  const [result, setResult] = useState<QuizResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (quizId) {
      fetchResult()
    } else {
      router.push('/dashboard')
    }
  }, [quizId])

  const fetchResult = async () => {
    try {
      // Assuming quizApi.history() returns results including the latest one
      // Or we could have a specific getResult endpoint
      const history = await quizApi.history()
      const latest = history.find((h: any) => h.quiz_id === quizId)
      if (latest) {
        setResult(latest)
      } else {
        setError('Quiz result not found.')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch results')
    } finally {
      setLoading(false)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <Loader2 className="animate-spin" size={48} />
    </div>
  )

  if (error) return (
    <div className="glass-card" style={{ padding: 'var(--space-2xl)', textAlign: 'center', maxWidth: 500, margin: '0 auto' }}>
      <XCircle size={48} color="var(--accent-warning)" style={{ marginBottom: 'var(--space-md)' }} />
      <h2 className="section-title">Error</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: 'var(--space-xl)' }}>{error}</p>
      <button type="button" className="btn btn-primary" onClick={() => router.push('/dashboard')}>Back to Dashboard</button>
    </div>
  )

  const score = Math.round((result?.score || 0) * 100)
  const isPassed = score >= 70

  return (
    <div className="main-content">
      <div className="results-container">
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-card score-card"
        >
          <div className="score-header">
            <div className={`pass-badge ${isPassed ? 'pass' : 'fail'}`}>
              {isPassed ? <Award size={24} /> : <CheckCircle2 size={24} />}
              <span>{isPassed ? 'Excellence' : 'Completed'}</span>
            </div>
            <h1 className="score-title">{result?.topic} Quiz</h1>
          </div>

          <div className="score-circle-wrapper">
            <div className={`score-circle ${isPassed ? 'pass' : 'fail'}`}>
              <div className="score-value">{score}%</div>
              <div className="score-label">Final Score</div>
            </div>
          </div>

          <div className="results-stats">
            <div className="res-stat">
              <Clock size={18} />
              <div className="res-stat-info">
                <div className="res-stat-val">{Math.floor(result?.time_taken / 60)}m {result?.time_taken % 60}s</div>
                <div className="res-stat-lab">Time Taken</div>
              </div>
            </div>
            <div className="res-stat">
              <Target size={18} />
              <div className="res-stat-info">
                <div className="res-stat-val">{result?.correct_count} / {result?.total_questions}</div>
                <div className="res-stat-lab">Accuracy</div>
              </div>
            </div>
          </div>
        </motion.div>

        <div className="action-grid">
          <button type="button" className="btn btn-primary btn-lg" onClick={() => router.push('/dashboard')}>
            Dashboard <ArrowRight size={18} />
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => router.push('/chat')}>
            Review with Socratic AI <Brain size={18} />
          </button>
        </div>
      </div>

      <style jsx>{`
        .results-container {
          max-width: 600px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: var(--space-xl);
        }
        .score-card {
          padding: var(--space-2xl);
          text-align: center;
          background: var(--gradient-card);
        }
        .score-header {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-md);
          margin-bottom: var(--space-2xl);
        }
        .pass-badge {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 16px;
          border-radius: 100px;
          font-size: 0.75rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .pass-badge.pass { background: rgba(0, 212, 170, 0.15); color: var(--accent-secondary); }
        .pass-badge.fail { background: rgba(108, 99, 255, 0.15); color: var(--accent-primary-light); }
        .score-title { font-size: 1.5rem; font-weight: 700; color: var(--text-primary); }
        .score-circle-wrapper {
          display: flex;
          justify-content: center;
          margin-bottom: var(--space-2xl);
        }
        .score-circle {
          width: 180px;
          height: 180px;
          border-radius: 50%;
          border: 8px solid var(--bg-glass);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          position: relative;
        }
        .score-circle.pass { border-color: var(--accent-secondary); box-shadow: 0 0 30px rgba(0, 212, 170, 0.2); }
        .score-circle.fail { border-color: var(--accent-primary); box-shadow: 0 0 30px rgba(108, 99, 255, 0.2); }
        .score-value { font-size: 3rem; font-weight: 800; color: white; line-height: 1; }
        .score-label { font-size: 0.8125rem; color: var(--text-muted); font-weight: 600; margin-top: 4px; }
        .results-stats {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--space-md);
          padding-top: var(--space-xl);
          border-top: 1px solid var(--border-subtle);
        }
        .res-stat {
          display: flex;
          align-items: center;
          gap: var(--space-md);
          padding: var(--space-md);
          background: var(--bg-glass);
          border-radius: var(--radius-md);
        }
        .res-stat-info { text-align: left; }
        .res-stat-val { font-size: 1.125rem; font-weight: 700; color: var(--text-primary); }
        .res-stat-lab { font-size: 0.75rem; color: var(--text-muted); }
        .action-grid { display: grid; grid-template-columns: 1fr; gap: var(--space-md); }
      `}</style>
    </div>
  )
}
