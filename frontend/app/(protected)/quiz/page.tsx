'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { quizApi } from '@/lib/services/api'
import { QuizData } from '@/lib/types'
import { motion, AnimatePresence } from 'framer-motion'
import { Clock, Loader2, AlertCircle, CheckCircle2, ChevronRight, Brain } from 'lucide-react'

export default function QuizPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const topic = searchParams.get('topic') || 'General'
  const difficulty = searchParams.get('difficulty') || 'medium'

  const [quizData, setQuizData] = useState<QuizData | null>(null)
  const [currentIdx, setCurrentIdx] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [timeLeft, setTimeLeft] = useState(600)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [startTime, setStartTime] = useState(Date.now())
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('aitutor_active_quiz')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        if (parsed.topic === topic && parsed.difficulty === difficulty) {
          setQuizData(parsed.quizData)
          setAnswers(parsed.answers || {})
          const elapsed = Math.floor((Date.now() - parsed.startTime) / 1000)
          const totalAllocated = parsed.quizData.questions?.length * 60 || 600
          setTimeLeft(Math.max(0, totalAllocated - elapsed))
          setStartTime(parsed.startTime)
          setLoading(false)
          return
        }
      } catch (err) {}
    }
    fetchQuiz()
  }, [topic, difficulty])

  useEffect(() => {
    if (quizData && !submitting) {
      localStorage.setItem('aitutor_active_quiz', JSON.stringify({
        topic,
        difficulty,
        quizData,
        answers,
        startTime
      }))
    }
  }, [quizData, answers, startTime, topic, difficulty, submitting])

  useEffect(() => {
    if (timeLeft <= 0 && quizData && !submitting) {
      handleSubmit()
    }
    const timer = setInterval(() => {
      setTimeLeft(prev => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [timeLeft, quizData, submitting])

  const fetchQuiz = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await quizApi.generate(topic, difficulty)
      setQuizData(data)
      setStartTime(Date.now())
      setTimeLeft(data.questions?.length * 60 || 600)
    } catch (err: any) {
      setError(err.message || 'Failed to generate quiz')
    } finally {
      setLoading(false)
    }
  }

  const handleSelect = (optionKey: string) => {
    setAnswers(prev => ({ ...prev, [currentIdx]: optionKey }))
  }

  const handleSubmit = async () => {
    if (submitting) return
    setSubmitting(true)
    const timeTaken = Math.floor((Date.now() - startTime) / 1000)
    const answerArray = Object.entries(answers).map(([idx, val]) => ({
      question_index: parseInt(idx),
      selected_option: val
    }))

    try {
      const result = await quizApi.submit(quizData.quiz_id, answerArray, timeTaken)
      localStorage.removeItem('aitutor_active_quiz')
      router.push(`/results?id=${quizData.quiz_id}`)
    } catch (err: any) {
      setError(err.message || 'Failed to submit quiz')
      setSubmitting(false)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <Loader2 className="animate-spin" size={48} />
      <p style={{ marginTop: 'var(--space-md)', color: 'var(--text-muted)' }}>Generating your adaptive quiz...</p>
    </div>
  )

  if (error) return (
    <div className="glass-card" style={{ padding: 'var(--space-2xl)', textAlign: 'center', maxWidth: 500, margin: '0 auto' }}>
      <AlertCircle size={48} color="var(--accent-warning)" style={{ marginBottom: 'var(--space-md)' }} />
      <h2 className="section-title">Quiz Error</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: 'var(--space-xl)' }}>{error}</p>
      <button type="button" className="btn btn-primary" onClick={fetchQuiz}>Try Again</button>
    </div>
  )

  const currentQuestion = quizData.questions[currentIdx]
  const progress = ((currentIdx + 1) / quizData.questions.length) * 100

  return (
    <div className="main-content">
      <div className="quiz-layout">
        <header className="quiz-header">
          <div className="quiz-info">
            <h1 className="quiz-topic">{topic} Quiz</h1>
            <div className="quiz-difficulty">{difficulty}</div>
          </div>
          <div className={`quiz-timer ${timeLeft < 60 ? 'warning' : ''}`}>
            <Clock size={18} />
            <span>{Math.floor(timeLeft / 60)}:{String(timeLeft % 60).padStart(2, '0')}</span>
          </div>
        </header>

        <div className="progress-container">
          <div className="progress-bar-track">
            <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="progress-text">Question {currentIdx + 1} of {quizData.questions.length}</div>
        </div>

        <main className="question-container">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentIdx}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="question-card glass-card"
            >
              <h2 className="question-text">{currentQuestion.question}</h2>
              <div className="options-grid">
                {Object.entries(currentQuestion.options).map(([key, value]: [string, any]) => (
                  <button
                    key={key}
                    type="button"
                    className={`option-btn ${answers[currentIdx] === key ? 'selected' : ''}`}
                    onClick={() => handleSelect(key)}
                  >
                    <div className="option-key">{key}</div>
                    <div className="option-value">{value}</div>
                  </button>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        </main>

        <footer className="quiz-footer">
          <button 
            type="button"
            className="btn btn-secondary" 
            disabled={currentIdx === 0}
            onClick={() => setCurrentIdx(prev => prev - 1)}
          >
            Previous
          </button>
          {currentIdx === quizData.questions.length - 1 ? (
            <button 
              type="button"
              className="btn btn-primary btn-lg" 
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? <Loader2 className="animate-spin" size={20} /> : 'Submit Quiz'}
            </button>
          ) : (
            <button 
              type="button"
              className="btn btn-primary" 
              onClick={() => setCurrentIdx(prev => prev + 1)}
            >
              Next Question <ChevronRight size={18} />
            </button>
          )}
        </footer>
      </div>

      <style jsx>{`
        .quiz-layout {
          max-width: 800px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: var(--space-xl);
        }
        .quiz-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .quiz-topic { font-size: 1.5rem; font-weight: 700; color: var(--text-primary); }
        .quiz-difficulty { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
        .quiz-timer {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: 8px 16px;
          background: var(--bg-glass);
          border: 1px solid var(--border-glass);
          border-radius: 100px;
          font-weight: 700;
          color: var(--text-primary);
        }
        .quiz-timer.warning { color: var(--accent-warning); border-color: var(--accent-warning); }
        .progress-container { display: flex; flex-direction: column; gap: 8px; }
        .progress-bar-track { height: 8px; background: var(--bg-glass); border-radius: 4px; overflow: hidden; }
        .progress-bar-fill { height: 100%; background: var(--gradient-primary); transition: width 0.3s ease; }
        .progress-text { font-size: 0.8125rem; color: var(--text-muted); text-align: right; }
        .question-card { padding: var(--space-2xl); min-height: 400px; }
        .question-text { font-size: 1.25rem; font-weight: 600; line-height: 1.4; margin-bottom: var(--space-2xl); color: var(--text-primary); }
        .options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); }
        .option-btn {
          display: flex;
          align-items: center;
          gap: var(--space-md);
          padding: var(--space-lg);
          background: var(--bg-glass);
          border: 1px solid var(--border-glass);
          border-radius: var(--radius-md);
          color: var(--text-secondary);
          cursor: pointer;
          transition: all 0.2s;
          text-align: left;
        }
        .option-btn:hover { background: var(--bg-glass-strong); border-color: var(--accent-primary-light); }
        .option-btn.selected { background: rgba(108, 99, 255, 0.15); border-color: var(--accent-primary); color: white; }
        .option-key { width: 32px; height: 32px; border-radius: 50%; background: rgba(255, 255, 255, 0.05); display: flex; alignItems: center; justifyContent: center; font-weight: 700; flex-shrink: 0; }
        .option-btn.selected .option-key { background: var(--accent-primary); color: white; }
        .quiz-footer { display: flex; justify-content: space-between; align-items: center; margin-top: var(--space-xl); }
      `}</style>
    </div>
  )
}
