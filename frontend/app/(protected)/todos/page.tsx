'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { Todo } from '@/lib/types'
import { Plus, Trash2, CheckCircle2, Circle } from 'lucide-react'

/**
 * Optimized Todos Page with multi-user safety and strict field selection.
 * Uses client-side Supabase client for immediate UI feedback.
 */
export default function TodosPage() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [newTodo, setNewTodo] = useState('')
  const [loading, setLoading] = useState(true)
  const supabase = createClient()

  useEffect(() => {
    fetchTodos()
  }, [])

  const fetchTodos = async () => {
    // Optimized query: specific fields and strict ordering
    const { data, error } = await supabase
      .from('todos')
      .select('id, name, is_completed, created_at')
      .order('created_at', { ascending: false })
    
    if (!error) {
      setTodos(data || [])
    }
    setLoading(false)
  }

  const addTodo = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTodo.trim()) return

    // Explicitly check for user to ensure multi-user safety
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    const { data, error } = await supabase
      .from('todos')
      .insert([{ 
        name: newTodo, 
        user_id: user.id // Required for RLS
      }])
      .select('id, name, is_completed, created_at')
      .single()

    if (!error) {
      // Optimistic update: adding the new todo to state immediately
      setTodos([data, ...todos])
      setNewTodo('')
    }
  }

  const toggleTodo = async (id: string, is_completed: boolean) => {
    const { error } = await supabase
      .from('todos')
      .update({ is_completed: !is_completed })
      .eq('id', id)

    if (!error) {
      setTodos(todos.map(t => t.id === id ? { ...t, is_completed: !is_completed } : t))
    }
  }

  const deleteTodo = async (id: string) => {
    const { error } = await supabase
      .from('todos')
      .delete()
      .eq('id', id)

    if (!error) {
      setTodos(todos.filter(t => t.id !== id))
    }
  }

  return (
    <div className="main-content">
      <header className="page-header">
        <h1 className="page-title">Supabase Todos</h1>
        <p className="page-subtitle">Production-ready persistent task management.</p>
      </header>

      <div className="glass-card" style={{ padding: 'var(--space-xl)', maxWidth: 600 }}>
        <form onSubmit={addTodo} style={{ display: 'flex', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
          <input
            type="text"
            className="input-field"
            placeholder="Add a new task..."
            value={newTodo}
            onChange={(e) => setNewTodo(e.target.value)}
          />
          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{ padding: '0 var(--space-lg)' }}
            title="Add task"
            aria-label="Add task"
          >
            <Plus size={20} />
          </button>
        </form>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-xl)' }}>
            <div className="loading-dots"><span></span><span></span><span></span></div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {todos.map((todo) => (
              <div 
                key={todo.id} 
                className="glass-card" 
                style={{ 
                  padding: 'var(--space-md)', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between',
                  background: todo.is_completed ? 'rgba(255, 255, 255, 0.02)' : 'var(--bg-glass)'
                }}
              >
                <div 
                  style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', cursor: 'pointer', flex: 1 }}
                  onClick={() => toggleTodo(todo.id, todo.is_completed)}
                >
                  {todo.is_completed ? (
                    <CheckCircle2 size={20} color="var(--accent-secondary)" />
                  ) : (
                    <Circle size={20} color="var(--text-muted)" />
                  )}
                  <span style={{ 
                    textDecoration: todo.is_completed ? 'line-through' : 'none',
                    color: todo.is_completed ? 'var(--text-muted)' : 'var(--text-primary)'
                  }}>
                    {todo.name}
                  </span>
                </div>
                <button 
                  type="button"
                  onClick={() => deleteTodo(todo.id)}
                  style={{ background: 'none', border: 'none', color: 'var(--accent-warning)', cursor: 'pointer', padding: 'var(--space-xs)' }}
                  title="Delete task"
                  aria-label="Delete task"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            ))}
            {todos.length === 0 && (
              <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                No tasks yet. Add one above!
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
