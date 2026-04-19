'use client'

import { useState, useEffect } from 'react'
import { fileApi, ingestApi } from '@/lib/services/api'
import { getUserTier, type UserTier } from '@/lib/saas/tiers'
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2, RefreshCw, Lock } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([])
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [reloading, setReloading] = useState(false)
  const [userTier, setUserTier] = useState<UserTier | null>(null)

  useEffect(() => {
    getUserTier().then(setUserTier)
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files)
      const limit = userTier?.limits.uploads || 2
      
      if (selected.length > limit) {
        setStatus('error')
        setMessage(`Your ${userTier?.tier} plan is limited to ${limit} uploads at a time.`)
        return
      }
      setFiles(selected)
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    
    const limit = userTier?.limits.uploads || 2
    if (files.length > limit) {
      setStatus('error')
      setMessage(`Upgrade to Pro to upload more than ${limit} files.`)
      return
    }

    setStatus('uploading')
    setMessage('')
// ... rest of existing handleUpload ...

    try {
      for (const file of files) {
        await fileApi.upload(file)
      }
      setStatus('success')
      setMessage(`Successfully uploaded ${files.length} file(s).`)
      setFiles([])
    } catch (err: any) {
      setStatus('error')
      setMessage(err.message || 'Upload failed')
    }
  }

  const handleReload = async () => {
    setReloading(true)
    try {
      await ingestApi.reload()
      setMessage('Knowledge graph reloaded successfully.')
    } catch (err: any) {
      setMessage('Failed to reload graph: ' + err.message)
    } finally {
      setReloading(false)
    }
  }

  return (
    <div className="main-content">
      <header className="page-header">
        <h1 className="page-title">Knowledge Ingestion</h1>
        <p className="page-subtitle">Upload documents to build your local knowledge graph.</p>
      </header>

      <div className="grid-2">
        <div className="glass-card upload-section">
          <div 
            className={`drop-zone ${files.length > 0 ? 'has-files' : ''}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              if (e.dataTransfer.files) setFiles(Array.from(e.dataTransfer.files))
            }}
          >
            <input 
              type="file" 
              id="file-upload" 
              multiple 
              hidden 
              onChange={handleFileChange}
              accept=".pdf,.md,.txt,.png,.jpg,.jpeg"
            />
            <label htmlFor="file-upload" className="drop-zone-content">
              <div className="upload-icon">
                <Upload size={32} />
              </div>
              <h3>{files.length > 0 ? `${files.length} files selected` : 'Drop files here or click to browse'}</h3>
              <p>Supports PDF, Markdown, Text, and Images</p>
            </label>
          </div>

          {files.length > 0 && (
            <div className="selected-files">
              {files.map((f, i) => (
                <div key={i} className="file-item">
                  <FileText size={16} />
                  <span>{f.name}</span>
                </div>
              ))}
            </div>
          )}

          <div className="upload-actions">
            <button 
              className="btn btn-primary btn-lg" 
              disabled={files.length === 0 || status === 'uploading'}
              onClick={handleUpload}
            >
              {status === 'uploading' ? (
                <><Loader2 className="animate-spin" size={20} /> Uploading...</>
              ) : (
                'Process Documents'
              )}
            </button>
            <button 
              className="btn btn-secondary"
              onClick={handleReload}
              disabled={reloading}
            >
              <RefreshCw size={18} className={reloading ? 'animate-spin' : ''} />
              Reload Graph
            </button>
          </div>

          <AnimatePresence>
            {message && (
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className={`status-msg ${status}`}
              >
                {status === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                <span>{message}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="glass-card info-card">
          <h2 className="section-title">How Ingestion Works</h2>
          <ul className="info-list">
            <li>
              <strong>Multi-modal Parsing:</strong> Text is extracted from PDFs, Markdown, and even images via OCR.
            </li>
            <li>
              <strong>Graph Construction:</strong> Concepts are linked together to form a vectorless knowledge graph.
            </li>
            <li>
              <strong>Hybrid Retrieval:</strong> BM25 keyword matching combined with graph traversal ensures grounded responses.
            </li>
          </ul>
        </div>
      </div>

      <style jsx>{`
        .upload-section {
          padding: var(--space-xl);
          display: flex;
          flex-direction: column;
          gap: var(--space-xl);
        }
        .drop-zone {
          border: 2px dashed var(--border-glass);
          border-radius: var(--radius-lg);
          padding: var(--space-2xl);
          text-align: center;
          transition: all 0.2s;
          cursor: pointer;
        }
        .drop-zone:hover, .drop-zone.has-files {
          border-color: var(--accent-primary);
          background: rgba(108, 99, 255, 0.05);
        }
        .drop-zone-content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-md);
          cursor: pointer;
        }
        .upload-icon {
          width: 64px;
          height: 64px;
          border-radius: 50%;
          background: var(--bg-glass);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--accent-primary);
        }
        .selected-files {
          display: flex;
          flex-direction: column;
          gap: var(--space-sm);
        }
        .file-item {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          font-size: 0.875rem;
          color: var(--text-secondary);
          background: var(--bg-glass);
          padding: 8px 12px;
          border-radius: var(--radius-sm);
        }
        .upload-actions {
          display: flex;
          gap: var(--space-md);
        }
        .status-msg {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-md);
          border-radius: var(--radius-md);
          font-size: 0.875rem;
        }
        .status-msg.success { background: rgba(0, 212, 170, 0.1); color: var(--accent-secondary); }
        .status-msg.error { background: rgba(255, 107, 107, 0.1); color: var(--accent-warning); }
        .info-card { padding: var(--space-xl); }
        .info-list {
          list-style: none;
          padding: 0;
          margin-top: var(--space-lg);
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
        }
        .info-list li {
          font-size: 0.9375rem;
          color: var(--text-secondary);
          line-height: 1.6;
        }
      `}</style>
    </div>
  )
}
