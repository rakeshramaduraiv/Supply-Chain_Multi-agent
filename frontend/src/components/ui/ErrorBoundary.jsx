import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an uncaught exception:", error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '24px', background: 'var(--s1)', border: '1px solid var(--b)',
          borderRadius: '8px', margin: '20px', textAlign: 'center',
          fontFamily: 'var(--font)', display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: '12px'
        }}>
          <AlertTriangle size={32} style={{ color: '#ef4444' }} />
          <h3 style={{ margin: 0, fontSize: '15px', color: 'var(--tp)' }}>
            Something went wrong rendering this component
          </h3>
          <p style={{ margin: 0, fontSize: '11px', color: 'var(--ts)', maxWidth: '400px' }}>
            {this.state.error?.message || "An unexpected rendering crash occurred."}
          </p>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload() }}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={12} /> Reload Application
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
