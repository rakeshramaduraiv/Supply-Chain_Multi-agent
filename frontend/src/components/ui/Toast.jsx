import { createContext, useContext, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'

const ToastCtx = createContext(null)

let id = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const add = useCallback((type, msg) => {
    const tid = ++id
    setToasts(t => [...t, { id: tid, type, msg }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== tid)), 4000)
  }, [])

  const ctx = {
    success: (msg) => add('success', msg),
    error: (msg) => add('error', msg),
    info: (msg) => add('info', msg),
  }

  return (
    <ToastCtx.Provider value={ctx}>
      {children}
      {createPortal(<ToastContainer toasts={toasts} />, document.body)}
    </ToastCtx.Provider>
  )
}

export function useToast() {
  return useContext(ToastCtx)
}

function ToastContainer({ toasts }) {
  if (!toasts.length) return null
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>{typeof t.msg === 'string' ? t.msg : JSON.stringify(t.msg)}</div>
      ))}
    </div>
  )
}
