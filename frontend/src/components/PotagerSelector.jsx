// [US-046 / CA2] Modal de sélection du potager actif.
import { useState } from 'react'
import { X, Sprout, Check } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'

export default function PotagerSelector({ onClose }) {
  const { potagers, activer } = usePotager()
  const [enCours, setEnCours] = useState(null)

  async function handleSelect(potagerId) {
    if (enCours) return
    setEnCours(potagerId)
    try {
      await activer(potagerId)
      // activer() recharge la page — pas besoin de fermer la modale manuellement
    } catch {
      setEnCours(null)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-6"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-xs"
        style={{ background: 'var(--g-card)', border: '1px solid var(--g-brd)', borderRadius: 18, padding: 20 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="flex items-center gap-2 font-semibold text-g-pri">
            <Sprout size={16} /> Vos potagers
          </span>
          <button onClick={onClose} aria-label="Fermer" className="text-g-sec hover:text-g-pri">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-2">
          {potagers.map((p) => (
            <button
              key={p.id}
              onClick={() => handleSelect(p.id)}
              disabled={Boolean(enCours)}
              className="flex items-center justify-between"
              style={{
                background: p.actif ? 'var(--g-acc-dim)' : 'var(--g-sur)',
                border: '1px solid var(--g-brd)',
                borderRadius: 12,
                padding: '10px 12px',
                color: 'var(--g-pri)',
                opacity: enCours && enCours !== p.id ? 0.5 : 1,
              }}
            >
              <span>{p.nom}</span>
              {p.actif && <Check size={16} color="var(--g-acc)" />}
              {enCours === p.id && <span style={{ fontSize: 12, color: 'var(--g-sec)' }}>…</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
