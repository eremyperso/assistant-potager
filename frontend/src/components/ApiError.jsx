import { AlertTriangle, RefreshCw } from 'lucide-react'

export default function ApiError({ message = 'Données indisponibles', onRetry }) {
  return (
    <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl p-4 flex flex-col items-center gap-3 text-center">
      <AlertTriangle className="text-red-500" size={24} />
      <p className="text-sm text-red-700 dark:text-red-300">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg px-3 py-1.5 hover:bg-red-100 dark:hover:bg-red-900 transition-colors"
        >
          <RefreshCw size={12} />
          Réessayer
        </button>
      )}
    </div>
  )
}
