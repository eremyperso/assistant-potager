import { AlertTriangle, RefreshCw } from 'lucide-react'

export default function ApiError({ message = 'Données indisponibles', onRetry }) {
  return (
    <div
      className="rounded-2xl p-4 flex flex-col items-center gap-3 text-center"
      style={{ background: 'var(--g-red-dim)', border: '1px solid var(--g-red)' }}
    >
      <AlertTriangle size={24} style={{ color: 'var(--g-red)' }} />
      <p className="text-sm" style={{ color: 'var(--g-red)' }}>{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 text-sm rounded-xl px-3.5 py-1.5 border transition-colors"
          style={{ color: 'var(--g-red)', borderColor: 'var(--g-red)', background: 'transparent' }}
        >
          <RefreshCw size={13} />
          Réessayer
        </button>
      )}
    </div>
  )
}
