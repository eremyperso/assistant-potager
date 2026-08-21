// [US-084 / CA3, CA4, CA type] Confirmation de suppression définitive d'un
// potager archivé — en deux temps, comme ModalArchiverPotager (US-083), mais
// nettement plus engageante : l'archivage se défait d'un clic, la suppression
// ouvre un compte à rebours de 30 jours au terme duquel les données n'existent
// plus. D'où la teinte rouge sur les deux étapes (l'archivage, réversible,
// reste ambre), le décompte réel de ce qui sera perdu (CA3) et la re-saisie du
// mot de passe (CA4) — jamais un simple bouton « Confirmer ».
import { useState, useEffect } from 'react'
import { Trash2, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Btn, Field } from './ui'

/** « 214 événements » / « 1 parcelle » — accorde le pluriel, jamais de 0 masqué. */
function ligneImpact(nombre, singulier, pluriel = null) {
  const mot = nombre > 1 ? (pluriel ?? `${singulier}s`) : singulier
  return `${nombre} ${mot}`
}

export default function ModalSupprimerPotager({ potagerId, nom, onClose, onSupprime }) {
  const [etape, setEtape] = useState('impact') // 'impact' | 'confirmer' | 'abandonne'
  const [impact, setImpact] = useState(null)
  const [motDePasse, setMotDePasse] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // [CA3] Chiffres calculés côté serveur — la modale n'estime rien elle-même.
  useEffect(() => {
    api.impactSuppressionPotager(potagerId).then(setImpact).catch((e) => setError(e.message))
  }, [potagerId])

  async function confirmer(e) {
    e.preventDefault()
    if (loading || !motDePasse) return
    setLoading(true)
    setError(null)
    try {
      const resultat = await api.supprimerPotager(potagerId, motDePasse)
      onSupprime?.(resultat)
    } catch (err) {
      setMotDePasse('')
      setLoading(false)
      setError(err.message)
      // [CA4] Au troisième échec, l'opération est abandonnée : plus de champ de
      // saisie, il faut ressortir et tout reprendre — un quatrième essai serait
      // de toute façon refusé côté serveur.
      if (err.code === 'trop_d_echecs') setEtape('abandonne')
    }
  }

  return (
    <Modal title="Supprimer définitivement" icon={Trash2} sub={nom} onClose={onClose} width={460}>
      {etape === 'impact' ? (
        <div className="@container/suppr">
          {/* [CA3] Décompte réel de ce qui sera perdu, avant toute confirmation. */}
          <p className="text-[13.5px] text-txt leading-relaxed mb-3">
            La suppression de « {nom} » entraînera la perte définitive de :
          </p>
          {impact ? (
            <ul className="flex flex-col gap-1.5 mb-4 text-[13.5px] text-txt">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red shrink-0" />
                {ligneImpact(impact.nb_evenements, 'événement')}
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red shrink-0" />
                {ligneImpact(impact.nb_parcelles, 'parcelle')}
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red shrink-0" />
                {ligneImpact(impact.nb_photos, 'photo')}
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red shrink-0" />
                {/* Les membres perdent l'accès, ils ne sont pas supprimés eux-mêmes. */}
                {ligneImpact(impact.nb_membres, 'membre')} perdront leur accès
              </li>
            </ul>
          ) : (
            <p className="text-[13px] text-txt3 mb-4">{error || 'Calcul en cours…'}</p>
          )}
          {/* [CA6] Le droit au remords est annoncé AVANT la confirmation, pas
              découvert après coup. */}
          <p className="text-[13px] text-txt2 leading-relaxed mb-4">
            Le potager disparaîtra immédiatement pour tous ses membres. Ses données
            seront effacées définitivement dans {impact?.delai_grace_jours ?? 30} jours —
            d'ici là, tu peux encore le restaurer depuis la corbeille.
          </p>
          <div className="flex items-center justify-end gap-2">
            <Btn kind="ghost" onClick={onClose}>Annuler</Btn>
            <Btn
              kind="soft"
              className="text-red border-red/40"
              disabled={!impact}
              onClick={() => setEtape('confirmer')}
            >
              Continuer
            </Btn>
          </div>
        </div>
      ) : etape === 'abandonne' ? (
        <>
          <p className="flex items-start gap-2 text-[13.5px] text-txt leading-relaxed mb-4">
            <AlertTriangle size={16} className="text-red shrink-0 mt-0.5" />
            {error} Le potager « {nom} » n'a pas été supprimé.
          </p>
          <div className="flex items-center justify-end">
            <Btn kind="ghost" onClick={onClose}>Fermer</Btn>
          </div>
        </>
      ) : (
        <form onSubmit={confirmer}>
          <p className="flex items-start gap-2 text-[13.5px] text-txt leading-relaxed mb-4">
            <AlertTriangle size={16} className="text-red shrink-0 mt-0.5" />
            Saisis ton mot de passe pour confirmer la suppression de « {nom} ».
          </p>
          {/* [CA4] Re-saisie du mot de passe du compte web (US-044). */}
          <Field
            id="suppr-potager-mdp"
            label="Mot de passe"
            type="password"
            required
            autoComplete="current-password"
            value={motDePasse}
            onChange={(e) => setMotDePasse(e.target.value)}
            className="mb-3"
          />
          {error && <p className="text-red text-[13px] mb-2">{error}</p>}
          <div className="flex items-center justify-end gap-2">
            <Btn type="button" kind="ghost" onClick={onClose} disabled={loading}>Annuler</Btn>
            <Btn
              type="submit"
              kind="soft"
              className="text-red border-red/40"
              disabled={loading || !motDePasse}
            >
              {loading ? '…' : 'Oui, supprimer ce potager'}
            </Btn>
          </div>
        </form>
      )}
    </Modal>
  )
}
