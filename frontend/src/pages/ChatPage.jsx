import React, { useRef, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { chatApi, fileApi, quizApi, youtubeApi } from '../services/api';
import {
  BookCheck,
  FileQuestion,
  FileText,
  Image as ImageIcon,
  Paperclip,
  Send,
  Sparkles,
  Trash2,
  Video,
} from 'lucide-react';

const STREAM_DELAY = 18;

function bytesToSize(bytes) {
  if (!bytes && bytes !== 0) return '';
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), sizes.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

function fileIcon(type) {
  if (type.startsWith('image/')) return ImageIcon;
  if (type === 'application/pdf') return FileText;
  return FileText;
}

export default function ChatPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [mode, setMode] = useState('socratic');
  const [loading, setLoading] = useState(false);
  const [pendingQuiz, setPendingQuiz] = useState(null);
  const [quizAnswer, setQuizAnswer] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [streamingId, setStreamingId] = useState(null);
  const [streamSupported, setStreamSupported] = useState(true);
  const [quizGenerating, setQuizGenerating] = useState(false);
  const [streamFallback, setStreamFallback] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingId, loading]);

  useEffect(() => {
    const stored = localStorage.getItem('aitutor_chat_history');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setMessages(parsed.slice(-60));
        }
      } catch (err) {
        localStorage.removeItem('aitutor_chat_history');
      }
    }
  }, []);

  useEffect(() => {
    if (!messages.length) return;
    localStorage.setItem('aitutor_chat_history', JSON.stringify(messages.slice(-60)));
  }, [messages]);

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = '0px';
    const height = Math.min(inputRef.current.scrollHeight, 160);
    inputRef.current.style.height = `${height}px`;
  }, [input]);

  const updateAttachment = (id, updates) => {
    setAttachments((prev) =>
      prev.map((item) => (item.id === id ? { ...item, ...updates } : item))
    );
  };

  const handleFilesSelected = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!files.length) return;

    const prepared = files.map((file) => ({
      id: `${file.name}-${file.size}-${Date.now()}`,
      name: file.name,
      type: file.type || 'application/octet-stream',
      size: file.size,
      previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : '',
      uploading: true,
      error: '',
      serverId: '',
      file,
    }));

    setAttachments((prev) => [...prepared, ...prev]);

    for (const item of prepared) {
      try {
        const res = await fileApi.upload(item.file);
        updateAttachment(item.id, { uploading: false, serverId: res.id || '' });
      } catch (err) {
        updateAttachment(item.id, {
          uploading: false,
          error: err.message || 'Upload failed',
        });
      }
    }
  };

  const handleRemoveAttachment = (id) => {
    setAttachments((prev) => prev.filter((item) => item.id !== id));
  };

  const buildAttachmentPayload = () =>
    attachments.map((item) => ({
      id: item.serverId || item.id,
      name: item.name,
      type: item.type,
      size: item.size,
      previewUrl: item.previewUrl,
      localOnly: !item.serverId,
    }));

  const streamText = (msgId, text) => {
    const words = text.split(' ');
    let idx = 0;
    setStreamingId(msgId);

    const interval = setInterval(() => {
      idx += 1;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === msgId
            ? { ...msg, text: words.slice(0, idx).join(' ') }
            : msg
        )
      );
      if (idx >= words.length) {
        clearInterval(interval);
        setStreamingId(null);
      }
    }, STREAM_DELAY);
  };

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;

    const outgoingAttachments = buildAttachmentPayload();
    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      text: q,
      attachments: outgoingAttachments,
      ts: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setAttachments([]);
    setLoading(true);

    const msgId = `ai-${Date.now()}`;
    let finalText = '';
    let isUploadRequired = false;
    let result = null;

    try {
      if (streamSupported && mode === 'socratic') {
        const placeholder = { id: msgId, role: 'ai', type: 'socratic', text: '', ts: Date.now() };
        setMessages((prev) => [...prev, placeholder]);
        setStreamingId(msgId);

        try {
          finalText = await chatApi.stream(q, mode, 3, outgoingAttachments, (text) => {
            setMessages((prev) => prev.map((msg) => (msg.id === msgId ? { ...msg, text } : msg)));
          });
          isUploadRequired = finalText.includes('upload a document to proceed') || finalText.includes('No relevant documents');
          setStreamingId(null);
        } catch (err) {
          console.error('Streaming failed, falling back to regular send:', err);
          setStreamSupported(false);
          setStreamingId(null);
          setStreamFallback(true);
          // Remove the placeholder so the regular send can add its own message
          setMessages((prev) => prev.filter((msg) => msg.id !== msgId));
          // Continue to regular send
        }
      }

      // If streaming was skipped or failed
      if (!streamSupported || mode !== 'socratic') {
        const data = await chatApi.send(q, mode, 3, outgoingAttachments);
        result = data.result || data;
        finalText = result.text || result.message || 'No response generated.';
        isUploadRequired = data.status === 'no_data' || result.action === 'upload_required' || finalText.includes('upload a document to proceed');

        if (result.mode === 'quiz') {
          setPendingQuiz({
            question: result.question,
            expected_answer: result.expected_answer,
            difficulty: result.difficulty,
            focus_node_id: result.focus_node_id,
          });

          setMessages((prev) => [
            ...prev,
            {
              id: `ai-${Date.now()}`,
              role: 'ai',
              type: 'quiz',
              text: result.question,
              difficulty: result.difficulty,
              citations: result.citations,
              ts: Date.now(),
            },
          ]);
          return;
        }

        let youtubeCard = null;
        try {
          if (q.length > 5 && !isUploadRequired) {
            const youtube = await youtubeApi.search(q);
            if (youtube && youtube.title) youtubeCard = youtube;
          }
        } catch (err) {}

        const initial = {
          id: msgId,
          role: 'ai',
          type: 'socratic',
          uploadRequired: isUploadRequired,
          text: '',
          followUp: result.follow_up_question,
          citations: result.citations,
          youtube: youtubeCard,
          ts: Date.now(),
        };
        setMessages((prev) => [...prev, initial]);
        streamText(msgId, finalText);
      } else {
        // Post-streaming enhancements (e.g. YouTube search)
        let youtubeCard = null;
        try {
          if (q.length > 5 && !isUploadRequired) {
            const youtube = await youtubeApi.search(q);
            if (youtube && youtube.title) youtubeCard = youtube;
          }
        } catch (err) {}
        
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === msgId
              ? { ...msg, uploadRequired: isUploadRequired, youtube: youtubeCard }
              : msg
          )
        );
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: 'ai',
          type: 'error',
          text: `Error: ${err.message}`,
          ts: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuizGenerate = async () => {
    if (!attachments.length || quizGenerating) return;
    setQuizGenerating(true);
    try {
      // Fix: quizApi.generate expects (topic, difficulty, num_questions)
      // We'll use the first attachment's name as the topic.
      const topic = attachments[0].name.replace(/\.[^/.]+$/, "");
      const data = await quizApi.generate(topic, 'medium', 10);
      const quiz = data.quiz || data;
      
      // Instead of just showing the first question in chat, let's offer to go to the Quiz Page
      // for a full 10-question experience as requested in Phase 1 Flow 4.
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: 'ai',
          type: 'socratic',
          text: `I've generated a 10-question quiz on **${topic}** for you!`,
          ts: Date.now(),
        },
      ]);
      
      // Navigate to the quiz page
      navigate(`/quiz?topic=${encodeURIComponent(topic)}&difficulty=medium`);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: `ai-${Date.now()}`, role: 'ai', type: 'error', text: `Quiz generation failed: ${err.message}`, ts: Date.now() },
      ]);
    } finally {
      setQuizGenerating(false);
    }
  };

  const handleQuizSubmit = async () => {
    if (!quizAnswer.trim() || !pendingQuiz) return;
    setLoading(true);

    try {
      const result = await chatApi.submitQuiz(
        pendingQuiz.focus_node_id || 'unknown',
        pendingQuiz.question,
        pendingQuiz.expected_answer,
        quizAnswer,
        pendingQuiz.difficulty || 'medium'
      );

      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, role: 'user', text: quizAnswer, ts: Date.now() },
        {
          id: `ai-${Date.now()}`,
          role: 'ai',
          type: 'quiz-result',
          text: result.is_correct
            ? 'Correct. Great understanding.'
            : 'Not quite right. Review this concept and try again.',
          mastery: result.updated_mastery,
          ts: Date.now(),
        },
      ]);
      setPendingQuiz(null);
      setQuizAnswer('');
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: `ai-${Date.now()}`, role: 'ai', type: 'error', text: `Quiz error: ${err.message}`, ts: Date.now() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (pendingQuiz) handleQuizSubmit();
      else handleSend();
    }
  };

  const disableSend = loading || !input.trim();
  const waitingForStream = useMemo(() => streamingId !== null, [streamingId]);

  return (
    <div className="chat-container">
      <div className="page-header" style={{ marginBottom: 'var(--space-md)' }}>
        <h1 className="page-title">Socratic Chat</h1>
        {streamFallback && (
          <div className="auth-error" style={{ marginTop: 'var(--space-sm)', marginBottom: 0 }}>
            Streaming is unavailable right now. Falling back to standard responses.
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginTop: 'var(--space-sm)' }}>
          <span className="page-subtitle" style={{ marginTop: 0 }}>Mode:</span>
          <div className="mode-toggle">
            <button className={mode === 'socratic' ? 'active' : ''} onClick={() => setMode('socratic')}>
              <Sparkles size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Socratic
            </button>
            <button className={mode === 'quiz' ? 'active' : ''} onClick={() => setMode('quiz')}>
              <FileQuestion size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Quiz
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: 'var(--space-2xl)', color: 'var(--text-muted)' }}>
            <Sparkles size={40} style={{ marginBottom: 12, opacity: 0.3 }} />
            <p style={{ fontSize: '1rem', fontWeight: 500 }}>Ask a question to begin your learning session</p>
            <p style={{ fontSize: '0.8125rem', marginTop: 8 }}>
              Try: "Explain BM25 retrieval" or "What is a knowledge graph?"
            </p>
          </div>
        )}

        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={msg.id || msg.ts + '-' + i}
              initial={{ opacity: 0, y: 12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'}`}
            >
              {msg.role === 'ai' && (
                <div className="bubble-label">
                  {msg.type === 'quiz' && <><FileQuestion size={14} /> Quiz Question</>}
                  {msg.type === 'quiz-result' && <><BookCheck size={14} /> Result</>}
                  {msg.type === 'socratic' && <><Sparkles size={14} /> SocratiQ</>}
                  {msg.type === 'error' && 'Error'}
                </div>
              )}

              {msg.attachments && msg.attachments.length > 0 && (
                <div className="attachment-row">
                  {msg.attachments.map((file) => {
                    const Icon = fileIcon(file.type);
                    return (
                      <div key={file.id} className="attachment-chip">
                        {file.previewUrl ? (
                          <img src={file.previewUrl} alt={file.name} />
                        ) : (
                          <Icon size={16} />
                        )}
                        <span className="attachment-name">{file.name}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                  {msg.text || (msg.type === 'socratic' && msg.id === streamingId ? ' ' : '')}
                </ReactMarkdown>
              </div>

              {msg.uploadRequired && (
                <div style={{ marginTop: 'var(--space-md)' }}>
                  <button 
                    className="btn btn-primary" 
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Paperclip size={16} /> Upload Document
                  </button>
                </div>
              )}

              {msg.followUp && (
                <div className="followup-chip">
                  Tip: {msg.followUp}
                </div>
              )}

              {msg.difficulty && (
                <span className={`badge ${msg.difficulty === 'hard' ? 'badge-danger' : msg.difficulty === 'medium' ? 'badge-warning' : 'badge-success'}`}
                  style={{ marginTop: 'var(--space-sm)', display: 'inline-flex' }}>
                  {msg.difficulty}
                </span>
              )}

              {msg.mastery && (
                <div style={{ marginTop: 'var(--space-sm)', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  New mastery: {(msg.mastery.mastery * 100).toFixed(0)}% | Trend: {(msg.mastery.trend * 100).toFixed(0)}%
                </div>
              )}

              {msg.citations && msg.citations.length > 0 && (
                <div className="citation-row">
                  {msg.citations.map((c, idx) => (
                    <span key={`${c.heading}-${idx}`} className="citation-chip">
                      {c.heading}
                    </span>
                  ))}
                </div>
              )}

              {msg.youtube && (
                <div className="youtube-card">
                  <div className="youtube-icon"><Video size={16} /></div>
                  <div>
                    <div className="youtube-title">{msg.youtube.title}</div>
                    <div className="youtube-meta">{msg.youtube.channel || 'YouTube'} · {msg.youtube.snippet || 'Recommended video'}</div>
                    {msg.youtube.url && (
                      <a className="youtube-link" href={msg.youtube.url} target="_blank" rel="noreferrer">
                        Watch
                      </a>
                    )}
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {(loading || waitingForStream) && (
          <div className="chat-bubble chat-bubble-ai" style={{ alignSelf: 'flex-start' }}>
            <div className="bubble-label"><Sparkles size={14} /> Thinking</div>
            <div className="loading-dots"><span></span><span></span><span></span></div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        {pendingQuiz ? (
          <>
            <textarea
              className="input-field"
              placeholder="Type your quiz answer..."
              value={quizAnswer}
              onChange={(e) => setQuizAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              style={{ resize: 'none', fontFamily: 'var(--font-sans)' }}
            />
            <button className="btn btn-primary" onClick={handleQuizSubmit} disabled={loading || !quizAnswer.trim()}>
              <BookCheck size={18} /> Submit
            </button>
          </>
        ) : (
          <>
            <div className="chat-input-stack">
              <textarea
                ref={inputRef}
                className="input-field"
                placeholder="Ask a learning question..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
                rows={1}
              />
              {attachments.length > 0 && (
                <div className="attachment-row">
                  {attachments.map((file) => {
                    const Icon = fileIcon(file.type);
                    return (
                      <div key={file.id} className={`attachment-chip ${file.error ? 'attachment-error' : ''}`}>
                        {file.previewUrl ? (
                          <img src={file.previewUrl} alt={file.name} />
                        ) : (
                          <Icon size={16} />
                        )}
                        <span className="attachment-name">{file.name}</span>
                        <span className="attachment-meta">
                          {file.uploading ? 'Uploading' : file.error ? 'Local only' : bytesToSize(file.size)}
                        </span>
                        <button className="attachment-remove" onClick={() => handleRemoveAttachment(file.id)}>
                          <Trash2 size={12} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,application/pdf"
              multiple
              hidden
              onChange={handleFilesSelected}
            />
            <button
              className="btn btn-ghost"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              title="Attach files"
            >
              <Paperclip size={18} />
            </button>
            <button
              className="btn btn-ghost"
              onClick={handleQuizGenerate}
              disabled={quizGenerating || attachments.length === 0}
              title="Generate quiz from attachments"
            >
              <BookCheck size={18} />
            </button>
            <button className="btn btn-primary" onClick={handleSend} disabled={disableSend}>
              <Send size={18} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
