// [US-059 CA1] Écran d'erreur d'appel serveur — tokens sémantiques uniquement.
// Bouton habillé sur place plutôt que via `Btn` : aucune variante du design
// system n'est déclinée en rouge, et surcharger celle qui s'en approche ferait
// dépendre le rendu de l'ordre du CSS généré.
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default function ApiError({ message = 'Données indisponibles', onRetry }) {
  return (
    <div className="rounded-2xl p-4 flex flex-col items-center gap-3 text-center bg-red-soft border border-red">
      <AlertTriangle size={24} className="text-red" />
      <p className="text-sm text-red">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 text-[13.5px] font-semibold rounded-[10px] px-3.5 py-1.5
                     bg-transparent border border-red text-red transition-colors"
        >
          <RefreshCw size={13} />
          Réessayer
        </button>
      )}
    </div>
  )
}
