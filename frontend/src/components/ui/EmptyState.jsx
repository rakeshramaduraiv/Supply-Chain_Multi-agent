export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="empty-state">
      {Icon && <Icon size={28} color="var(--tm)" />}
      {title && <div className="empty-title">{title}</div>}
      {description && <div className="empty-desc">{description}</div>}
      {action && <div style={{ marginTop: '10px' }}>{action}</div>}
    </div>
  )
}
