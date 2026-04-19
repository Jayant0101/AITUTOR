'use client'

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error(error)
  }, [error])

  return (
    <div className="main-content" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <h2 className="page-title" style={{ color: 'var(--accent-warning)', marginBottom: 'var(--space-md)' }}>Something went wrong!</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--space-xl)' }}>{error.message || 'An unexpected error occurred.'}</p>
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => reset()}
        title="Retry"
      >
        Try again
      </button>
    </div>
  )
}
