export function Skeleton({ type = 'text', count = 3 }: { type?: 'text' | 'card' | 'table'; count?: number }) {
  if (type === 'card') {
    return (
      <div className="stats-grid">
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="stat-card">
            <div className="skeleton skeleton-title" />
            <div className="skeleton skeleton-text" />
            <div className="skeleton skeleton-text" />
          </div>
        ))}
      </div>
    )
  }
  if (type === 'table') {
    return (
      <>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="skeleton skeleton-row" style={{ marginBottom: 8 }} />
        ))}
      </>
    )
  }
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton skeleton-text" />
      ))}
    </>
  )
}
