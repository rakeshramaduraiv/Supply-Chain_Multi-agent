import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

export default function Modal({ open, onClose, title, subtitle, children, width = 560 }) {
  if (!open) return null
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ width: `${width}px` }} onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <span className="modal-title">{title}</span>
            {subtitle && <div className="modal-subtitle">{subtitle}</div>}
          </div>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>,
    document.body
  )
}
