import { useState, useEffect } from 'react'
import { Sprout, ChevronDown, Check, KeyRound, ArrowLeftRight, Settings, Plus, Archive, Trash2 } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { api } from '../lib/api.js'
import { Pop, PopItem, PopHead, PopSep, Badge } from './ui'
import { libelleRole } from '../lib/roles.js'
import PotagerSelector from './PotagerSelector.jsx'
import ParametresPotager from '../views/ParametresPotager.jsx'
import ModalCreerPotager from './ModalCreerPotager.jsx'
import ModalCorbeillePotagers from './ModalCorbeillePotagers.jsx'

/**
 * Sélecteur de potager [US-054].
 *
 * Remplace le bouton texte qui ouvrait directement une modale : le nom du
 * potager actif ouvre désormais un menu déroulant listant les potagers de
 * l'utilisateur (rôle, parcelles, membres), suivi des actions « Créer un
 * nouveau potager » (US-081), « Rejoindre un potager » et « Tous mes
 * potagers » [CA1, CA2].
 *
 * Aucune logique métier ici : la bascule et l'adhésion restent portées par
 * `PotagerContext` (US-046) et `PotagerSelector` (US-048).
 */
/** « Éditeur · 3 parcelles · 2 membres » — accorde les pluriels. */
function sousTitrePotager({ role, nb_parcelles = 0, nb_membres = 0 }) {
  const parcelles = `${nb_parcelles} parcelle${nb_parcelles > 1 ? 's' : ''}`
  const membres = `${nb_membres} membre${nb_membres > 1 ? 's' : ''}`
  return `${libelleRole(role)} · ${parcelles} · ${membres}`
}

export default function PotagerMenu() {
  const { potagers, potagerActif, activer, potagerId, setPotagerId } = usePotager()
  const [ouvert, setOuvert] = useState(false)
  const [modale, setModale] = useState(null) // null | 'liste' | 'rejoindre' | 'creer' | 'corbeille'
  const [bascule, setBascule] = useState(null)
  // [US-083 / CA6 révisé] Détail du potager consulté (archivé) — le bouton de
  // sélection en en-tête doit refléter le potager réellement affiché, pas
  // seulement le potager actif serveur ; `potagers` ne connaît que les actifs.
  const [potagerConsulteDetail, setPotagerConsulteDetail] = useState(null)
  // [US-083 / CA6] Potager ciblé par l'écran Paramètres — le potager actif via
  // l'entrée de menu, ou un potager archivé consulté explicitement depuis la
  // liste ci-dessous (jamais activable, CA6).
  const [parametresPotagerId, setParametresPotagerId] = useState(null)
  // [US-083 / CA6] Archivés masqués par défaut ; chargés à la demande, jamais
  // mélangés à `potagers` (qui ne connaît que les potagers actifs, US-080).
  const [voirArchives, setVoirArchives] = useState(false)
  const [archives, setArchives] = useState([])
  const [chargementArchives, setChargementArchives] = useState(false)

  useEffect(() => {
    if (!potagerId) { setPotagerConsulteDetail(null); return }
    api.potager(potagerId).then(setPotagerConsulteDetail).catch(() => {})
  }, [potagerId])

  // [CA3] Sans potager actif, rien à afficher : l'utilisateur est alors dirigé
  // vers l'assistant d'onboarding (Onboarding.jsx, US-058) par le PotagerGate d'App.jsx.
  if (!potagerActif) return null

  // [US-083 / CA6 révisé] Le geste de sélection reste unique, qu'un potager
  // soit archivé ou non : `selectionneId` est le potager réellement affiché
  // (consulté s'il y en a un, sinon l'actif serveur) — il pilote l'indicateur
  // de sélection courante du menu déroulant, indépendant du badge « actif ».
  const consultationArchive = potagerId != null
  const selectionneId = potagerId ?? potagerActif.id
  const nomAffiche = consultationArchive ? (potagerConsulteDetail?.nom ?? '…') : potagerActif.nom

  async function basculerVers(id) {
    if (bascule) {
      setOuvert(false)
      return
    }
    if (id === potagerActif.id) {
      // [US-083 / CA6 révisé] Revenir sur son potager actif depuis une
      // consultation archivée : même geste, pas d'activation serveur inutile.
      setPotagerId(null)
      setOuvert(false)
      return
    }
    setBascule(id)
    try {
      // [CA4] `activer()` recharge la page (comportement d'origine US-046 :
      // évite tout état obsolète dans les vues déjà montées).
      await activer(id)
    } catch {
      setBascule(null)
    }
  }

  async function basculerVoirArchives() {
    const prochain = !voirArchives
    setVoirArchives(prochain)
    if (prochain && archives.length === 0) {
      setChargementArchives(true)
      try {
        const res = await api.potagers('tous')
        setArchives(res.potagers.filter((p) => p.etat === 'archive'))
      } finally {
        setChargementArchives(false)
      }
    }
  }

  return (
    <div className="relative min-w-0">
      <button
        onClick={() => setOuvert((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={ouvert}
        aria-label="Changer de potager / rejoindre un potager"
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-[10px] max-w-[230px] min-w-0 ${
          consultationArchive ? 'bg-amber-soft text-amber' : 'bg-header-glass'
        }`}
      >
        {/* [US-083 / CA6 révisé] Variante « archivé » : icône et couleur
            reflètent le potager réellement affiché, pas le potager actif serveur. */}
        {consultationArchive
          ? <Archive size={15} className="shrink-0" />
          : <Sprout size={15} className="shrink-0" />}
        {/* [CA5] Troncature en ellipse plutôt que débordement du bandeau. */}
        <span className="text-[13px] font-semibold truncate min-w-0">{nomAffiche}</span>
        <ChevronDown size={14} className="shrink-0" />
      </button>

      {/* Largeur 320 : laisse tenir « Propriétaire · 12 parcelles · 8 membres »
          à côté du badge « actif » sans troncature. */}
      {ouvert && (
        <Pop width={320} onClose={() => setOuvert(false)}>
          <PopHead>Vos potagers · {potagers.length}</PopHead>

          {potagers.map((p) => (
            <PopItem
              key={p.id}
              // [US-083 / CA6 révisé] L'indicateur de sélection suit le potager
              // affiché (`selectionneId`), le badge « actif » reste indépendant
              // et reflète toujours l'état serveur réel (`p.actif`).
              icon={p.id === selectionneId ? Check : Sprout}
              tint={p.id === selectionneId ? 'brand' : undefined}
              label={p.nom}
              sub={bascule === p.id ? 'Basculement…' : sousTitrePotager(p)}
              onClick={() => basculerVers(p.id)}
              right={p.actif ? <Badge tint="brand">actif</Badge> : null}
            />
          ))}

          {/* [US-083 / CA6] Bascule d'affichage — masqués par défaut, jamais
              sélectionnables comme potager actif : un clic ouvre Paramètres
              en lecture (CA7) plutôt que de tenter une activation refusée. */}
          <PopItem
            icon={Archive}
            label={voirArchives ? 'Masquer les potagers archivés' : 'Voir les potagers archivés'}
            sub={chargementArchives ? 'Chargement…' : undefined}
            onClick={basculerVoirArchives}
          />
          {voirArchives && archives.map((p) => (
            <PopItem
              key={p.id}
              // [US-083 / CA6 révisé] Même indicateur de sélection que la liste
              // active, indépendant du badge « archivé » (toujours affiché ici).
              icon={p.id === selectionneId ? Check : Archive}
              tint={p.id === selectionneId ? 'brand' : undefined}
              label={p.nom}
              sub={sousTitrePotager(p)}
              // [US-083 / CA7] Clic sur potager archivé : le consulter en lecture seule
              onClick={() => {
                setOuvert(false)
                setPotagerId(p.id)
              }}
              right={<Badge tint="amber">archivé</Badge>}
            />
          ))}

          <PopSep />

          {/* [US-081 / CA1] Seul chemin de création une fois l'onboarding passé
              (le PotagerGate d'App.jsx ne le déclenche plus dès qu'un potager
              existe). Visible quel que soit le rôle sur le potager actif :
              créer SON potager ne dépend d'aucun rôle. */}
          <PopItem
            icon={Plus}
            label="Créer un nouveau potager"
            sub="Un autre jardin réel"
            onClick={() => {
              setOuvert(false)
              setModale('creer')
            }}
          />

          {/* [US-084 / CA6] Corbeille — point d'accès dédié à la restauration.
              Voisine immédiate de « Voir les potagers archivés » : les deux
              montrent des potagers absents de la liste principale, à un stade
              différent du cycle de vie. Le décompte n'est pas préchargé ici :
              la corbeille est vide en régime normal, la charger à chaque
              ouverture du menu coûterait une requête pour rien. */}
          <PopItem
            icon={Trash2}
            label="Corbeille"
            sub="Restaurer un potager supprimé"
            onClick={() => {
              setOuvert(false)
              setModale('corbeille')
            }}
          />

          {/* [CA2] Seul accès permanent au code d'invitation (cf. US-048 / CA4). */}
          <PopItem
            icon={KeyRound}
            label="Rejoindre un potager"
            sub="Avec un code d'invitation"
            onClick={() => {
              setOuvert(false)
              setModale('rejoindre')
            }}
          />
          <PopItem
            icon={ArrowLeftRight}
            label="Tous mes potagers"
            sub="Comparer et basculer"
            onClick={() => {
              setOuvert(false)
              setModale('liste')
            }}
          />

          {/* [US-082 / CA1, CA6] Remplace « Modifier le potager » (US-074) — pas de
              doublon d'accès. Visible quel que soit le rôle : l'écran lui-même
              adapte son contenu (lecture seule pour editor/lecteur, CA6). */}
          <PopItem
            icon={Settings}
            label="Paramètres du potager"
            sub="Identité, membres, cycle de vie"
            onClick={() => {
              setOuvert(false)
              setParametresPotagerId(potagerActif.id)
            }}
          />
        </Pop>
      )}

      {(modale === 'liste' || modale === 'rejoindre') && (
        <PotagerSelector focusCode={modale === 'rejoindre'} onClose={() => setModale(null)} />
      )}
      {parametresPotagerId != null && (
        <ParametresPotager potagerId={parametresPotagerId} onClose={() => setParametresPotagerId(null)} />
      )}
      {modale === 'creer' && <ModalCreerPotager onClose={() => setModale(null)} />}
      {/* [US-084 / CA6] Un potager restauré revient ARCHIVÉ : il ne réapparaît
          pas dans `potagers` (actifs seuls) mais dans la liste des archivés,
          rechargée à la demande — d'où la remise à zéro de ce cache local. */}
      {modale === 'corbeille' && (
        <ModalCorbeillePotagers
          onClose={() => setModale(null)}
          onRestaure={() => { setArchives([]); setVoirArchives(false) }}
        />
      )}
    </div>
  )
}
