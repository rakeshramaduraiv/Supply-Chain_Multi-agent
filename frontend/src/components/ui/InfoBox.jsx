import { Info, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'

const ICONS = { info: Info, warn: AlertTriangle, error: AlertCircle, success: CheckCircle }

export default function InfoBox({ type = 'info', children }) {
  const Icon = ICONS[type]
  return (
    <div className={`info-box ${type}`}>
      <Icon size={14} style={{ flexShrink: 0, marginTop: 1 }} />
      <div>{children}</div>
    </div>
  )
}
