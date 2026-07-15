import { useRef, useState } from 'react'
import { Upload, X } from 'lucide-react'

export default function UploadZone({ onFile, accept = '.csv', hint, hasFile, fileName, onClear, disabled }) {
  const inputRef = useRef(null)
  const [drag, setDrag] = useState(false)

  const handle = (file) => { if (file && onFile) onFile(file) }

  const onDrop = (e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]) }
  const onDragOver = (e) => { e.preventDefault(); setDrag(true) }
  const onDragLeave = () => setDrag(false)
  const onChange = (e) => { handle(e.target.files[0]); e.target.value = '' }

  if (hasFile && fileName) {
    return (
      <div className="upload-zone has-file">
        <span className="upload-file-name">{fileName}</span>
        <button className="btn btn-ghost" onClick={onClear} style={{ padding: '2px 6px' }}><X size={14} /></button>
      </div>
    )
  }

  return (
    <div className={`upload-zone${drag ? ' drag' : ''}${disabled ? ' disabled' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}>
      <Upload size={20} color="var(--tm)" />
      <span className="upload-hint">{hint || `Drop ${accept} file or click to browse`}</span>
      <input ref={inputRef} type="file" accept={accept} hidden onChange={onChange} />
    </div>
  )
}
