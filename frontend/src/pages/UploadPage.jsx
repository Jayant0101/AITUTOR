import React, { useState, useRef } from 'react';
import { UploadCloud, CheckCircle, AlertCircle, FileText, Image as ImageIcon } from 'lucide-react';
import { fileApi } from '../services/api';

export default function UploadPage() {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState([]);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const handleFiles = (newFiles) => {
    const valid = newFiles.filter(
      (f) => f.type === 'application/pdf' || f.type.startsWith('image/')
    );
    const prepared = valid.map((f) => ({
      id: `${f.name}-${Date.now()}`,
      file: f,
      status: 'pending',
      error: null
    }));
    setFiles((prev) => [...prepared, ...prev]);

    prepared.forEach(async (item) => {
      setFiles((prev) => prev.map((f) => f.id === item.id ? { ...f, status: 'uploading' } : f));
      try {
        const res = await fileApi.upload(item.file);
        setFiles((prev) => prev.map((f) => f.id === item.id ? { ...f, status: 'success', serverId: res.id } : f));
      } catch (err) {
        setFiles((prev) => prev.map((f) => f.id === item.id ? { ...f, status: 'error', error: err.message } : f));
      }
    });
  };

  return (
    <div className="page-container" style={{ maxWidth: 800, margin: '0 auto', paddingTop: 'var(--space-2xl)' }}>
      <h1 className="page-title">Upload Documents</h1>
      <p className="page-subtitle" style={{ marginBottom: 'var(--space-2xl)' }}>
        Upload PDFs or images to provide additional context for SocratiQ.
      </p>

      <div
        className={`upload-zone ${dragActive ? 'active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragActive ? 'var(--primary)' : 'var(--border)'}`,
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--space-3xl) var(--space-xl)',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragActive ? 'rgba(var(--primary-rgb), 0.05)' : 'var(--bg-card)',
          transition: 'all 0.2s ease',
          marginBottom: 'var(--space-xl)'
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,application/pdf"
          multiple
          onChange={handleChange}
          style={{ display: 'none' }}
        />
        <UploadCloud size={48} style={{ color: dragActive ? 'var(--primary)' : 'var(--text-muted)', marginBottom: 'var(--space-md)' }} />
        <h3 style={{ marginBottom: 'var(--space-xs)' }}>Drag and drop files here</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>or click to browse (PDF, Images)</p>
      </div>

      {files.length > 0 && (
        <div className="upload-list" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          <h3 style={{ fontSize: '1rem', marginBottom: 'var(--space-sm)' }}>Recent Uploads</h3>
          {files.map((file) => (
            <div key={file.id} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: 'var(--space-md)', background: 'var(--bg-card)',
              borderRadius: 'var(--radius-md)', border: '1px solid var(--border)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                {file.file.type.startsWith('image/') ? <ImageIcon size={20} className="text-primary" /> : <FileText size={20} className="text-primary" />}
                <div>
                  <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{file.file.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {(file.file.size / 1024 / 1024).toFixed(2)} MB
                  </div>
                </div>
              </div>
              <div>
                {file.status === 'uploading' && <span style={{ color: 'var(--warning)', fontSize: '0.875rem' }}>Uploading...</span>}
                {file.status === 'success' && <CheckCircle size={20} style={{ color: 'var(--success)' }} />}
                {file.status === 'error' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--danger)' }}>
                    <AlertCircle size={16} />
                    <span style={{ fontSize: '0.75rem' }}>{file.error}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
