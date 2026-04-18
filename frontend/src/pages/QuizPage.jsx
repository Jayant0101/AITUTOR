import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { BookCheck, Clock, AlertTriangle, ChevronRight, ChevronLeft, CheckCircle2 } from 'lucide-react';
import { quizApi } from '../services/api';

export default function QuizPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const topic = searchParams.get('topic') || 'General';
  const difficulty = searchParams.get('difficulty') || 'medium';
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [quizData, setQuizData] = useState(null);
  
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({}); // { questionIndex: selectedOptionIndex }
  const [timeLeft, setTimeLeft] = useState(600); // 10 minutes default
  const [startTime, setStartTime] = useState(Date.now());
  const [submitting, setSubmitting] = useState(false);

  // Prevention of refresh loss
  useEffect(() => {
    const saved = localStorage.getItem('aitutor_active_quiz');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.topic === topic && parsed.difficulty === difficulty) {
          setQuizData(parsed.quizData);
          setAnswers(parsed.answers || {});
          
          // Fix: Calculate remaining time based on startTime to avoid mismatch
          const elapsed = Math.floor((Date.now() - parsed.startTime) / 1000);
          const totalAllocated = parsed.quizData.questions?.length * 60 || 600;
          const remaining = Math.max(0, totalAllocated - elapsed);
          
          setTimeLeft(remaining);
          setStartTime(parsed.startTime);
          setLoading(false);
          return;
        }
      } catch (err) {}
    }
    
    // Fetch new quiz
    fetchQuiz();
  }, [topic, difficulty]);

  useEffect(() => {
    if (quizData) {
      localStorage.setItem('aitutor_active_quiz', JSON.stringify({
        topic,
        difficulty,
        quizData,
        answers,
        startTime // Only need startTime, timeLeft is derived
      }));
    }
  }, [quizData, answers, startTime, topic, difficulty]);

  // Timer countdown
  useEffect(() => {
    if (loading || submitting || timeLeft <= 0) return;
    
    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          handleSubmit(); // auto submit when time is up
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => clearInterval(timer);
  }, [loading, submitting, timeLeft]);

  const fetchQuiz = async () => {
    try {
      setLoading(true);
      setError('');
      // Phase 1 Flow 4: Generate quiz with 10 questions
      const data = await quizApi.generate(topic, difficulty, 10);
      setQuizData(data);
      const now = Date.now();
      setStartTime(now);
      setTimeLeft(data.questions?.length * 60 || 600);
    } catch (err) {
      setError(err.message || 'Failed to generate quiz');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectOption = (qIdx, optIdx) => {
    setAnswers(prev => ({ ...prev, [qIdx]: optIdx }));
  };

  const handleSubmit = async () => {
    if (!quizData) return;
    setSubmitting(true);
    try {
      const timeTaken = Math.floor((Date.now() - startTime) / 1000);
      // Map dictionary of answers to array matching question indices. Missing -> -1
      const answerArray = quizData.questions.map((_, idx) => 
        answers[idx] !== undefined ? answers[idx] : -1
      );
      
      const result = await quizApi.submit(quizData.quiz_id, answerArray, timeTaken);
      localStorage.removeItem('aitutor_active_quiz');
      // Navigate to results
      navigate('/results', { state: { result, quizData, answerArray, timeTaken } });
    } catch (err) {
      // Phase 2: Handle "Quiz not found" (server restart) by allowing retry
      if (err.message?.includes('not found')) {
        setError('Your session expired or the server restarted. Please start a new quiz.');
        localStorage.removeItem('aitutor_active_quiz');
      } else {
        setError('Submission failed: ' + err.message);
      }
      setSubmitting(false);
    }
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="page-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="loading-dots" style={{ marginBottom: 16 }}><span></span><span></span><span></span></div>
          <p style={{ color: 'var(--text-muted)' }}>Generating adaptive quiz...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container" style={{ paddingTop: 'var(--space-2xl)' }}>
        <div className="auth-error">
          <AlertTriangle size={20} /> {error}
        </div>
        <button className="btn btn-primary" onClick={fetchQuiz} style={{ marginTop: 'var(--space-md)' }}>Retry</button>
      </div>
    );
  }

  if (!quizData || !quizData.questions?.length) {
    return <div className="page-container">No questions found.</div>;
  }

  const question = quizData.questions[currentIndex];
  const allAnswered = quizData.questions.every((_, i) => answers[i] !== undefined);

  return (
    <div className="page-container" style={{ maxWidth: 800, margin: '0 auto', paddingTop: 'var(--space-2xl)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-xl)' }}>
        <div>
          <h1 className="page-title" style={{ fontSize: '1.5rem', marginBottom: 'var(--space-xs)' }}>
            Knowledge Check: {topic}
          </h1>
          <span className={`badge ${difficulty === 'hard' ? 'badge-danger' : difficulty === 'medium' ? 'badge-warning' : 'badge-success'}`}>
            {difficulty}
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1.125rem', fontWeight: 600, color: timeLeft < 60 ? 'var(--danger)' : 'var(--text)' }}>
          <Clock size={20} />
          {formatTime(timeLeft)}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 'var(--space-lg)' }}>
          {quizData.questions.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentIndex(i)}
              style={{
                flex: 1,
                height: 6,
                borderRadius: 4,
                border: 'none',
                cursor: 'pointer',
                background: currentIndex === i ? 'var(--primary)' : answers[i] !== undefined ? 'var(--success)' : 'var(--border)'
              }}
              title={`Question ${i + 1}`}
            />
          ))}
        </div>

        <h3 style={{ fontSize: '1.25rem', marginBottom: 'var(--space-xl)', lineHeight: 1.5 }}>
          <span style={{ color: 'var(--text-muted)', marginRight: 8 }}>{currentIndex + 1}.</span>
          {question.question}
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          {question.options.map((opt, oIdx) => {
            const isSelected = answers[currentIndex] === oIdx;
            return (
              <button
                key={oIdx}
                onClick={() => handleSelectOption(currentIndex, oIdx)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 'var(--space-md)',
                  padding: 'var(--space-md) var(--space-lg)',
                  borderRadius: 'var(--radius-md)',
                  border: `2px solid ${isSelected ? 'var(--primary)' : 'var(--border)'}`,
                  background: isSelected ? 'rgba(var(--primary-rgb), 0.05)' : 'var(--bg-section)',
                  color: 'var(--text)',
                  fontSize: '1rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ 
                  width: 24, height: 24, borderRadius: '50%', 
                  border: `2px solid ${isSelected ? 'var(--primary)' : 'var(--text-muted)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  {isSelected && <div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--primary)' }} />}
                </div>
                <span>{opt}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button 
          className="btn btn-ghost" 
          disabled={currentIndex === 0} 
          onClick={() => setCurrentIndex(prev => prev - 1)}
        >
          <ChevronLeft size={20} /> Previous
        </button>

        {currentIndex === quizData.questions.length - 1 ? (
          <button 
            className="btn btn-primary" 
            onClick={handleSubmit} 
            disabled={submitting || !allAnswered}
          >
            {submitting ? 'Submitting...' : 'Submit Quiz'}
            {!submitting && <CheckCircle2 size={20} style={{ marginLeft: 8 }} />}
          </button>
        ) : (
          <button 
            className="btn btn-primary" 
            onClick={() => setCurrentIndex(prev => prev + 1)}
          >
            Next <ChevronRight size={20} />
          </button>
        )}
      </div>
    </div>
  );
}
