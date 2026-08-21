// [US-084 / CA6] Corbeille des potagers supprimés — point d'accès dédié du
// droit au remords, seul endroit de l'application où un potager supprimé
// réapparaît (US-080 / CA7 : il est invisible partout ailleurs, `etat=tous`
// compris). Restaurer le fait revenir à l'état ARCHIVÉ, jamais directement
// actif : reprendre l'écriture reste un geste explicite de désarchivage.
import { useState, useEffect, useCallback } from 'react'
import { Trash2, RotateCcw } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Card, Btn, Badge } from './ui'

/** « 12/09/2026 » — date de purge, affichée telle que le serveur la calcule. */
function formaterDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export default function ModalCorbeillePotagers({ onClose, onRestaure }) {
  const [potagers, setPotagers] = useState(null)
  const [enCours, setEnCours] = useState(null)
  const [error, setError] = useState(null)

  const charger = useCallback(() => {
    api.corbeillePotagers()
      .then((res) => setPotagers(res.potagers))
      .catch((e) => { setPotagers([]); setError(e.message) })
  }, [])

  useEffect(() => { charger() }, [charger])

  async function restaurer(potagerId) {
    setEnCours(potagerId)
    setError(null)
    try {
      await api.restaurerPotager(potagerId)
      onRestaure?.()
      charger()
    } catch (e) {
      setError(e.message)
    } finally {
      setEnCours(null)
    }
  }

  return (
    <Modal title="Corbeille" icon={Trash2} sub="Potagers supprimés restaurables" onClose={onClose} width={520}>
      <div className="@container/corbeille flex flex-col gap-3">
        {error && <p className="text-red text-[13px]">{error}</p>}

        {potagers === null && <p className="text-[13px] text-txt3">Chargement…</p>}

        {/* `Placeholder` du design system est réservé aux écrans « à venir »
            (il annonce une prochaine version) — ici l'état vide est un état
            normal et définitif, pas une fonctionnalité manquante. */}
        {potagers?.length === 0 && (
          <p className="text-[13.5px] text-txt2 leading-relaxed">
            Aucun potager supprimé — rien à restaurer.
          </p>
        )}

        {potagers?.map((p) => (
          <Card key={p.id} className="flex flex-col gap-2 @[420px]/corbeille:flex-row @[420px]/corbeille:items-center">
            <div className="flex flex-col gap-1 min-w-0 flex-1">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[13.5px] font-semibold text-txt truncate">{p.nom}</span>
                <Badge tint="red">supprimé</Badge>
              </div>
              {/* [CA7] La date de purge est annoncée, jamais implicite. */}
              <span className="text-[12.5px] text-txt3">
                Effacement définitif le {formaterDate(p.purge_prevue_le)}
              </span>
            </div>
            <Btn
              kind="ghost"
              icon={RotateCcw}
              disabled={enCours === p.id}
              onClick={() => restaurer(p.id)}
              className="shrink-0"
            >
              {enCours === p.id ? 'Restauration…' : 'Restaurer'}
            </Btn>
          </Card>
        ))}

        {potagers?.length > 0 && (
          <p className="text-[12.5px] text-txt3 leading-relaxed">
            Un potager restauré revient à l'état archivé (lecture seule) — désarchive-le
            depuis ses paramètres pour y écrire à nouveau.
          </p>
        )}
      </div>
    </Modal>
  )
}
