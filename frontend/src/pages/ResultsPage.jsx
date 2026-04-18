import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { BookCheck, Clock, TrendingUp, RefreshCw, ChevronRight, XCircle, CheckCircle2 } from 'lucide-react';

export default function ResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state;

  if (!state || !state.result) {
    return (
      <div className="page-container" style={{ textAlign: 'center', paddingTop: 'var(--space-2xl)' }}>
        <h2 className="page-title">No Results Found</h2>
        <p className="page-subtitle">Please take a quiz first to see results.</p>
        <button className="btn btn-primary" onClick={() => navigate('/dashboard')} style={{ marginTop: 'var(--space-md)' }}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  const { result, quizData, answerArray, timeTaken } = state;
  const { score, total, percentage, feedback } = result;

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  return (
    <div className="page-container" style={{ maxWidth: 800, margin: '0 auto', paddingTop: 'var(--space-2xl)' }}>
      <div style={{ textAlign: 'center', marginBottom: 'var(--space-2xl)' }}>
        <h1 className="page-title">Quiz Results</h1>
        <p className="page-subtitle">Here is how you performed on {result.topic}</p>
      </div>

      <div style={{ 
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: 'var(--space-md)', marginBottom: 'var(--space-2xl)' 
      }}>
        <div className="stat-card">
          <BookCheck className="stat-icon" size={24} style={{ color: 'var(--primary)' }} />
          <div className="stat-value">{score} / {total}</div>
          <div className="stat-label">Final Score</div>
        </div>
        <div className="stat-card">
          <TrendingUp className="stat-icon" size={24} style={{ color: percentage >= 80 ? 'var(--success)' : percentage >= 60 ? 'var(--warning)' : 'var(--danger)' }} />
          <div className="stat-value">{percentage.toFixed(1)}%</div>
          <div className="stat-label">Accuracy</div>
        </div>
        <div className="stat-card">
          <Clock className="stat-icon" size={24} style={{ color: 'var(--text-muted)' }} />
          <div className="stat-value">{formatTime(timeTaken)}</div>
          <div className="stat-label">Time Taken</div>
        </div>
      </div>

      {feedback && (
        <div className="card" style={{ marginBottom: 'var(--space-2xl)', background: 'rgba(var(--primary-rgb), 0.05)', border: '1px solid rgba(var(--primary-rgb), 0.2)' }}>
          <h3 style={{ fontSize: '1.25rem', marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingUp size={20} className="text-primary" /> Personalized Feedback
          </h3>
          <p style={{ lineHeight: 1.6, color: 'var(--text)' }}>
            {feedback}
          </p>
        </div>
      )}

      {quizData && answerArray && (
        <div style={{ marginBottom: 'var(--space-2xl)' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: 'var(--space-xl)' }}>Question Review</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            {quizData.questions.map((q, qIdx) => {
              const uAns = answerArray[qIdx];
              const isCorrect = uAns === q.correct_index;
              
              return (
                <div key={qIdx} className="card" style={{ borderLeft: `4px solid ${isCorrect ? 'var(--success)' : 'var(--danger)'}` }}>
                  <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
                    {isCorrect ? <CheckCircle2 size={24} style={{ color: 'var(--success)', flexShrink: 0 }} /> : <XCircle size={24} style={{ color: 'var(--danger)', flexShrink: 0 }} />}
                    <h4 style={{ fontSize: '1.125rem', lineHeight: 1.4, margin: 0 }}>{qIdx + 1}. {q.question}</h4>
                  </div>
                  
                  <div style={{ paddingLeft: 32, display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                    {q.options.map((opt, oIdx) => {
                      let bg = 'var(--bg-section)';
                      let border = '1px solid var(--border)';
                      let color = 'var(--text)';
                      
                      if (oIdx === q.correct_index) {
                        bg = 'rgba(var(--success-rgb), 0.1)';
                        border = '1px solid var(--success)';
                        color = 'var(--success)';
                      } else if (oIdx === uAns && !isCorrect) {
                        bg = 'rgba(var(--danger-rgb), 0.1)';
                        border = '1px solid var(--danger)';
                        color = 'var(--danger)';
                      }
                      
                      return (
                        <div key={oIdx} style={{ 
                          padding: 'var(--space-sm) var(--space-md)', 
                          borderRadius: 'var(--radius-sm)',
                          background: bg, border, color,
                          display: 'flex', alignItems: 'center', gap: 'var(--space-sm)'
                        }}>
                          <div style={{ width: 16, height: 16, borderRadius: '50%', border: `1px solid ${color}`, display: 'grid', placeItems: 'center' }}>
                            {(oIdx === q.correct_index || oIdx === uAns) && <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />}
                          </div>
                          <span>{opt}</span>
                          {oIdx === q.correct_index && <span style={{ marginLeft: 'auto', fontSize: '0.75rem', fontWeight: 600 }}>Correct Answer</span>}
                          {oIdx === uAns && !isCorrect && <span style={{ marginLeft: 'auto', fontSize: '0.75rem', fontWeight: 600 }}>Your Answer</span>}
                        </div>
                      );
                    })}
                  </div>
                  
                  {(!isCorrect || q.explanation) && (
                    <div style={{ marginTop: 'var(--space-md)', padding: 'var(--space-md)', background: 'var(--bg-section)', borderRadius: 'var(--radius-md)' }}>
                      <strong>Explanation:</strong> {q.explanation || 'No explanation provided.'}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-md)' }}>
        <button className="btn btn-ghost" onClick={() => navigate('/dashboard')}>
          <ChevronRight size={18} /> Back to Dashboard
        </button>
        <button className="btn btn-primary" onClick={() => navigate('/quiz?topic=' + encodeURIComponent(result.topic))}>
          <RefreshCw size={18} /> Retry Topic Challenge
        </button>
      </div>
    </div>
  );
}
