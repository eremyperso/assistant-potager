// [US-082] Écran « Paramètres du potager » — regroupe l'identité (US-074
// absorbée : renommer, localiser), les membres (US-048 intégrée, sans
// duplication) et l'emplacement d'accueil des actions de cycle de vie livrées
// par US-083 (archiver/désarchiver), US-084 (supprimer), US-085 (transférer
// la propriété) et US-086 (quitter).
//
// Rendu en overlay `Modal`, comme les autres destinations ouvertes depuis
// PotagerMenu (ModalCreerPotager, PotagerSelector…) — ce projet n'a pas de
// librairie de routage (cf. App.jsx / VIEWS), un « écran » atteint depuis un
// menu y vit donc comme une modale plein contenu, pas comme une vue routée.
//
// [US-083 / CA7] `potagerId` (prop optionnelle, défaut : potager actif) rend
// l'écran consultable sur un AUTRE potager que celui de l'utilisateur — cas
// d'un potager archivé, jamais sélectionnable comme potager actif (CA6), mais
// « consultable en lecture via un accès explicite depuis la liste des
// archivés ». Dans ce cas `detail` (GET /potagers/{id}) est la SEULE source de
// vérité : `potagerActif` décrit un potager différent, le préremplissage
// optimiste ne s'applique qu'en consultant son propre potager actif.
import { useState, useEffect, useCallback } from 'react'
import { Settings, Archive, ArchiveRestore } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { api } from '../lib/api.js'
import { libelleRole, teinteRole } from '../lib/roles.js'
import { Modal, Card, SectionLabel, Field, VilleSearch, Btn, Badge, InfoBanner } from '../components/ui'
import GestionMembres from '../components/GestionMembres.jsx'
import ModalArchiverPotager from '../components/ModalArchiverPotager.jsx'

const LIBELLE_ETAT = { actif: 'Actif', archive: 'Archivé', supprime: 'Supprimé' }

export default function ParametresPotager({ potagerId: potagerIdProp, onClose }) {
  const { potagerActif, modifierPotager, recharger } = usePotager()
  const potagerId = potagerIdProp ?? potagerActif?.id
  // [CA7] Son propre potager actif : préremplissage optimiste possible (pas de
  // flash). Un autre potager consulté explicitement : on attend `detail`.
  const estPotagerActif = potagerId === potagerActif?.id

  const [detail, setDetail] = useState(null)
  const [moiId, setMoiId] = useState(null)
  const [modaleArchiver, setModaleArchiver] = useState(false)
  const [erreurLifecycle, setErreurLifecycle] = useState(null)
  const [loadingLifecycle, setLoadingLifecycle] = useState(false)

  const [nom, setNom] = useState(estPotagerActif ? potagerActif?.nom || '' : '')
  const [localisation, setLocalisation] = useState(
    estPotagerActif && potagerActif?.latitude != null && potagerActif?.longitude != null
      ? { ville: potagerActif.ville || '', latitude: potagerActif.latitude, longitude: potagerActif.longitude }
      : null
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const charger = useCallback(() => {
    if (!potagerId) return
    api.potager(potagerId).then((d) => {
      setDetail(d)
      // [CA7] Consultation d'un autre potager : le formulaire ne se remplit
      // qu'une fois `detail` connu — jamais depuis `potagerActif`, qui décrit
      // un potager différent.
      if (!estPotagerActif) {
        setNom(d.nom)
        setLocalisation(
          d.latitude != null && d.longitude != null
            ? { ville: d.ville || '', latitude: d.latitude, longitude: d.longitude }
            : null
        )
      }
    }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [potagerId])

  useEffect(() => { charger() }, [charger])
  useEffect(() => { api.moi().then((m) => setMoiId(m.id)).catch(() => {}) }, [])

  if (!potagerId) return null

  const role = detail?.role ?? (estPotagerActif ? potagerActif.role : null)
  const etat = detail?.etat ?? (estPotagerActif ? potagerActif.etat : null)
  // [CA2, CA6 (non-régression US-074)] Jamais de valeur inventée.
  const ville = detail?.ville ?? (estPotagerActif ? potagerActif.ville : undefined)
  const nomAffiche = detail?.nom ?? (estPotagerActif ? potagerActif.nom : '…')
  const nbParcelles = detail?.nb_parcelles ?? (estPotagerActif ? potagerActif.nb_parcelles : 0) ?? 0
  const nbMembres = detail?.nb_membres ?? (estPotagerActif ? potagerActif.nb_membres : 0) ?? 0
  // [CA3, CA6] Seul l'owner modifie — un editor/lecteur consulte (CA8 : y
  // compris sur un potager archivé, aucune restriction supplémentaire ici).
  const estOwner = role === 'owner'
  const estArchive = etat === 'archive'

  async function handleSubmit(e) {
    e.preventDefault()
    if (loading || !nom.trim()) return
    setLoading(true)
    setError(null)
    try {
      await modifierPotager(potagerId, {
        nom: nom.trim(),
        ville: localisation?.ville,
        latitude: localisation?.latitude,
        longitude: localisation?.longitude,
      })
      charger()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // [US-083 / CA7 révisé] Même convention que activer/creerPotager/accepterInvitation
  // (PotagerContext.jsx) : un rechargement complet plutôt qu'une synchronisation
  // manuelle multi-composants (bandeau + bouton + menu) — cette dernière est la
  // cause directe de la régression « on reste sur cette modale » observée en
  // retour terrain. [CA8] Le potager actif de personne n'est rebasculé : le
  // reload ne fait que rafraîchir l'affichage client, pas l'état serveur.
  async function handleDesarchiver() {
    setLoadingLifecycle(true)
    setErreurLifecycle(null)
    try {
      await api.desarchiverPotager(potagerId)
      window.location.reload()
    } catch (e) {
      setErreurLifecycle(e.message)
      setLoadingLifecycle(false)
    }
  }

  // [US-083 / CA5] Si le potager archivé était le potager actif de
  // l'utilisateur, celui-ci vient d'être invalidé côté serveur — un
  // rechargement complet reflète la bascule automatique (même principe que
  // PotagerContext.activer/creerPotager). Sinon (potager consulté
  // explicitement, jamais actif — CA6), un simple rafraîchissement suffit.
  function handleArchive() {
    if (estPotagerActif) {
      window.location.reload()
    } else {
      recharger({ silencieux: true })
      charger()
    }
  }

  return (
    <Modal title="Paramètres du potager" icon={Settings} sub={nomAffiche} onClose={onClose} width={620}>
      <div className="@container/parametres flex flex-col gap-4">
        {/* [CA2] Identité en tête : nom (cf. sous-titre du Modal), ville ou mention
            explicite, état, rôle de l'utilisateur courant, compteurs. */}
        <div className="flex flex-wrap items-center gap-2">
          {role && <Badge tint={teinteRole(role)}>{libelleRole(role)}</Badge>}
          {etat && <Badge tint={estArchive ? 'amber' : 'brand'}>{LIBELLE_ETAT[etat] || etat}</Badge>}
          <span className="text-[12.5px] text-txt3">
            {ville || 'Localisation non renseignée'} · {nbParcelles} parcelle{nbParcelles > 1 ? 's' : ''} ·{' '}
            {nbMembres} membre{nbMembres > 1 ? 's' : ''}
          </span>
        </div>

        {/* [CA7] Bandeau permanent sur un potager archivé, quel que soit le rôle. */}
        {estArchive && (
          <InfoBanner
            tint="amber"
            dismissible={false}
            icon={Archive}
            title="Potager archivé — lecture seule"
            body="Consultation possible, mais plus aucun événement ne peut y être enregistré tant qu'il n'est pas désarchivé."
          />
        )}

        {/* [CA6] Explique en une phrase pourquoi aucune action n'est proposée. */}
        {!estOwner && (
          <InfoBanner
            tint="brand"
            dismissible={false}
            title="Accès en lecture seule"
            body="Seul le propriétaire du potager peut modifier ces réglages."
          />
        )}

        {/* [CA3] Section Identité — édition réservée à l'owner, lecture pour les autres. */}
        <Card>
          <SectionLabel>Identité</SectionLabel>
          {estOwner ? (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
              <Field
                id="parametres-potager-nom"
                label="Nom du potager"
                required
                value={nom}
                onChange={(e) => setNom(e.target.value)}
              />
              {/* [CA1, CA7] Recherche facultative — rien n'empêche d'enregistrer sans ville. */}
              <VilleSearch
                id="parametres-potager-ville"
                label="Ville"
                value={localisation}
                onSelect={setLocalisation}
                placeholder="Rechercher une ville…"
                hint="Facultatif — sert à personnaliser la météo du potager."
              />
              {error && <p className="text-[13px] text-red">{error}</p>}
              <Btn
                type="submit"
                kind="primary"
                disabled={loading || !nom.trim()}
                className="self-start @[420px]/parametres:self-end"
              >
                {loading ? 'Enregistrement…' : 'Enregistrer'}
              </Btn>
            </form>
          ) : (
            <div className="flex flex-col gap-1 text-[13.5px]">
              <span className="font-semibold text-txt">{nomAffiche}</span>
              {/* [CA6, non-régression US-074/CA6] Jamais de valeur inventée. */}
              <span className="text-txt2">{ville || 'Localisation non renseignée'}</span>
            </div>
          )}
        </Card>

        {/* [CA4] Section Membres — même composant que le menu Compte (US-048),
            sans dupliquer la logique liste/invitation/retrait. */}
        <Card>
          <SectionLabel>Membres</SectionLabel>
          <GestionMembres embedded potagerId={potagerId} moiId={moiId} lectureSeule={!estOwner} />
        </Card>

        {/* [US-083 / CA5, CA8] Zone sensible — n'affiche que les actions
            réellement disponibles pour cet état (jamais de bouton factice) :
            archiver sur un potager actif, désarchiver sur un potager archivé.
            US-084/085/086 y ajouteront leurs propres actions. */}
        {estOwner && (
          <Card bg="bg-red-soft">
            <SectionLabel>Zone sensible</SectionLabel>
            {erreurLifecycle && <p className="text-red text-[13px] mb-2">{erreurLifecycle}</p>}
            <div className="flex flex-col gap-2">
              {!estArchive ? (
                <Btn
                  kind="ghost"
                  icon={Archive}
                  onClick={() => setModaleArchiver(true)}
                  className="justify-start text-txt"
                >
                  Archiver ce potager
                </Btn>
              ) : (
                <Btn
                  kind="ghost"
                  icon={ArchiveRestore}
                  onClick={handleDesarchiver}
                  disabled={loadingLifecycle}
                  className="justify-start text-txt"
                >
                  {loadingLifecycle ? 'Désarchivage…' : 'Désarchiver ce potager'}
                </Btn>
              )}
            </div>
          </Card>
        )}
      </div>

      {modaleArchiver && (
        <ModalArchiverPotager
          potagerId={potagerId}
          nom={nomAffiche}
          onClose={() => setModaleArchiver(false)}
          onArchive={() => {
            setModaleArchiver(false)
            handleArchive()
          }}
        />
      )}
    </Modal>
  )
}
