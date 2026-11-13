// [US-330, US-331] Le détail d'une parcelle, ouvert dans le Plan (D1 à D6).
//
// Reprend, sans second dessin, les cartes de l'ancien onglet « Parcelles » (US-229 à US-232) :
// « Caractéristiques » (modifiable, US-230 / US-331), « Rotation » (US-231) et « Sol et
// entretien » (US-232). Elles se rangent en quatre onglets — En place, Caractéristiques,
// Rotation, Entretien ; une pépinière a « Lots » à la place de « En place » et pas de Rotation.
//
// Tout se calcule dans `lib/planParcelles.js` ; aucune lecture ici : le plan a déjà servi
// `GET /plan` (parcelle, vocabulaires, gestes de sol).
import { useState, useEffect, useMemo } from 'react'
import { Copy, Check, X } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  detailDeParcelle,
  carteSol,
  chargeUtile, avertissementsBascule, messageConfirmation, CHAMP_API,
  CHOIX_NON_RENSEIGNE, LIBELLE_NON_RENSEIGNE,
  SAISIE_DEDUITE, SAISIE_LISTE, SAISIE_NOMBRE, SAISIE_OUI_NON,
} from '../lib/planParcelles.js'
import { ObservationIcon, ObservationPanel } from './Observations.jsx'
import { useObservations } from '../hooks/useObservations.js'
import { ObservationsUIProvider } from '../context/ObservationsUIContext.jsx'
import { Card, Btn } from './ui'
import BoutonGeste from './BoutonGeste.jsx'
import { LigneChemin } from './PlanMobile.jsx'
import {
  ongletsDeParcelle, ongletValide, pictoParcelle, sousTitreDetail, geometrieDetail, resumeEnPlace,
  ONGLET_EN_PLACE, ONGLET_LOTS, ONGLET_CARACTERISTIQUES, ONGLET_ROTATION, ONGLET_ENTRETIEN,
} from '../lib/parcelleDansPlan.js'

/**
 * [US-229 / C7, C5 — US-232 / S7] La ligne d'aide : la phrase à dire au compagnon, et un bouton
 * qui la copie. UN seul composant, partagé par « Caractéristiques » et « Sol et entretien ».
 *
 * [CA8] La copie est un confort, jamais une condition : sans presse-papiers, ou
 * s'il refuse, la phrase reste là, sélectionnable, et rien ne s'affiche en
 * erreur.
 */
function LigneAideCompagnon({ phrase, prefixe = 'Ou dites au compagnon :' }) {
  const [copie, setCopie] = useState(false)
  async function copier() {
    try {
      await navigator.clipboard?.writeText(phrase)
      setCopie(true)
      setTimeout(() => setCopie(false), 2000)
    } catch {
      /* [CA8] Presse-papiers indisponible : la phrase reste lisible telle quelle. */
    }
  }
  return (
    <div className="flex items-start gap-2 mt-3.5 text-[12.5px] text-txt2">
      <button
        type="button"
        onClick={copier}
        aria-label={`Copier la phrase : ${phrase}`}
        className="shrink-0 text-txt3 hover:text-txt rounded p-1 -m-1
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        {copie ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
      </button>
      <span className="min-w-0">
        {prefixe}{' '}
        <code className="font-mono text-[12px] bg-card-alt text-txt rounded px-1.5 py-0.5 break-words">
          {phrase}
        </code>
      </span>
    </div>
  )
}

// ── [US-229] Carte « Caractéristiques » ──────────────────────────────────────

/**
 * [C3, C4, C5] Un champ de la grille. Renseigné, il porte sa valeur et, le cas
 * échéant, la précision qui dit qu'elle est **déduite** et non déclarée.
 * Absent, il se rend en **état manquant** : cadre en pointillés, teinte
 * d'alerte douce, « Non renseigné » écrit en toutes lettres — jamais masqué,
 * jamais remplacé par un tiret discret ni par une valeur de repli.
 */
function ChampCaracteristique({ champ, saisie, edition, valeur, onChange, erreur, onCompleter }) {
  // [E1] Le MÊME bloc : même cadre, même ordre, même place. Seul son contenu
  // bascule. Ni fenêtre modale, ni page dédiée, ni déplacement de la carte.
  // [US-331 / CA1] Un champ verrouillé (dimensions, statut) ne passe jamais en saisie.
  const enEdition = edition && saisie && saisie.type !== SAISIE_DEDUITE
  const completable = champ.manquant && !champ.verrouille && saisie && onCompleter && !edition
  return (
    <div
      className={`rounded-[10px] px-3 py-2.5 flex flex-col gap-0.5 min-w-0 border ${
        erreur
          ? 'border-red bg-red-soft'
          : champ.manquant && !enEdition && !champ.verrouille
            ? 'border-dashed border-red bg-red-soft'
            : 'border-border-soft'
      }`}
    >
      <label
        className="text-[12px] text-txt2"
        htmlFor={enEdition ? `carac-${champ.cle}` : undefined}
      >
        {champ.label}
      </label>

      {enEdition ? (
        <ChampSaisie
          saisie={saisie}
          valeur={valeur}
          onChange={onChange}
          invalide={Boolean(erreur)}
        />
      ) : (
        completable ? (
          // [US-331 / CA3] « Non renseigné · Compléter » : un toucher ouvre la saisie sur ce champ.
          <button
            type="button"
            onClick={() => onCompleter(champ.cle)}
            className="min-h-[44px] min-w-0 text-left text-[13.5px] text-red break-words
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
          >
            {champ.valeur} · <span className="font-semibold underline">Compléter</span>
          </button>
        ) : (
          <span
            className={`min-w-0 break-words ${
              champ.manquant ? 'text-[13.5px] text-red' : 'text-[15px] font-semibold text-txt'
            }`}
          >
            {champ.valeur}
            {champ.suffixe && (
              <span className="ml-1 text-[12px] font-normal text-txt3">{champ.suffixe}</span>
            )}
            {champ.note && (
              <span className="ml-1 text-[12px] font-normal text-txt3">· {champ.note}</span>
            )}
          </span>
        )
      )}

      {/* [E5] Le refus vient du domaine et nomme la borne. Il se place SOUS le
          champ fautif — jamais en haut de la carte —, et les autres
          modifications restent à l'écran. */}
      {erreur && (
        <span role="alert" className="text-[12px] text-red font-medium">{erreur}</span>
      )}
      {/* [C5] La largeur absente dit d'où elle serait venue : l'écran ne la
          présente jamais comme une valeur que le jardinier aurait pu déclarer. */}
      {!erreur && champ.aide && !enEdition && !completable && (
        <span className="text-[11.5px] text-txt3">{champ.aide}</span>
      )}
    </div>
  )
}

/**
 * [E2, E3, E11] Le champ lui-même. Trois formes seulement — texte, nombre,
 * liste — plus la case de la largeur, qui n'en est pas une : elle DIT d'où la
 * valeur vient, en teinte secondaire, à la place du champ.
 *
 * [CA5] `min`, `max`, `step` et `maxLength` sont recopiés du descripteur, qui
 * les tient de la maquette : ce sont des repères de frappe. La règle, elle, est
 * au point d'écriture — un navigateur qui les ignore reçoit le même refus que
 * le compagnon.
 */
function ChampSaisie({ saisie, valeur, onChange, invalide }) {
  const commun = {
    id: `carac-${saisie.cle}`,
    value: valeur ?? '',
    onChange: (e) => onChange(e.target.value),
    'aria-invalid': invalide || undefined,
    // [E11] 44 px de cible d'appui, à 375 px comme ailleurs.
    className: `w-full min-h-[44px] rounded-md border px-2 py-1 text-[15px] font-semibold
                text-txt bg-card focus:outline-none focus:ring-2 focus:ring-brand
                ${invalide ? 'border-red' : 'border-border'}`,
  }

  if (saisie.type === SAISIE_DEDUITE) {
    return <span className="text-[13px] text-txt3 py-2">{saisie.texte}</span>
  }
  if (saisie.type === SAISIE_LISTE || saisie.type === SAISIE_OUI_NON) {
    return (
      <select {...commun}>
        {/* [E2, CA6] « Non renseigné » remet la valeur à NULL — ce qui n'est ni
            « Non », ni « Aucun ». Les deux booléens qui ont toujours une valeur
            (pépinière, statut) ne portent pas ce choix. */}
        {saisie.nonRenseignable && (
          <option value={CHOIX_NON_RENSEIGNE}>{LIBELLE_NON_RENSEIGNE}</option>
        )}
        {saisie.options.map((o) => (
          <option key={o.valeur} value={o.valeur}>
            {o.definition ? `${o.libelle} — ${o.definition}` : o.libelle}
          </option>
        ))}
      </select>
    )
  }
  return (
    <input
      {...commun}
      type={saisie.type === SAISIE_NOMBRE ? 'number' : 'text'}
      inputMode={saisie.type === SAISIE_NOMBRE ? 'decimal' : undefined}
      min={saisie.min}
      max={saisie.max}
      step={saisie.step}
      maxLength={saisie.maxLength}
    />
  )
}

/**
 * [C1, C2, C7, C11] Tout ce que l'application sait de la parcelle, d'un coup
 * d'œil — et ce qu'elle n'en sait pas, dit plutôt que masqué. La carte
 * s'intercale entre l'en-tête (D5) et le bloc des rangs.
 *
 * [CA9] Le bouton « Modifier » est rendu **désactivé** tant qu'US-230 n'est pas
 * livrée : cette US ne livre aucun mode édition, aucun champ de saisie, aucun
 * appel d'écriture. Il est hors tabulation et dit pourquoi.
 */
function CarteCaracteristiques({ champs, saisie, aide, parcelle, lectureSeule, onEnregistre }) {
  // [E1] L'édition est un ÉTAT de la carte, pas un second écran.
  const [edition, setEdition] = useState(false)
  // Les valeurs d'origine viennent du MÊME descripteur que les champs rendus :
  // il n'existe pas deux idées de ce que la parcelle vaut aujourd'hui.
  const initiales = useMemo(
    () => Object.fromEntries(
      (saisie ?? []).filter((c) => c.type !== SAISIE_DEDUITE).map((c) => [c.cle, c.valeur]),
    ),
    [saisie],
  )
  const [valeurs, setValeurs] = useState(initiales)
  const [erreurChamp, setErreurChamp] = useState(null)
  const [erreurReseau, setErreurReseau] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [confirmation, setConfirmation] = useState(null)
  // [US-331 / CA3] Le champ sur lequel « Compléter » a ouvert la saisie : il prend le focus.
  const [aCompleter, setACompleter] = useState(null)
  useEffect(() => {
    if (!edition || !aCompleter) return
    document.getElementById(`carac-${aCompleter}`)?.focus?.()
    setACompleter(null)
  }, [edition, aCompleter])

  // Changer de parcelle referme l'édition : on ne reporte jamais la saisie
  // d'une planche sur une autre.
  useEffect(() => {
    setEdition(false)
    setValeurs(initiales)
    setErreurChamp(null)
    setErreurReseau(null)
  }, [parcelle?.id, initiales])

  const modifie = useMemo(
    () => Object.keys(chargeUtile(initiales, valeurs, parcelle)).length > 0,
    [initiales, valeurs, parcelle],
  )
  const avertissements = useMemo(
    () => (edition ? avertissementsBascule(initiales, valeurs) : []),
    [edition, initiales, valeurs],
  )

  // [CA8] Quitter l'onglet en cours d'édition DEMANDE confirmation plutôt que
  // de perdre la saisie silencieusement.
  useEffect(() => {
    if (!edition || !modifie) return undefined
    const garde = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', garde)
    return () => window.removeEventListener('beforeunload', garde)
  }, [edition, modifie])

  function annuler() {
    // [CA8] Aucun appel réseau : les valeurs d'origine sont déjà là.
    setValeurs(initiales)
    setErreurChamp(null)
    setErreurReseau(null)
    setEdition(false)
  }

  async function enregistrer() {
    const charge = chargeUtile(initiales, valeurs, parcelle)
    if (Object.keys(charge).length === 0) { setEdition(false); return }
    setEnCours(true)
    setErreurChamp(null)
    setErreurReseau(null)
    try {
      // [E4] UN seul appel porte tous les champs modifiés. Rien n'est écrit
      // champ par champ à la volée, et un champ non touché n'est pas transmis.
      const maj = await api.modifierParcelle(parcelle.id, charge)
      // [E6, CA9] La carte repasse en lecture, et l'en-tête comme la Vue plan
      // reflètent la nouvelle valeur SANS rechargement complet.
      onEnregistre?.(maj)
      setEdition(false)
      setConfirmation(messageConfirmation(maj.modifications))
      setTimeout(() => setConfirmation(null), 5000)
    } catch (e) {
      // [E5] Refus d'une valeur : le message se pose sous le champ fautif, les
      // autres modifications restent à l'écran, la carte reste en édition.
      if (e.champ) setErreurChamp({ champ: e.champ, message: e.message })
      // [CA13] Échec réseau : la saisie est conservée, l'erreur est affichée,
      // une relance est proposée — et rien n'a été écrit à moitié.
      else setErreurReseau(e.message)
    } finally {
      setEnCours(false)
    }
  }

  /** [E5] Le champ fautif, nommé par le serveur sous son nom d'API. */
  const cleEnErreur = erreurChamp
    ? Object.keys(CHAMP_API).find((c) => CHAMP_API[c] === erreurChamp.champ)
    : null
  const parCle = Object.fromEntries((saisie ?? []).map((s) => [s.cle, s]))

  return (
    <Card>
      {/* [C11] Sous 375 px, le bouton passe sous le titre — il ne disparaît
          jamais : c'est la seule promesse d'édition de l'écran. */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3.5">
        <h2 className="font-serif font-semibold text-[17px] text-txt tracking-tight">
          Caractéristiques
        </h2>
        {/* [E10] Membre en lecture seule : le bouton n'est PAS rendu. Pas
            grisé, pas présent — la carte est celle d'US-229. */}
        {!lectureSeule && (
          edition ? (
            // [E1, E11] « Enregistrer » en teinte primaire, « Annuler » à côté.
            // Sous 375 px les deux restent atteignables sans faire défiler la
            // carte entière.
            <div className="flex gap-2">
              {/* [E11] 44 px de cible d'appui : les deux boutons restent
                  atteignables au pouce, à 375 px comme ailleurs. */}
              <Btn small className="min-h-[44px]" onClick={annuler} disabled={enCours}>
                Annuler
              </Btn>
              <Btn small className="min-h-[44px]" kind="primary" onClick={enregistrer} disabled={enCours}>
                {enCours ? 'Enregistrement…' : 'Enregistrer'}
              </Btn>
            </div>
          ) : (
            <Btn small className="min-h-[44px]" onClick={() => { setEdition(true); setConfirmation(null) }}>
              Modifier
            </Btn>
          )
        )}
      </div>

      {/* [C11, E11] Une colonne à 375 px, autant que la carte en tient au-delà :
          largeur du CONTENEUR, jamais de l'écran. */}
      <div className="grid gap-2.5 grid-cols-1 @[420px]/card:grid-cols-[repeat(auto-fill,minmax(190px,1fr))]">
        {champs.map((champ) => (
          <ChampCaracteristique
            key={champ.cle}
            champ={champ}
            saisie={parCle[champ.cle]}
            edition={edition}
            valeur={valeurs[champ.cle]}
            onCompleter={lectureSeule ? undefined : (cle) => { setEdition(true); setConfirmation(null); setACompleter(cle) }}
            onChange={(v) => {
              setValeurs((p) => ({ ...p, [champ.cle]: v }))
              if (cleEnErreur === champ.cle) setErreurChamp(null)
            }}
            erreur={cleEnErreur === champ.cle ? erreurChamp.message : null}
          />
        ))}
      </div>

      {/* [E8, E9] Ce qu'une bascule entraîne ailleurs, dit AVANT
          l'enregistrement. Une phrase, pas une fenêtre de confirmation. */}
      {avertissements.map((phrase) => (
        <p key={phrase} className="mt-2.5 text-[12.5px] text-amber bg-amber-soft rounded-lg px-2.5 py-2">
          {phrase}
        </p>
      ))}

      {/* [CA13] Échec réseau : la saisie est conservée telle quelle, l'erreur
          est dite, et la relance est à portée — rien n'a été écrit à moitié. */}
      {erreurReseau && (
        <div role="alert" className="mt-2.5 flex flex-wrap items-center gap-2 text-[12.5px] text-red bg-red-soft rounded-lg px-2.5 py-2">
          <span className="min-w-0">{erreurReseau}</span>
          <Btn small onClick={enregistrer} disabled={enCours}>Réessayer</Btn>
        </div>
      )}

      {/* [E6] Un message bref qui dit CE QUI a changé. */}
      {confirmation && !edition && (
        <p role="status" className="mt-2.5 text-[12.5px] text-brand-text bg-brand-soft rounded-lg px-2.5 py-2">
          {confirmation}
        </p>
      )}

      {/* [C7] La phrase à dire au compagnon, bâtie avec le nom RÉEL de la
          parcelle et — quand un seul champ manque — avec ce champ-là. */}
      <LigneAideCompagnon phrase={aide.phrase}
        prefixe="Les dimensions se règlent sur le plan. Ou dites à Gaston :" />
    </Card>
  )
}

// ── [US-231] Carte « Rotation » ──────────────────────────────────────────────

/**
 * [R2, R3, R7, CA7] Une vignette de famille : le nom en gras, les cultures
 * dessous. La teinte identifie la FAMILLE et rien d'autre (R3) — elle vient de
 * `lib/familles.js`, la même d'une parcelle à l'autre et d'une année à l'autre.
 *
 * [CA7] Chaque culture nommée est un appui vers sa fiche culture (US-207). Tant
 * que cette fiche n'existe pas, l'appui mène à l'écran Cultures sur CETTE
 * culture — la sortie dégrade, elle ne disparaît pas. Une vignette qui porte
 * plusieurs cultures les propose donc toutes, une par une : rien n'est choisi
 * à la place du jardinier.
 *
 * [CA8] Lecture seule : ces appuis NAVIGUENT, ils n'écrivent rien. Un membre en
 * lecture seule voit la carte à l'identique.
 */
function VignetteFamille({ vignette, onCulture }) {
  const { teinte } = vignette
  return (
    <div
      className="rounded-[10px] border px-2 py-1.5 flex flex-col gap-0.5 min-w-0"
      style={{ background: teinte.fond, borderColor: teinte.bord }}
    >
      <span
        className={`text-[12.5px] font-semibold leading-tight ${vignette.inconnue ? 'italic' : ''}`}
        style={{ color: teinte.encre }}
      >
        {vignette.famille}
      </span>
      {vignette.cultures.length > 0 && (
        <span className="flex flex-wrap gap-x-1.5 gap-y-0.5">
          {vignette.cultures.map((culture) => (
            <button
              key={culture}
              type="button"
              onClick={() => onCulture(culture)}
              aria-label={`Voir la culture ${culture}`}
              className="text-[11.5px] text-txt2 underline decoration-dotted
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
            >
              {culture}
            </button>
          ))}
        </span>
      )}
      {/* Colonne de conseil : pourquoi cette famille est possible. */}
      {vignette.note && (
        <span className="text-[11px] text-txt3 leading-tight">{vignette.note}</span>
      )}
    </div>
  )
}

/**
 * [R1, R4, R5, R6, R9] La carte « Rotation » — quatre colonnes, l'année en tête,
 * la dernière en pointillés.
 *
 * [R9] À 375 px les quatre colonnes deviennent quatre LIGNES empilées, l'année
 * en tête de ligne : un seul DOM, deux mises en page, par la largeur du
 * CONTENEUR et jamais celle de l'écran. L'alerte reste sous la grille.
 *
 * Aucun calcul ici [CA1] : les colonnes, l'alerte et les mentions viennent de
 * `lib/planParcelles.js`, qui les reçoit de `app/services/rotation.py` — le
 * même service que l'avertissement de plantation (US-163).
 */
function CarteRotation({ rotation, onCulture }) {
  return (
    <Card>
      <h2 className="font-serif font-semibold text-[17px] text-txt tracking-tight mb-3.5">
        Rotation
      </h2>

      {/* [R6] L'absence d'antécédent se DIT — elle ne se lit pas comme
          « aucun conflit » —, et la colonne de conseil reste. */}
      {rotation.mentionAucunAntecedent && (
        <p className="text-[12.5px] text-txt2 bg-card-alt rounded-lg px-2.5 py-2 mb-3">
          {rotation.mentionAucunAntecedent}
        </p>
      )}

      {/* [R1, R9] Quatre colonnes dès que la carte a la largeur de les porter,
          quatre LIGNES empilées à 375 px. Le palier intermédiaire à deux
          colonnes évite qu’un nom de famille se casse en trois lignes quand
          la carte partage sa rangée avec « Sol et entretien ». Largeur du
          CONTENEUR, jamais de l’écran. */}
      <div className="grid gap-2.5 grid-cols-1 @[380px]/card:grid-cols-2 @[520px]/card:grid-cols-4">
        {rotation.colonnes.map((colonne) => (
          <div
            key={colonne.annee}
            className={`rounded-xl p-2 flex flex-col gap-1.5 min-w-0 ${
              colonne.conseil
                ? 'border border-dashed border-border'
                : 'border border-border-soft'
            }`}
          >
            <div className="flex items-baseline gap-1.5 flex-wrap">
              <span className="text-[13px] font-semibold text-txt">{colonne.annee}</span>
              {colonne.libelle && (
                <span className="text-[11.5px] text-txt2">{colonne.libelle}</span>
              )}
            </div>
            {/* [R6] Une année sans donnée reste une colonne — vide, et qui le dit. */}
            {colonne.vide ? (
              <span className="text-[11.5px] text-txt3">
                {colonne.conseil ? 'Aucun conseil' : 'Rien d’enregistré'}
              </span>
            ) : (
              colonne.vignettes.map((vignette) => (
                <VignetteFamille
                  key={`${vignette.famille}-${vignette.familleId ?? 'inconnue'}`}
                  vignette={vignette}
                  onCulture={onCulture}
                />
              ))
            )}
          </div>
        ))}
      </div>

      {/* [R5] L'alerte de répétition, sous la grille, en teinte d'alerte — le
          seul endroit de cette carte où une couleur porte un jugement. */}
      {rotation.alertes.map((alerte) => (
        <p
          key={alerte.famille}
          role="alert"
          className="mt-2.5 text-[12.5px] text-amber bg-amber-soft rounded-lg px-2.5 py-2"
        >
          {alerte.message}
        </p>
      ))}

      {/* [R7] La lacune du référentiel, dite en une ligne — et payée en
          exclusion du calcul, jamais en silence. */}
      {rotation.mentionFamillesInconnues && (
        <p className="mt-2.5 text-[12.5px] text-txt2 bg-card-alt rounded-lg px-2.5 py-2">
          {rotation.mentionFamillesInconnues}
        </p>
      )}
      {/* [R4] Un conseil qui ne se formule pas dit ce qui manque. */}
      {rotation.mentionConseil && (
        <p className="mt-2.5 text-[12.5px] text-txt2 bg-card-alt rounded-lg px-2.5 py-2">
          {rotation.mentionConseil}
        </p>
      )}
    </Card>
  )
}

// ── [US-232] Carte « Sol et entretien » ──────────────────────────────────────

/**
 * [S1 à S8] Ce que le jardinier a apporté au SOL de cette planche, dans l'ordre
 * du temps — paillage, amendement, désherbage, binage.
 *
 * Aucun enregistrement n'est inventé ici : ces gestes existent déjà, ils se
 * noyaient seulement dans un journal trié par date, toutes parcelles
 * confondues. La carte **filtre et regroupe**, et pose l'endroit d'où en
 * ajouter un.
 *
 * [S4] Un semis, une plantation, une récolte n'y figurent pas : ils portent sur
 * une culture, pas sur le sol. Le filtre est fait par le domaine
 * (`evenements.GESTES_SOL`), jamais ici [CA2].
 *
 * [CA7] « Ajouter » **prépare** un geste avec la parcelle en contexte : il
 * n'écrit rien, c'est le compagnon qui relit et confirme (US-224).
 * [CA9] `BoutonGeste` ne rend rien du tout à un membre en lecture seule — la
 * liste, elle, reste entière.
 */
function CarteSol({ sol, parcelleId, parcelleNom, dateRef, onJournal }) {
  return (
    <Card>
      {/* [S1] Titre à gauche, « Ajouter » à droite. */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-serif font-semibold text-[17px] text-txt tracking-tight">
          Sol et entretien
        </h2>
        <BoutonGeste
          geste={{ action: 'paillage', parcelleId, parcelleNom }}
          dateRef={dateRef}
          ecran="plan"
          libelle="Ajouter"
          small
        />
      </div>

      {/* [S6] Aucune intervention : la carte le DIT, et garde sa ligne d'aide.
          Elle n'est jamais masquée — une planche dont on ne sait rien du sol
          n'est pas une planche sans carte. */}
      {sol.vide ? (
        <p className="text-[13.5px] text-txt2">{sol.message}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border-soft">
          {sol.lignes.map((ligne) => (
            /* [S2, S8] Date à gauche, libellé à droite ; à 375 px la date passe
               AU-DESSUS du libellé — largeur du CONTENEUR, jamais de l'écran. */
            <li
              key={ligne.id}
              className="@container/sol flex flex-col gap-0.5 py-2
                         @[22rem]/card:flex-row @[22rem]/card:gap-3 @[22rem]/card:items-baseline"
            >
              <span className="shrink-0 text-[12px] font-semibold text-txt3 tabular-nums @[22rem]/card:w-[5.5rem]">
                {ligne.date}
              </span>
              <span className="text-[13.5px] text-txt min-w-0">{ligne.libelle}</span>
            </li>
          ))}
        </ul>
      )}

      {/* [S5] Au-delà de huit, le Journal prend le relais — filtré sur CETTE
          parcelle et sur CES gestes. */}
      {sol.toutVoir && (
        <button
          type="button"
          onClick={onJournal}
          className="mt-2.5 text-[12.5px] font-semibold underline text-txt2
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
        >
          Tout voir ({sol.total}) →
        </button>
      )}

      {/* [S7] La phrase à dire au compagnon — même composant qu'US-229 / C5. */}
      <LigneAideCompagnon phrase={sol.aide.phrase} />
    </Card>
  )
}

// ── [US-330] Le détail d'une parcelle, en quatre onglets ─────────────────────

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'

/** [D3] Onglet « En place » : l'occupation, une ligne par culture (celle de la liste mobile), les rangs libres. */
function OngletEnPlace({ resume, entree, onCulture }) {
  const lignes = entree?.lignes ?? []
  return (
    <div className="flex flex-col gap-2">
      <p className="text-[14px] font-semibold text-txt">{resume || 'Rien en place.'}</p>
      {lignes.length > 0 ? (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
          {lignes.map((l) => <LigneChemin key={l.cle} ligne={l} onOuvrir={onCulture} />)}
        </ul>
      ) : (
        <p className="text-[12.5px] text-txt3">Rien en place.</p>
      )}
    </div>
  )
}

/** [D3] Pour une pépinière : ses lots, et le chemin vers « Ma pépinière ». */
function OngletLots({ entree, onLot, onPepiniere }) {
  const lots = entree?.lots ?? []
  return (
    <div className="flex flex-col gap-2">
      {lots.length > 0 ? (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
          {lots.map((lot) => (
            <li key={lot.cle}>
              <button type="button" aria-label={lot.nomAccessible} onClick={() => onLot?.(lot)}
                className={`flex w-full min-h-[54px] items-center gap-3 px-3 py-1.5 text-left hover:bg-card-alt ${FOCUS}`}>
                <span className="w-10 shrink-0 text-[12px] font-bold text-txt2">{lot.numero != null ? `#${lot.numero}` : '—'}</span>
                <span aria-hidden="true" className="text-[18px] leading-none">{lot.emoji}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-semibold text-txt">{lot.nom}</span>
                  {lot.detail && <span className="block truncate text-[12px] text-txt2">{lot.detail}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[12.5px] text-txt3">Aucun lot en cours.</p>
      )}
      <Btn kind="primary" small onClick={onPepiniere}>Voir Ma pépinière →</Btn>
    </div>
  )
}

/**
 * [D1 à D6] Le détail d'une parcelle. `onglet` / `onOnglet` sont tenus par l'écran (état exact,
 * US-195 / CA8) ; `entree` est la parcelle telle que le chemin la lit (`parcellesDuChemin`).
 */
function DetailParcelleInterne({
  parcelle, entree, onglet, onOnglet, dateRef, vocabulaires, gestesSol, lectureSeule, ordinateur,
  onFermer, onCulture, onVoirCulture, onLot, onPepiniere, onJournalSol, onNoter, onAjuster, onRetirer, onParcelleMaj, ancre,
}) {
  const { id, nom } = parcelle
  const detail = useMemo(() => detailDeParcelle(parcelle, vocabulaires), [parcelle, vocabulaires])
  const sol = useMemo(() => carteSol(parcelle, { dateRef, gestesSol }), [parcelle, dateRef, gestesSol])
  const obs = useObservations(`parcelle:${id}`, { parcelleId: id })
  const onglets = ongletsDeParcelle(parcelle)
  const actif = ongletValide(parcelle, onglet)
  const geo = geometrieDetail(parcelle)
  const pepiniere = Boolean(parcelle.est_pepiniere)

  return (
    <>
      {/* [US-195 / CA4] Point d'ancrage du focus quand un lien désigne cette parcelle. */}
      <div ref={ancre} tabIndex={-1} className="@container/detail flex flex-col gap-3 outline-none">
        {/* D1 */}
        <header className="flex items-start gap-3">
          <span aria-hidden="true" className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl bg-card-alt text-[22px]">
            {pictoParcelle(parcelle)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-serif text-[19px] font-semibold leading-tight text-txt">{nom}</h3>
              {detail.entete.hasObservations && (
                <ObservationIcon onClick={obs.toggle} active={obs.open} count={detail.entete.nbObservations} />
              )}
            </div>
            <p className="text-[12.5px] text-txt2">{sousTitreDetail(parcelle)}</p>
          </div>
          {onFermer && (
            <button type="button" onClick={onFermer} aria-label="Fermer le détail de la parcelle"
              className={`inline-flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg text-txt2 hover:bg-card-alt ${FOCUS}`}>
              <X size={18} aria-hidden="true" />
            </button>
          )}
        </header>
        {detail.entete.hasObservations && obs.open && <ObservationPanel items={obs.items} loading={obs.loading} />}

        {/* D2 */}
        {!pepiniere && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card-alt px-3 py-2">
            <p className="text-[12.5px] text-txt2">{geo.texte}</p>
            {ordinateur && !lectureSeule && (
              <Btn small disabled={!onAjuster} onClick={onAjuster}>
                Ajuster sur le plan
              </Btn>
            )}
          </div>
        )}

        {/* Onglets */}
        <div role="tablist" aria-label="Détail de la parcelle" className="flex gap-1 overflow-x-auto rounded-[10px] bg-card-alt p-[3px]">
          {onglets.map((o) => (
            <button key={o.id} type="button" role="tab" id={`onglet-parcelle-${o.id}`}
              aria-selected={actif === o.id} aria-controls="panneau-parcelle" tabIndex={actif === o.id ? 0 : -1}
              onClick={() => onOnglet(o.id)}
              className={`min-h-[40px] shrink-0 rounded-lg px-2 text-[12.5px] font-semibold whitespace-nowrap ${FOCUS}
                ${actif === o.id ? 'bg-card text-txt shadow-sm' : 'text-txt2 hover:text-txt'}`}>
              {o.label}
            </button>
          ))}
        </div>

        <div role="tabpanel" id="panneau-parcelle" aria-labelledby={`onglet-parcelle-${actif}`} className="flex flex-col gap-3">
          {actif === ONGLET_EN_PLACE && (
            <OngletEnPlace resume={resumeEnPlace(parcelle, entree?.lignes)} entree={entree} onCulture={onCulture} />
          )}
          {actif === ONGLET_LOTS && <OngletLots entree={entree} onLot={onLot} onPepiniere={onPepiniere} />}
          {actif === ONGLET_CARACTERISTIQUES && (
            <>
              <CarteCaracteristiques
                champs={detail.caracteristiques} saisie={detail.saisie} aide={detail.aideCompagnon}
                parcelle={parcelle} lectureSeule={lectureSeule} onEnregistre={onParcelleMaj}
              />
              {/* [US-332 / R2, CA6] Gaston vérifie les cultures et l'historique ; un lecteur ne voit pas le bouton. */}
              {onRetirer && !lectureSeule && (
                <div className="flex flex-col items-start gap-1">
                  <Btn small onClick={onRetirer}>Rendre inactive ou supprimer…</Btn>
                  <p className="text-[12px] text-txt3">Gaston vérifie d’abord les cultures et l’historique, puis te propose la suite.</p>
                </div>
              )}
            </>
          )}
          {/* D5 — CA3 : la carte d'US-231, sans second dessin. */}
          {actif === ONGLET_ROTATION && detail.rotation && (
            <>
              <CarteRotation rotation={detail.rotation} onCulture={onVoirCulture} />
              <p className="text-[12.5px] text-txt3">Vue détaillée dans la tuile Rotation (à venir).</p>
            </>
          )}
          {/* D6 — CA3 : le journal du sol d'US-232, et « Noter » qui ouvre Gaston sur la parcelle. */}
          {actif === ONGLET_ENTRETIEN && (
            <>
              <CarteSol sol={sol} parcelleId={id} parcelleNom={nom} dateRef={dateRef} onJournal={onJournalSol} />
              {!pepiniere && !lectureSeule && (
                <div><Btn kind="primary" onClick={onNoter}>Noter</Btn></div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}

export default function DetailParcelle(props) {
  return <ObservationsUIProvider><DetailParcelleInterne {...props} /></ObservationsUIProvider>
}

/** [CA4] La liste : toutes les parcelles, posées ou non — l'autre mode de la même sélection. */
export function ListeParcelles({ parcelles, choisie, onChoisir }) {
  if (!parcelles.length) return <p className="text-[13px] text-txt3">Aucune parcelle enregistrée.</p>
  return (
    <ul aria-label="Parcelles" className="flex flex-col gap-1.5">
      {parcelles.map((p) => (
        <li key={p.id}>
          <button type="button" aria-pressed={choisie === p.id} onClick={() => onChoisir(p.id)}
            className={`flex w-full min-h-[54px] items-center gap-3 rounded-xl border px-3 py-2 text-left ${FOCUS}
              ${choisie === p.id ? 'border-brand bg-brand-soft' : 'border-border bg-card hover:bg-card-alt'}`}>
            <span aria-hidden="true" className="text-[20px] leading-none">{p.picto}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-serif text-[14.5px] font-semibold text-txt">{p.nom}</span>
              <span className="block truncate text-[12px] text-txt2">
                {p.sousTitre}{!p.placee && !p.pepiniere ? ' · pas encore sur le plan' : ''}
              </span>
            </span>
            {p.occupation && <span className="shrink-0 text-[12px] text-txt2">{p.occupation}</span>}
          </button>
        </li>
      ))}
    </ul>
  )
}
