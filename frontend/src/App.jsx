import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HashRouter } from 'react-router-dom'
import { ToastProvider } from './components/ui/Toast'
import AppShell from './components/layout/AppShell'
import ErrorBoundary from './components/ui/ErrorBoundary'

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      staleTime: 5_000,
      refetchInterval: 15_000, // Background poll fallback
      refetchOnWindowFocus: true,
    }
  }
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <HashRouter>
        <ToastProvider>
          <ErrorBoundary>
            <AppShell />
          </ErrorBoundary>
        </ToastProvider>
      </HashRouter>
    </QueryClientProvider>
  )
}
