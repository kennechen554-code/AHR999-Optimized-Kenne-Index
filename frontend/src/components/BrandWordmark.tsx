interface BrandWordmarkProps {
  caption?: string
  compact?: boolean
}

function BrandWordmark({ caption, compact = false }: BrandWordmarkProps) {
  return (
    <div className={`brand-wordmark ${compact ? 'brand-wordmark-compact' : ''}`}>
      <div className="brand-wordmark-main" aria-label="KENNE INDEX">
        <span>KENNE</span>
        <span className="brand-wordmark-slash">/</span>
        <span>INDEX</span>
      </div>
      {caption && <div className="brand-wordmark-caption">{caption}</div>}
    </div>
  )
}

export default BrandWordmark
