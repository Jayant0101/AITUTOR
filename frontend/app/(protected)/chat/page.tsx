'use client'

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { chatApi, youtubeApi } from '@/lib/services/api'
import { getUserTier, type UserTier } from '@/lib/saas/tiers'
import { Message, YouTubeResult } from '@/lib/types'
import { Send, Plus, Search, Youtube, Loader2, Sparkles, AlertCircle, Lock } from 'lucide-react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState('socratic')
  const [ytQuery, setYtQuery] = useState('')
  const [ytResults, setYtResults] = useState<YouTubeResult[]>([])
  const [ytLoading, setYtLoading] = useState(false)
  const [error, setError] = useState('')
  const [userTier, setUserTier] = useState<UserTier | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getUserTier().then(setUserTier)
    const stored = localStorage.getItem('aitutor_chat_history')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        if (Array.isArray(parsed)) setMessages(parsed.slice(-60))
      } catch (err) {
        localStorage.removeItem('aitutor_chat_history')
      }
    }
  }, [])

  useEffect(() => {
    if (messages.length) {
      localStorage.setItem('aitutor_chat_history', JSON.stringify(messages.slice(-60)))
    }
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg = { role: 'user', content: input, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setError('')

    try {
      let fullContent = ''
      setMessages(prev => [...prev, { role: 'assistant', content: '', id: 'streaming' }])
      
      // Prepare history for API (excluding the current user message just added)
      const apiHistory = messages.map(m => ({
        role: m.role,
        content: m.content
      }))

      await chatApi.stream(input, mode, 3, [], apiHistory, (chunk) => {
        fullContent = chunk
        setMessages(prev => prev.map(m => m.id === 'streaming' ? { ...m, content: chunk } : m))
      })
      
      setMessages(prev => prev.map(m => m.id === 'streaming' ? { ...m, id: Date.now() } : m))
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(errorMessage)
      setMessages(prev => prev.filter(m => m.id !== 'streaming'))
    } finally {
      setLoading(false)
    }
  }

  const handleYoutubeSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ytQuery.trim()) return
    setYtLoading(true)
    try {
      const data = await youtubeApi.search(ytQuery)
      setYtResults(data.videos || [])
    } catch (err) {
      console.error(err)
    } finally {
      setYtLoading(false)
    }
  }

  return (
    <div className="main-content chat-layout">
      <div className="chat-container">
        <header className="page-header chat-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
            <div className="chat-avatar"><Sparkles size={20} /></div>
            <div>
              <h1 className="page-title" style={{ fontSize: '1.25rem' }}>Socratic Chat</h1>
              <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 4 }}>
                <button 
                  type="button"
                  onClick={() => setMode('socratic')} 
                  className={`mode-badge ${mode === 'socratic' ? 'active' : ''}`}
                  title="Socratic mode"
                  aria-label="Socratic mode"
                >
                  Socratic
                </button>
                <button 
                  type="button"
                  onClick={() => {
                    if (userTier === 'free') {
                      setError('Direct mode is available on Pro plans.')
                      return
                    }
                    setMode('direct')
                  }} 
                  className={`mode-badge ${mode === 'direct' ? 'active' : ''}`}
                  title="Direct mode"
                  aria-label="Direct mode"
                >
                  {userTier === 'free' && <Lock size={10} style={{ marginRight: 4 }} />}
                  Direct
                </button>
              </div>
            </div>
          </div>
        </header>

        <div className="messages-list">
          <AnimatePresence>
            {messages.map((m) => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`message-wrapper ${m.role}`}
              >
                <div className={`message-bubble ${m.role}`}>
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]} 
                    rehypePlugins={[rehypeHighlight]}
                  >
                    {m.content}
                  </ReactMarkdown>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          {loading && (
            <div className="message-wrapper assistant">
              <div className="message-bubble assistant loading">
                <Loader2 className="animate-spin" size={18} />
              </div>
            </div>
          )}
          {error && (
            <div className="error-toast">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
          <div ref={scrollRef} />
        </div>

        <form onSubmit={handleSend} className="chat-input-wrapper">
          <input
            className="chat-input"
            placeholder="Ask anything..."
            aria-label="Ask the AI Tutor a question"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="send-btn" disabled={loading || !input.trim()} title="Send message" aria-label="Send message">
            <Send size={18} />
          </button>
        </form>
      </div>

      <aside className="chat-sidebar">
        <div className="glass-card yt-search-card">
          <h3><Youtube size={18} color="#FF0000" /> YouTube Grounding</h3>
          <form onSubmit={handleYoutubeSearch} className="yt-input-group">
            <input 
              placeholder="Find educational videos..." 
              value={ytQuery}
              onChange={(e) => setYtQuery(e.target.value)}
            />
            <button type="submit" title="Search YouTube" aria-label="Search YouTube"><Search size={16} /></button>
          </form>

          <div className="yt-results">
            {ytLoading ? (
              <div style={{ textAlign: 'center', padding: 'var(--space-lg)' }}><Loader2 className="animate-spin" /></div>
            ) : (
              ytResults.map(v => (
                <div key={v.id} className="yt-item" onClick={() => setInput(prev => prev + ` \n\nReference video: ${v.url}`)}>
                  <img src={v.thumbnail} alt="" />
                  <div className="yt-info">
                    <div className="yt-title">{v.title}</div>
                    <div className="yt-channel">{v.channel}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>

      <style jsx>{`
        .chat-layout {
          display: grid;
          grid-template-columns: 1fr 320px;
          gap: var(--space-xl);
          height: calc(100vh - 100px);
        }
        .chat-container {
          display: flex;
          flex-direction: column;
          background: var(--bg-glass);
          border: 1px solid var(--border-glass);
          border-radius: var(--radius-xl);
          overflow: hidden;
        }
        .messages-list {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-xl);
          display: flex;
          flex-direction: column;
          gap: var(--space-lg);
        }
        .message-wrapper {
          display: flex;
          width: 100%;
        }
        .message-wrapper.user { justify-content: flex-end; }
        .message-bubble {
          max-width: 85%;
          padding: var(--space-md) var(--space-lg);
          border-radius: var(--radius-lg);
          font-size: 0.9375rem;
          line-height: 1.5;
        }
        .message-bubble.user {
          background: var(--accent-primary);
          color: white;
          border-bottom-right-radius: 4px;
        }
        .message-bubble.assistant {
          background: var(--bg-glass-strong);
          color: var(--text-primary);
          border-bottom-left-radius: 4px;
        }
        .chat-input-wrapper {
          padding: var(--space-lg);
          background: rgba(0,0,0,0.2);
          display: flex;
          gap: var(--space-md);
        }
        .chat-input {
          flex: 1;
          background: var(--bg-glass);
          border: 1px solid var(--border-glass);
          border-radius: var(--radius-full);
          padding: 12px 24px;
          color: white;
          outline: none;
        }
        .send-btn {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          background: var(--gradient-primary);
          border: none;
          color: white;
          cursor: pointer;
          display: flex;
          alignItems: center;
          justifyContent: center;
        }
        .mode-badge {
          background: transparent;
          border: 1px solid var(--border-glass);
          color: var(--text-muted);
          font-size: 0.75rem;
          padding: 2px 10px;
          border-radius: 100px;
          cursor: pointer;
        }
        .mode-badge.active {
          background: var(--accent-primary);
          border-color: var(--accent-primary);
          color: white;
        }
        .yt-search-card {
          padding: var(--space-lg);
          height: 100%;
        }
        .yt-input-group {
          display: flex;
          background: var(--bg-glass);
          border-radius: var(--radius-md);
          margin: var(--space-md) 0;
          padding: 4px;
        }
        .yt-input-group input {
          flex: 1;
          background: transparent;
          border: none;
          color: white;
          padding: 8px;
          font-size: 0.8125rem;
          outline: none;
        }
        .yt-input-group button {
          background: transparent;
          border: none;
          color: var(--text-muted);
          padding: 0 8px;
          cursor: pointer;
        }
        .yt-results {
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
          max-height: calc(100vh - 350px);
          overflow-y: auto;
        }
        .yt-item {
          display: flex;
          gap: var(--space-sm);
          cursor: pointer;
          padding: 8px;
          border-radius: var(--radius-sm);
          transition: background 0.2s;
        }
        .yt-item:hover { background: var(--bg-glass); }
        .yt-item img {
          width: 80px;
          height: 45px;
          object-fit: cover;
          border-radius: 4px;
        }
        .yt-title { font-size: 0.75rem; font-weight: 500; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .yt-channel { font-size: 0.6875rem; color: var(--text-muted); margin-top: 2px; }
      `}</style>
    </div>
  )
}
