// [US-081] Modale « Créer un nouveau potager » — création d'un potager
// additionnel (résidence secondaire, jardin partagé, potager d'un proche),
// jusqu'ici possible uniquement à l'onboarding (Onboarding.jsx, US-058).
//
// Action rare et explicite : ni étape parcelles, ni étape cultures (CA2) —
// l'utilisateur est déjà expérimenté et complétera dans les écrans dédiés.
//
// Composant réutilisable au sens de CLAUDE.md (règle des container queries) :
// le wrapper porte donc `@container`, jamais de breakpoint d'écran.
import { useState } from 'react'
import { Sprout, AlertTriangle } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { Modal, Field, VilleSearch, Btn, InfoBanner } from './ui'

export default function ModalCreerPotager({ onClose }) {
  const { potagers, creerPotager } = usePotager()
  const [nom, setNom] = useState('')
  // [CA2] Localisation facultative, même composant de recherche qu'US-074.
  const [localisation, setLocalisation] = useState(null)
  // [CA3] Cochée par défaut : le cas courant reste « je crée et j'y vais ».
  const [basculer, setBasculer] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // [CA7] Nom en double : autorisé (deux jardins peuvent légitimement porter le
  // même nom), simplement signalé — jamais bloquant.
  const nomNettoye = nom.trim()
  const doublon = nomNettoye !== '' && potagers.some(
    (p) => p.nom.trim().toLowerCase() === nomNettoye.toLowerCase()
  )

  async function handleSubmit(e) {
    e.preventDefault()
    // [CA7] Un nom vide ou uniquement composé d'espaces ne part jamais au serveur.
    if (loading || !nomNettoye) return
    setLoading(true)
    setError(null)
    try {
      // [CA5] Avec bascule, `creerPotager` recharge l'application sur le nouveau
      // potager ; sans bascule, il rafraîchit simplement la liste en silence.
      await creerPotager(
        nomNettoye,
        localisation?.ville,
        localisation?.latitude,
        localisation?.longitude,
        basculer
      )
      onClose()
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <Modal title="Créer un nouveau potager" icon={Sprout} onClose={onClose} width={420}>
      <form onSubmit={handleSubmit} className="@container/creer flex flex-col gap-3.5">
        {/* [CA6] Anti-cas « un potager par saison » — rappelé avant la saisie,
            pour éviter la création plutôt que de la corriger après coup. */}
        <InfoBanner
          tint="amber"
          dismissible={false}
          title="Une nouvelle saison ?"
          body="Ce n'est pas un nouveau potager — utilise la clôture de saison pour repartir à zéro dans le même jardin."
        />

        <Field
          id="creer-potager-nom"
          label="Nom du potager"
          required
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="Jardin de Bretagne"
        />
        {doublon && (
          <p className="flex items-start gap-1.5 -mt-2 text-[12px] text-amber">
            <AlertTriangle size={14} className="shrink-0 mt-px" />
            Tu as déjà un potager portant ce nom. Ce n'est pas bloquant, mais les deux
            seront difficiles à distinguer dans le sélecteur.
          </p>
        )}

        {/* [CA2] Facultative : rien n'empêche de créer un potager sans ville. */}
        <VilleSearch
          id="creer-potager-ville"
          label="Ville"
          value={localisation}
          onSelect={setLocalisation}
          placeholder="Rechercher une ville…"
          hint="Facultatif — sert à personnaliser la météo du potager."
        />

        {/* [CA3] Bascule explicite : décochée, l'utilisateur reste sur son
            potager courant (cas du jardinier en pleine saison). */}
        <label className="flex items-start gap-2.5 cursor-pointer">
          <input
            type="checkbox"
            checked={basculer}
            onChange={(e) => setBasculer(e.target.checked)}
            className="mt-0.5 w-4 h-4 shrink-0 accent-brand"
          />
          <span className="text-[13px] text-txt2 leading-snug">
            En faire mon potager actif dès maintenant
          </span>
        </label>

        {error && <p className="text-[13px] text-red">{error}</p>}

        {/* Actions empilées dans une colonne étroite (menu déroulant), alignées
            à droite dès que la modale a la place — container query, pas
            breakpoint : ce formulaire vit dans deux contextes de layout. */}
        <div className="flex flex-col gap-2 @[340px]/creer:flex-row @[340px]/creer:justify-end">
          <Btn type="button" kind="ghost" onClick={onClose} className="justify-center">
            Annuler
          </Btn>
          <Btn type="submit" kind="primary" disabled={loading || !nomNettoye} className="justify-center">
            {loading ? 'Création…' : 'Créer le potager'}
          </Btn>
        </div>
      </form>
    </Modal>
  )
}
