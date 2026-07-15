export default function Spinner({ size = 'md', centered, text }) {
  const px = size === 'sm' ? '14px' : '18px'
  return (
    <div className={`spinner-wrap${centered ? ' centered' : ''}`}>
      <div className="spinner" style={{ width: px, height: px }} />
      {text && <span className="spinner-text">{text}</span>}
    </div>
  )
}
