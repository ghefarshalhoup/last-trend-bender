import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State { error: Error | null }

/** Last line of defence: a render crash shows a message and reload button instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Explorer crashed:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" style={{ maxWidth: '44rem', margin: '4rem auto', padding: '0 1rem', display: 'grid', gap: '0.75rem' }}>
        <h1 style={{ fontFamily: 'var(--font-display)' }}>Something went wrong in the explorer</h1>
        <p>{this.state.error.message}</p>
        <p style={{ color: 'var(--color-ink-muted)', fontSize: '0.9rem' }}>Open the browser console (F12) for details, then reload.</p>
        <button type="button" onClick={() => window.location.reload()} style={{ justifySelf: 'start', minHeight: 44, padding: '0 1.25rem' }}>
          Reload
        </button>
      </div>
    )
  }
}
