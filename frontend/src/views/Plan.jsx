// [US-060, US-222, US-232] Onglet **Parcelles** — le niveau 2 du zoom d'information.
//
// US-060 avait posé le maître-détail : la liste des parcelles à gauche, la fiche
// de celle qui est sélectionnée à droite. US-222 l'avait recousu sur la Vue plan
// en y dessinant les rangs — et l'**amendement du 24/09/2026** défait ce dernier
// point : dessiner les rangs aux deux niveaux, c'étaient deux dessins du même
// objet qu'il fallait ensuite garantir identiques.
//
// **Le rang vit dans le Plan, la parcelle vit dans sa fiche.** Ce que la fiche
// porte désormais est ce que le Plan ne peut pas porter :
//
//   * un **bandeau d'occupation** (D5b) — N rangs occupés sur M, les cases, les
//     NOMS des cultures — et « Voir les cultures dans le Plan → » ;
//   * la carte « Caractéristiques » (US-229, US-230) ;
//   * la carte « Sol et entretien » (US-232) — le journal du sol de la planche.
//
// Ce qui a QUITTÉ cet écran, et le dit : les tuiles de culture, leurs numéros de
// rang, leur piste, leur frise des douze mois, leur pastille de confiance et le
// rang libre actionnable (D7 à D10, CA6, CA7, CA9). Ils vivent dans la Vue plan
// (US-200, US-228) et dans la fiche culture (US-206, US-207).
//
// Conséquence directe : cet écran ne fait plus qu'UNE lecture — `GET /plan`.
// Le calendrier cultural (US-176) et la confiance (US-180) ne lui servaient que
// pour les tuiles.
//
// Tout se calcule dans `lib/planParcelles.js` (CA15). Aucune lecture ici (CA1).
import { useState, useEffect, useMemo, useRef } from 'react'
import { RelectureAuRetourProvider } from '../hooks/useRelectureAuRetour.jsx'
import { MapPin, Leaf, Copy, Check } from 'lucide-react'
import { api } from '../lib/api.js'
import { formatUnite, filtrerParcelles, parcelleSelectionnee } from '../lib/plan.js'
import {
  detailDeParcelle, ligneListeParcelle, TIRET_OCCUPATION, TITRE_A_COMPLETER,
  // [US-232] La carte « Sol et entretien » : ce que le jardinier a apporté au
  // sol de cette planche, dans l'ordre du temps.
  carteSol,
  // [US-230] La même carte, en édition : descripteurs de saisie, corps de
  // l'unique appel d'enregistrement, avertissements de bascule.
  chargeUtile, avertissementsBascule, messageConfirmation, CHAMP_API,
  CHOIX_NON_RENSEIGNE, LIBELLE_NON_RENSEIGNE,
  SAISIE_DEDUITE, SAISIE_LISTE, SAISIE_NOMBRE, SAISIE_OUI_NON,
} from '../lib/planParcelles.js'
import { peutEnregistrer } from '../lib/gestes.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useNavigation, useIntention, useEtatEcran } from '../context/NavigationContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import MetricStrip from '../components/MetricStrip.jsx'
import BoutonGeste from '../components/BoutonGeste.jsx'
import { ObservationIcon, ObservationPanel } from '../components/Observations.jsx'
import { useObservations } from '../hooks/useObservations.js'
import { ObservationsUIProvider } from '../context/ObservationsUIContext.jsx'
import { Card, SectionLabel, Btn } from '../components/ui'

// ── Ligne de la liste des parcelles ──────────────────────────────────────────

/**
 * [D1, D2] Une ligne de l'**index** — et rien d'autre. Aucune parcelle n'y est
 * dessinée : la liste de gauche n'est pas une seconde Vue plan (règle 20 de la
 * v4). Nom, ce que la parcelle est, et son occupation **en rangs** à droite, à
 * la place du pourcentage d'US-060 / CA2.
 *
 * [D12] Sous 900 px de conteneur, la même ligne se replie en **pastille** d'un
 * sélecteur horizontal : c'est le sous-titre qui disparaît, pas la ligne — un
 * seul DOM, deux mises en page, aucun écran de retour.
 */
function ParcelleRow({ parcelle, selected, onSelect }) {
  const ligne = ligneListeParcelle(parcelle)

  return (
    <button
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${ligne.nom}, ${ligne.sousTitre}${
        ligne.occupation === TIRET_OCCUPATION ? '' : `, ${ligne.occupation} rangs occupés`
      }${ligne.mention ? `, ${ligne.mention}` : ''}${
        ligne.aCompleter ? `, ${TITRE_A_COMPLETER}` : ''
      }`}
      className={`text-left flex items-center gap-[11px] rounded-xl border transition-colors
                  shrink-0 snap-start px-3 py-2 min-h-[44px]
                  @[900px]/plan:w-full @[900px]/plan:py-[11px] ${
        selected ? 'bg-brand-soft border-brand' : 'bg-card border-border shadow-card'
      }`}
    >
      <div
        className={`w-[34px] h-[34px] rounded-[10px] hidden @[900px]/plan:flex items-center justify-center shrink-0 ${
          selected ? 'bg-card' : 'bg-card-alt'
        }`}
      >
        {/* [D2] L'épingle ne porte plus la couleur d'un taux : elle est neutre. */}
        <MapPin size={17} className="text-txt3" aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0" aria-hidden="true">
        <div className="font-serif text-[14.5px] font-semibold text-txt truncate whitespace-nowrap">
          {ligne.nom}
        </div>
        {/* [D1, D3, D4] « 3 cultures · 12 m² », « libre · 12 m² », « pépinière
            chaude · 3 lots » — replié en pastille, le nom suffit. */}
        <div className="hidden @[900px]/plan:block text-[11.5px] text-txt3 mt-px truncate">
          {ligne.sousTitre}
          {ligne.mention && <span className="italic"> · {ligne.mention}</span>}
        </div>
      </div>
      {/* [D1, D2, D11] L'occupation en rangs — « 4/5 », « — ». Teinte d'alerte
          au seul dépassement, jamais un code couleur de remplissage. */}
      <span
        aria-hidden="true"
        className={`text-[12.5px] font-bold tabular-nums shrink-0 ${
          ligne.depassement > 0 ? 'text-amber' : 'text-txt2'
        }`}
      >
        {ligne.occupation}
      </span>
      {/* [US-229 / C8] Un point discret — jamais une couleur d'état, jamais une
          raison esthétique : il dit qu'une caractéristique de la fiche reste à
          renseigner, et rien d'autre. */}
      {ligne.aCompleter && (
        <span
          role="img"
          aria-label={TITRE_A_COMPLETER}
          title={TITRE_A_COMPLETER}
          className="w-2 h-2 rounded-full bg-red shrink-0"
        />
      )}
    </button>
  )
}

// ── [US-222, amendement du 24/09/2026] Ce qui a quitté cet écran ─────────────
//
// `CultureTile` et `RangLibre` sont **retirés**. La maquette `Parcelle - Fiche`
// retire les tuiles du niveau 2 : dessiner les rangs aux deux niveaux, c'était
// deux dessins du même objet qu'il fallait ensuite garantir identiques. Le rang
// vit désormais dans le Plan (US-200, US-228), la culture dans sa fiche.
//
// ⚠️ Régression assumée, à dire dans `PATCH_NOTES.md` : la frise des douze mois,
// la pastille de confiance et l'ouverture de la fiche calendrier depuis une
// tuile ne sont plus atteignables depuis CET écran tant qu'US-206 et US-207 ne
// sont pas livrées. Elles restent atteignables depuis la Vue plan et le
// Dashboard, qui les rendent toujours.

/**
 * [US-229 / C7, C5 — US-232 / S7] La ligne d'aide : la phrase à dire au
 * compagnon, et un bouton qui la copie. UN seul composant, partagé par la carte
 * « Caractéristiques » et par la carte « Sol et entretien » — deux copies de ce
 * bloc, ce seraient deux comportements de copie à maintenir.
 *
 * [CA8] La copie est un confort, jamais une condition : sans presse-papiers, ou
 * s'il refuse, la phrase reste là, sélectionnable, et rien ne s'affiche en
 * erreur.
 */
function LigneAideCompagnon({ phrase }) {
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
        Ou dites au compagnon :{' '}
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
function ChampCaracteristique({ champ, saisie, edition, valeur, onChange, erreur }) {
  // [E1] Le MÊME bloc : même cadre, même ordre, même place. Seul son contenu
  // bascule. Ni fenêtre modale, ni page dédiée, ni déplacement de la carte.
  const enEdition = edition && saisie
  return (
    <div
      className={`rounded-[10px] px-3 py-2.5 flex flex-col gap-0.5 min-w-0 border ${
        erreur
          ? 'border-red bg-red-soft'
          : champ.manquant && !enEdition
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
        <span
          className={`min-w-0 break-words ${
            champ.manquant ? 'text-[13.5px] text-red' : 'text-[15px] font-semibold text-txt'
          }`}
        >
          {champ.valeur}
          {champ.suffixe && (
            <span className="ml-1 text-[12px] font-normal text-txt3">{champ.suffixe}</span>
          )}
        </span>
      )}

      {/* [E5] Le refus vient du domaine et nomme la borne. Il se place SOUS le
          champ fautif — jamais en haut de la carte —, et les autres
          modifications restent à l'écran. */}
      {erreur && (
        <span role="alert" className="text-[12px] text-red font-medium">{erreur}</span>
      )}
      {/* [C5] La largeur absente dit d'où elle serait venue : l'écran ne la
          présente jamais comme une valeur que le jardinier aurait pu déclarer. */}
      {!erreur && champ.aide && !enEdition && (
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
          <option key={o.valeur} value={o.valeur}>{o.libelle}</option>
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
      <LigneAideCompagnon phrase={aide.phrase} />
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

// ── Panneau de détail de la parcelle sélectionnée ────────────────────────────

function DetailParcelle({ parcelle, dateRef, ancre, vocabulaires, gestesSol, lectureSeule, onVuePlan, onPepiniere, onJournalSol, onCulture, onParcelleMaj }) {
  const { id, nom } = parcelle
  // [US-230 / CA3] Les listes fermées viennent du serveur : l'écran les rend,
  // il ne les écrit pas.
  const detail = useMemo(
    () => detailDeParcelle(parcelle, vocabulaires),
    [parcelle, vocabulaires],
  )
  const { entete, bandeau, caracteristiques, aideCompagnon, saisie, rotation } = detail
  // [US-232 / CA3] La carte du sol se compose de ce que `GET /plan` a déjà
  // servi : changer de parcelle ne déclenche aucune lecture de plus.
  const sol = useMemo(
    () => carteSol(parcelle, { dateRef, gestesSol }),
    [parcelle, dateRef, gestesSol],
  )
  const obs = useObservations(`parcelle:${id}`, { parcelleId: id })

  return (
    // [US-195 / CA4] Point d'ancrage du focus : une intention qui désigne cette
    // parcelle amène le clavier ICI, pas en haut de page.
    <div ref={ancre} tabIndex={-1} className="@container/detail flex flex-col gap-4 outline-none">
      <Card>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-serif text-[24px] font-semibold text-brand-text tracking-tight">{nom}</span>
          {/* [US-039 / CA15] Observations de la parcelle. */}
          {entete.hasObservations && (
            <ObservationIcon onClick={obs.toggle} active={obs.open} count={entete.nbObservations} />
          )}
          {/* [CA8] La remontée d'un niveau : la Vue plan, sur CETTE parcelle. */}
          <button
            type="button"
            onClick={onVuePlan}
            className="ml-auto text-[13px] font-semibold underline text-txt2 whitespace-nowrap
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
          >
            ← Voir dans la Vue plan
          </button>
        </div>

        {/* [D5 amendé] Une LIGNE d'état, en teinte secondaire. Les pastilles de
            superficie, dimensions, exposition, abri et paillage sont retirées :
            elles répétaient ce que la carte « Caractéristiques » dit juste en
            dessous, en mieux (US-229 / C2, C3). */}
        <p className="mt-1.5 text-[13px] text-txt2">{entete.etat}</p>

        {/* [D3, CA10] Le détail d'une pépinière porte ses lots et le lien vers
            la Pépinière, pas des rangs de semis. */}
        {entete.pepiniere && (
          <button
            type="button"
            onClick={onPepiniere}
            className="mt-2.5 text-[13px] font-semibold underline text-txt2
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded"
          >
            Voir la Pépinière →
          </button>
        )}

        {entete.hasObservations && obs.open && <ObservationPanel items={obs.items} loading={obs.loading} />}
      </Card>

      {/* [D5b] Le bandeau d'occupation — tout ce qui reste des cultures dans
          cette fiche : combien de rangs sont occupés, lesquels, par quelles
          cultures, et le chemin vers le Plan. Ni quantité, ni variété, ni
          frise, ni confiance : elles se lisent au niveau 1 et au niveau 3. */}
      {!bandeau.pepiniere && (
        <Card>
          {bandeau.occupation && (
            <p className={`text-[14px] font-semibold ${bandeau.depassement > 0 ? 'text-amber' : 'text-txt'}`}>
              {bandeau.occupation}
            </p>
          )}
          {/* [D4] Une parcelle dont le nombre de rangs n'a jamais été dit porte
              sa mention ici — elle ne propose pas de cases inventées. */}
          {bandeau.mention && (
            <p className="mt-1.5 text-[12.5px] text-txt2">{bandeau.mention}.</p>
          )}
          {bandeau.cases.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2.5" aria-hidden="true">
              {bandeau.cases.map((c) => (
                <span
                  key={c.numero}
                  title={`Rang ${c.numero}${c.libre ? ' — libre' : ''}`}
                  className={`h-2.5 w-7 rounded-full ${c.libre ? 'bg-card-alt border border-border-soft' : 'bg-brand'}`}
                />
              ))}
            </div>
          )}
          {/* [CA6 amendé] Le bandeau garde le NOM des cultures présentes, et
              rien de plus. */}
          {bandeau.libre ? (
            <p className="mt-2.5 text-[13.5px] text-txt2">
              Cette parcelle est libre : aucune culture n’y est en place.
            </p>
          ) : (
            <p className="mt-2.5 text-[13.5px] text-txt2">{bandeau.cultures.join(' · ')}</p>
          )}
          {/* [D5b, CA7 amendé] Le seul chemin vers une culture depuis cette
              fiche : le Plan. */}
          <Btn className="mt-3" kind="primary" small onClick={onVuePlan}>
            Voir les cultures dans le Plan →
          </Btn>
        </Card>
      )}

      {/* [US-229 / C1] Tout ce que l'application sait de la parcelle — et ce
          qu'elle n'en sait pas —, entre le bandeau et la colonne de fin. */}
      <CarteCaracteristiques
        champs={caracteristiques}
        saisie={saisie}
        aide={aideCompagnon}
        parcelle={parcelle}
        lectureSeule={lectureSeule}
        onEnregistre={onParcelleMaj}
      />

      {/* [US-231, US-232 / S1, amendement] La colonne de deux cartes que la
          maquette pose en fin de fiche : « Rotation » d'abord — juste après
          « Caractéristiques » —, « Sol et entretien » en regard. Elles empilent
          sous 768 px. [R8] La pépinière n'a pas de rotation : la carte n'est
          pas rendue, et la colonne n'en porte alors qu'une. */}
      <div className="grid gap-4 @[768px]/detail:grid-cols-2">
        {rotation && <CarteRotation rotation={rotation} onCulture={onCulture} />}
        <CarteSol
          sol={sol}
          parcelleId={id}
          parcelleNom={nom}
          dateRef={dateRef}
          onJournal={onJournalSol}
        />
      </div>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Plan({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId, potagerActif } = usePotager()
  const { annoncer, signaler, aller } = useNavigation()
  // [US-230 / E10] L'écran cache, le serveur interdit — jamais l'un sans
  // l'autre : `require_role` refuse de son côté (CA1).
  const lectureSeule = !peutEnregistrer(potagerActif?.role)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // [US-195 / CA9, CA11] Recherche et sélection font l'état EXACT de cet écran :
  // ils sont tenus par la coquille, qui les rend tels quels au retour — fiche
  // culture fermée, aller-retour vers la Vue plan, changement de sous-onglet.
  // En mémoire de session seulement — rien n'est persisté.
  const intention = useIntention('plan', (recue) => {
    if (recue.parcelle) setEtat({ parcelle: recue.parcelle })
  })
  const [etat, setEtat] = useEtatEcran('plan', { search: '', parcelle: null }, intention)
  const { search, parcelle: selId } = etat
  const setSearch = (v) => setEtat({ search: v })
  const setSelId = (id) => setEtat({ parcelle: id })
  const ficheRef = useRef(null)

  async function load({ silencieux = false } = {}) {
    // [US-230 / CA9] Une relecture APRÈS enregistrement est silencieuse :
    // l'écran a déjà la nouvelle valeur, il attend seulement que le serveur
    // recalcule ce qui s'en déduit (rangs, places, dépassement). Un squelette
    // ici ferait clignoter la fiche pour rien.
    if (!silencieux) setLoading(true)
    setError(null)
    try {
      // [CA1] La MÊME lecture que la Vue plan, enrichie par US-198 — rien de
      // plus. Changer de parcelle ne déclenche aucune requête (RT6).
      // [US-222, amendement] Une SEULE lecture, désormais : la fiche n'ayant
      // plus de tuiles, elle n'a plus besoin du calendrier cultural (US-176)
      // ni de la confiance (US-180). Les deux appels qui les servaient sont
      // retirés — la frise et les étoiles se lisent dans la Vue plan et dans
      // la fiche culture, qui les chargent pour leur compte.
      const plan = await api.plan(dateRef, potagerId)
      setData(plan)
    } catch (e) {
      // [CA13] Une relecture silencieuse qui échoue ne casse pas l'écran :
      // la valeur enregistrée y est déjà, et le serveur l'a bien écrite.
      if (!silencieux) setError(e.message)
    } finally {
      if (!silencieux) setLoading(false)
    }
  }

  useEffect(() => { load() }, [refresh, dateRef, potagerId])

  /**
   * [US-230 / CA9] La nouvelle valeur est posée dans l'état DÉJÀ chargé : la
   * fiche et la Vue plan la reflètent sans rechargement complet. Ce qui s'en
   * DÉDUIT (rangs occupés, places, dépassement) reste du ressort du serveur —
   * une relecture silencieuse suit, l'écran ne le recalcule pas de son côté.
   */
  function majParcelle(maj) {
    setData((d) => (d ? {
      ...d,
      parcelles: d.parcelles.map((p) => (p.id === maj.id ? {
        ...p, ...maj,
        // `rangs_declares` EST `nb_rangs` : une recopie, pas un calcul.
        disposition: { ...p.disposition, rangs_declares: maj.nb_rangs },
      } : p)),
    } : d))
    load({ silencieux: true })
  }

  const parcelles = data?.parcelles ?? []

  // [CA16 d'US-060] Filtre culture, conservé d'US-031 (cf. `lib/plan.js`).
  const filtered = useMemo(() => filtrerParcelles(parcelles, search), [parcelles, search])

  // [CA1/CA16 d'US-060] Une seule parcelle sélectionnée ; la première de la
  // liste à l'ouverture, et la première encore listée quand le filtre exclut
  // celle qui l'était.
  const selection = parcelleSelectionnee(filtered, selId)

  // [US-195 / CA3] Une intention qui désigne une parcelle supprimée ou absente
  // du potager : l'écran s'ouvre normalement sur la première de la liste, et on
  // le DIT — jamais une erreur ni un écran vide.
  useEffect(() => {
    if (!intention?.parcelle || loading || parcelles.length === 0) return
    if (parcelles.some((p) => p.id === intention.parcelle)) {
      annoncer(`Parcelle ${selection?.nom ?? ''} sélectionnée.`)
      ficheRef.current?.focus?.()
    } else {
      signaler("Cette parcelle n'existe plus.")
    }
  }, [loading, parcelles, intention])

  const nbActives = filtered.filter((p) => p.cultures.length > 0).length
  const nbCultures = filtered.reduce((s, p) => s + p.cultures.length, 0)

  // [CA14] Chargement et échec sont ceux de la Vue plan, pas des variantes.
  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={load} />

  return (
    // [US-196 / CA12] Un geste lancé depuis une tuile relit le plan UNE FOIS au
    // retour sur l'onglet — jamais d'interrogation périodique.
    <RelectureAuRetourProvider relire={load}>
    <ObservationsUIProvider>
      <div className="flex flex-col gap-3.5">
        {/* [CA16 d'US-060] Sélecteur de date de référence + filtre culture. */}
        <div className="flex items-center gap-2">
          <DateRefPicker />
          <CultureFilter value={search} onChange={setSearch} className="relative flex-1 min-w-0" />
        </div>

        {filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-3 mt-12 text-txt3">
            <Leaf size={36} />
            <p className="text-base">
              {search ? 'Aucune culture correspondante.' : 'Aucune parcelle enregistrée.'}
            </p>
          </div>
        ) : (
          <>
            {/* [CA6] Bandeau de métriques conservé. */}
            <MetricStrip
              metrics={[
                { value: nbActives, label: 'parcelles actives', tone: 'brand' },
                { value: nbCultures, label: 'cultures en place', tone: 'txt' },
              ]}
            />

            {/* [D12] Bascule pilotée par la largeur du **conteneur** : sous
                900 px, l'index se replie en sélecteur horizontal de pastilles
                et le détail reste dessous, visible sans écran de retour ;
                au-delà, liste calée à 290 px et détail fluide. */}
            <div className="@container/plan">
              <div className="grid gap-4 items-start @[900px]/plan:grid-cols-[290px_1fr]">
                <aside className="min-w-0">
                  <SectionLabel>Mes parcelles · {filtered.length}</SectionLabel>
                  <div
                    role="group"
                    aria-label="Choisir une parcelle"
                    className="flex gap-[7px] overflow-x-auto snap-x pb-1 -mx-1 px-1
                               @[900px]/plan:flex-col @[900px]/plan:overflow-visible @[900px]/plan:mx-0 @[900px]/plan:px-0"
                  >
                    {filtered.map((p) => (
                      <ParcelleRow
                        key={p.id}
                        parcelle={p}
                        selected={selection?.id === p.id}
                        onSelect={() => setSelId(p.id)}
                      />
                    ))}
                  </div>
                </aside>

                {selection && (
                  // La sélection remonte le composant à neuf : les panneaux
                  // d'observations d'une parcelle ne survivent pas au passage à
                  // la suivante.
                  <DetailParcelle
                    key={selection.id}
                    ancre={ficheRef}
                    parcelle={selection}
                    dateRef={data?.date_ref_effective}
                    // [US-230 / CA3] Les listes fermées de la fiche viennent du
                    // domaine, servies par `GET /plan` — aucune lecture de plus.
                    vocabulaires={data?.vocabulaires}
                    // [US-232 / CA2] La liste des gestes de sol vient du
                    // DOMAINE, servie par `GET /plan`. L'écran la transporte
                    // jusqu'au Journal, il ne la recopie jamais.
                    gestesSol={data?.gestes_sol}
                    lectureSeule={lectureSeule}
                    onParcelleMaj={majParcelle}
                    // [CA8] Le sous-onglet Vue plan, avec CETTE parcelle à
                    // l'écran (intention `plan-vue` + `parcelle`, US-195 / CA2).
                    onVuePlan={() => aller('plan-vue', { parcelle: selection.id })}
                    // [CA10] La Pépinière sur cet emplacement. L'onglet
                    // « Emplacements » n'est choisi que si le potager compte
                    // plusieurs pépinières (US-201 / I5) — « Aujourd'hui » sinon.
                    onPepiniere={() => aller('pepiniere', {
                      onglet: parcelles.filter((p) => p.est_pepiniere).length > 1 ? 'emplacements' : 'aujourdhui',
                      emplacement: selection.nom,
                    })}
                    // [US-232 / CA8] « Tout voir » : le Journal, filtré sur
                    // CETTE parcelle et sur CES gestes — ceux que le serveur a
                    // servis, jamais une liste recopiée ici.
                    // [US-231 / CA7] La sortie d'une vignette de famille : la
                    // fiche culture d'US-207, non livrée à ce jour — l'appui
                    // mène donc à l'écran Cultures sur CETTE culture. La sortie
                    // dégrade, elle ne disparaît pas.
                    onCulture={(culture) => aller('cultures', { culture })}
                    onJournalSol={() => aller('journal', {
                      parcelle: selection.nom,
                      gestes: (data?.gestes_sol ?? []).join(','),
                    })}
                  />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </ObservationsUIProvider>
    </RelectureAuRetourProvider>
  )
}
