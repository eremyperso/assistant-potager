export default function LoadingSkeleton({ lines = 3 }) {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="bg-g-card border border-g-brd rounded-2xl p-4 space-y-2">
          <div className="h-3 bg-g-brd rounded w-2/5" />
          <div className="h-10 bg-g-brd rounded" />
          <div className="h-3 bg-g-brd rounded w-3/5" />
        </div>
      ))}
    </div>
  )
}
