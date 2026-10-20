// [US-216] La fiche d'un lot — le poste de terrain.
//
// Un seul composant pour deux formes (maquette figée du 14/10/2026) :
//   * `panneau` — « Lot sélectionné » à côté de la liste, quand le conteneur de
//     l'écran fait au moins 900 px (la décision est prise par l'écran, qui mesure SON
//     conteneur) ;
//   * `modale`  — fenêtre « adaptative » sinon : plein écran sous 480 px (le terrain,
//     375 px), modale centrée au-delà.
//
// Ordre figé : identité, échéance, gestes, traçabilité, où les mettre, détail du lot.
//
// « Le même écran s'ouvre par scan d'étiquette ou depuis la liste des lots. Le scan
// ne fait que remplacer la navigation ; il n'ajoute aucun chemin d'écriture. »
//
// ⚠️ La fiche n'écrit rien. Chaque bouton PRÉPARE un geste pré-rempli que le
// compagnon confirme (`BoutonGeste`, US-196/US-224). La fiche ne saisit AUCUN détail :
// « Noter la levée » dépose le geste avec son seul lot, et le bot demande le nombre de
// levés et si la levée est terminée (US-212). Les règles — quels gestes, quelles
// quantités, quel taux — vivent dans `lib/ficheLot.js`.
import { useState } from 'react'
import {
  AlertTriangle, ArrowLeftRight, Check, ChevronRight, CircleHelp, Clock, Flower2, Leaf,
  MapPin, BookOpen, Sprout, X,
} from 'lucide-react'
import { Badge, Modal } from './ui'
import BoutonGeste from './BoutonGeste.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { peutEnregistrer, plafondGesteDeLot } from '../lib/gestes.js'
import { useFileGestes } from '../context/FileGestesContext.jsx'
import { emplacementLot } from '../lib/pepiniere.js'
import {
  LEVEE_DISPONIBLE, badgeEtat, dateEnClair, echeanceEnClair, gestePrepare,
  gesteMiseEnTerreIci, gestesDuLot, incoherenceEnClair, NB_SUGGESTIONS_VISIBLES, placeEnClair, suggestionsVisibles, joursDepuisSemis, phraseLotSansGeste, phraseSolde,
  tracabilite,
} from '../lib/ficheLot.js'
import {
  bilanLot, datesEtiquette, enteteEtiquette, grandChiffre, indexColonne, ligneFragment, metaBandeau,
} from '../lib/parcours.js'   // [US-218] le bandeau

/** Une icône par geste — celles de la maquette. */
const ICONE = {
  repiquer: Flower2,
  noter_levee: Sprout,
  mettre_en_terre: Leaf,
  declarer_perte: AlertTriangle,
  deplacer: ArrowLeftRight,
  cloturer: Check,
}

// ── Barre du haut ────────────────────────────────────────────────────────────

/**
 * `panneau` : « Lot sélectionné » + badge + croix carrée à droite. `modale` : sous
 * 480 px, la croix à gauche (48 px) et le titre en clair ; au-delà, titre en petites
 * capitales et croix à droite — breakpoints d'ÉCRAN, comme `Modal` : une fenêtre
 * occupe la page, pas un conteneur.
 */
function BarreHaut({ forme, titre, badge, onClose }) {
  const panneau = forme === 'panneau'
  return (
    <div className="flex items-center gap-2.5 border-b border-border shrink-0 min-h-14 pl-1 pr-2 min-[480px]:pl-[18px] min-[480px]:pr-3 py-1">
      {!panneau && (
        <button
          type="button" onClick={onClose} aria-label="Fermer la fiche"
          className="min-[480px]:hidden w-12 h-12 flex items-center justify-center rounded-[12px] text-txt"
        >
          <X size={20} strokeWidth={2} />
        </button>
      )}
      <span
        className={`flex-1 min-w-0 truncate font-bold ${
          panneau
            ? 'text-[11px] uppercase tracking-[.06em] text-txt3 pl-[14px]'
            : 'text-[15px] text-txt min-[480px]:text-[11px] min-[480px]:uppercase min-[480px]:tracking-[.06em] min-[480px]:text-txt3'
        }`}
      >
        {panneau ? 'Lot sélectionné' : titre}
      </span>
      {badge && <Badge tint={badge[1]}>{badge[0]}</Badge>}
      <button
        type="button" onClick={onClose} aria-label="Fermer"
        className={`${panneau ? 'flex' : 'hidden min-[480px]:flex'} w-9 h-9 items-center justify-center rounded-[9px] bg-card-alt text-txt2`}
      >
        <X size={16} />
      </button>
    </div>
  )
}

// ── Identité ─────────────────────────────────────────────────────────────────

/** [CA3] « #128 · Chou » — le nom de la culture ouvre sa fiche culture. */
function Identite({ lot, onOuvrirCulture }) {
  const numero = lot.numero_lot != null ? `#${lot.numero_lot} · ` : ''
  const jours = joursDepuisSemis(lot)
  return (
    <header>
      <div className="flex items-baseline gap-[7px] flex-wrap">
        <span className="font-serif text-[21px] font-semibold text-txt tracking-[-.01em] capitalize">
          {numero}
          {onOuvrirCulture && lot.culture ? (
            <button
              type="button" onClick={() => onOuvrirCulture(lot.culture)} title="Ouvrir la fiche culture"
              className="underline decoration-border underline-offset-4 hover:text-brand text-left"
            >
              {lot.culture}
            </button>
          ) : lot.culture}
        </span>
        <span className="font-serif italic text-[13.5px] text-txt3">{lot.variete || 'variété non précisée'}</span>
      </div>
      <div className="text-[12.5px] text-txt2 mt-1">
        {lot.sans_semis_rattache || !lot.date_semis
          ? 'godets formés sans semis rattaché'
          : `semé le ${dateEnClair(lot.date_semis)}${jours != null ? ` · ${jours} j` : ''}`}
      </div>
      <div className="flex items-center gap-[5px] text-[12.5px] text-txt2 mt-[3px]">
        <MapPin size={14} className="text-txt3 shrink-0" aria-hidden="true" />
        {emplacementLot(lot)}
      </div>
    </header>
  )
}

// ── Échéance (CA4) ───────────────────────────────────────────────────────────

const TON = {
  retard: { fond: 'bg-amber-soft', texte: 'text-amber', Icone: AlertTriangle },
  na: { fond: 'bg-card-alt', texte: 'text-txt3', Icone: CircleHelp },
  info: { fond: 'bg-card-alt', texte: 'text-txt2', Icone: Clock },
}

function Echeance({ lot }) {
  const { titre, detail, ton } = echeanceEnClair(lot)
  if (!titre) return null
  const t = TON[ton] ?? TON.info
  return (
    <div className={`flex gap-2.5 items-start rounded-[12px] px-[13px] py-[11px] ${t.fond}`}>
      <t.Icone size={17} strokeWidth={2.1} className={`${t.texte} shrink-0 mt-px`} aria-hidden="true" />
      <div className="flex-1 min-w-0">
        {/* [RT2] Pas de conseil rédigé : le titre et le détail viennent de l'API. */}
        <div className={`text-[14.5px] font-bold leading-snug ${ton === 'retard' ? 'text-amber dark:text-txt' : 'text-txt'}`}>
          {titre}
        </div>
        {detail && <div className="text-[12.5px] text-txt2 mt-0.5 leading-[1.45]">{detail}</div>}
      </div>
    </div>
  )
}

// ── Le geste, en un appui (CA8, CA9, CA11) ───────────────────────────────────

function Gestes({ lot, dateRef, nbPepinieres, levee }) {
  const gestes = gestesDuLot(lot, { nbPepinieres, levee })
  if (gestes.length === 0) return null

  const principal = gestes.find((g) => g.principal)
  return (
    <section aria-label="Le geste, en un appui">
      <div className="text-[11px] font-bold text-txt3 uppercase tracking-[.06em] mb-2">Le geste, en un appui</div>
      {/* Deux colonnes, le geste suggéré sur toute la largeur : à 375 × 667 ils tiennent sans défilement. */}
      <div className="grid grid-cols-2 gap-2">
        {gestes.map((g) => {
          const p = g.principal
          const libelle = `${g.libelle}${p && g.quantite ? ` · ${g.quantite}` : ''}`
          const Icone = ICONE[g.code] ?? Check
          const taille = p
            ? 'min-h-[52px] text-[15px] font-bold justify-center'
            : 'min-h-[48px] text-[13.5px] font-bold !justify-start text-left'
          return (
            <div key={g.code} className={`flex flex-col gap-1 ${p ? 'col-span-2' : ''}`}>
              {/* [US-212] « Noter la levée » comme tous les gestes : un appui, le lot seul. */}
              <BoutonGeste
                geste={gestePrepare(g)} dateRef={dateRef} ecran="pepiniere"
                libelle={libelle} kind={p ? 'primary' : 'ghost'} icone={Icone}
                plein afficherPhrase={g === principal} btnClassName={taille}
              />
              {/* Une clôture est définitive : elle dit ce qu'elle solde AVANT d'appuyer. */}
              {g.code === 'cloturer' && <p className="text-[11.5px] text-txt3 leading-snug">{phraseSolde(g.solde)}</p>}
            </div>
          )
        })}
      </div>
    </section>
  )
}

// ── Traçabilité (CA5) ────────────────────────────────────────────────────────

function Tracabilite({ lot }) {
  const lignes = tracabilite(lot)
  const incoherence = incoherenceEnClair(lot)
  return (
    <section aria-label="Traçabilité">
      <div className="text-[11px] font-bold text-txt3 uppercase tracking-[.06em] mb-2">Traçabilité</div>
      <dl className="border-t border-border-soft">
        {lignes.map((l) => (
          <div key={l.cle} className="flex items-baseline gap-2.5 py-2 border-b border-border-soft">
            <dt className="flex-1 min-w-0 text-[13px] text-txt2 leading-[1.35]">
              {l.libelle}
              {l.sub && <span className="block text-[11.5px] text-txt3">{l.sub}</span>}
            </dt>
            <dd className="text-[14.5px] font-bold text-txt tabular-nums">
              {/* Un tiret : « aucun geste de ce type » — jamais zéro. */}
              {l.valeur == null
                ? <span className="text-txt3 font-medium" aria-label="aucun">—</span>
                : `${l.valeur}${l.unite ? ` ${l.unite}` : ''}`}
            </dd>
          </div>
        ))}
      </dl>
      {incoherence && (
        <div className="flex gap-2 mt-[9px] text-[12px] text-amber dark:text-txt bg-amber-soft rounded-[10px] px-2.5 py-2 leading-[1.45]">
          <AlertTriangle size={15} strokeWidth={2} className="text-amber shrink-0" aria-hidden="true" />
          {incoherence}
        </div>
      )}
      <div className="text-[11.5px] text-txt3 mt-[7px]">Un tiret : aucun geste de ce type sur le lot.</div>
    </section>
  )
}

// ── Où les mettre (US-217) ───────────────────────────────────────────────────

/**
 * Les parcelles où il reste de la place, d'après la répartition du Plan (US-198,
 * US-227) calculée par le serveur. Lecture pure : rien n'est réservé. Le bouton
 * PRÉPARE la plantation, le compagnon la confirme — la rotation y est vérifiée.
 */
function OuLesMettre({ lot, dateRef, lecture }) {
  const [toutes, setToutes] = useState(false)
  // [INC-014] Combien de plants partent sur CETTE parcelle : vide = tout ce qui reste. Plusieurs
  // parcelles = plusieurs gestes, chacun plafonné par ce que le lot et la file laissent.
  const [nb, setNb] = useState('')
  const { enAttente } = useFileGestes()
  const om = lot.ou_mettre
  if (!om) return null
  const base = gesteMiseEnTerreIci(lot, null)
  const plafond = plafondGesteDeLot(base, enAttente)
  const voulu = nb === '' ? null : Math.max(1, Math.min(Number(nb) || 1, plafond?.disponibles ?? Infinity))
  const gesteIci = (s) => {
    const g = gesteMiseEnTerreIci(lot, s)
    return g && voulu != null ? { ...g, quantite: voulu } : g
  }
  const visibles = suggestionsVisibles(om, toutes)
  const reste = (om.suggestions?.length ?? 0) - NB_SUGGESTIONS_VISIBLES
  return (
    <section aria-label="Où les mettre">
      <div className="text-[11px] font-bold text-txt3 uppercase tracking-[.06em] mb-2">Où les mettre</div>
      {om.aucun_rang_libre && (
        <div className="text-[13px] text-txt2 bg-card-alt rounded-[12px] px-[13px] py-[11px] leading-[1.45] mb-[7px]">
          Aucun rang libre n’est déclaré dans tes parcelles.
          {!lecture && ' Tu peux quand même mettre en terre : le compagnon te demandera la parcelle.'}
        </div>
      )}
      {om.aucun_rang_libre && !lecture && (
        <BoutonGeste
          geste={gesteIci(null)} dateRef={dateRef} ecran="pepiniere"
          libelle="Mettre en terre" kind="ghost" icone={Leaf} plein btnClassName="min-h-[48px] text-[13.5px] font-bold"
        />
      )}
      {!lecture && plafond && !plafond.epuise && (
        <label className="flex items-center gap-2 text-[12.5px] text-txt2 mb-[7px]">
          Plants à mettre en terre
          <input
            type="number" inputMode="numeric" min={1} max={plafond.disponibles} value={nb}
            placeholder={String(plafond.disponibles)} onChange={(e) => setNb(e.target.value)}
            aria-label="Nombre de plants à mettre en terre"
            className="w-20 min-h-[44px] rounded-[10px] border border-border bg-card px-2 text-[14px] text-txt"
          />
          <span className="text-txt3">sur {plafond.disponibles} disponible{plafond.disponibles > 1 ? 's' : ''}</span>
        </label>
      )}
      <ul className="flex flex-col gap-[7px]">
        {visibles.filter((s) => !om.aucun_rang_libre || s.rangs_libres == null).map((s) => (
          <li key={s.parcelle_id} className="border border-border rounded-[12px] px-3 py-2.5 flex flex-col gap-2">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="font-bold text-[13.5px] text-txt">{s.parcelle}</span>
              <span className="text-[12px] text-txt2">{placeEnClair(s, lot.culture)}</span>
            </div>
            {/* [CA2, CA6] L'exposition écrite en mots, jamais une coche seule. */}
            <div className={`text-[12px] leading-[1.45] ${s.exposition?.deconseille ? 'text-red' : s.exposition?.comparaison === 'differe' ? 'text-amber' : 'text-txt3'}`}>
              {s.exposition?.libelle}
            </div>
            {/* [US-239 / CA8] L'ensoleillement non renseigné invite à le déclarer :
                la phrase à dire au compagnon, jamais une valeur supposée. */}
            {s.exposition?.invitation && (
              <div className="text-[12px] leading-[1.45] text-txt3">{s.exposition.invitation}</div>
            )}
            {/* [CA9] Lecture seule : les suggestions, sans bouton. Rangs inconnus : la parcelle
                reste une destination possible (CA3). */}
            {!lecture && (
              <BoutonGeste
                geste={gesteIci(s)} dateRef={dateRef} ecran="pepiniere"
                libelle="Mettre en terre ici" kind="ghost" icone={Leaf} plein afficherPhrase={false}
                btnClassName="min-h-[44px] text-[13px] font-bold"
              />
            )}
          </li>
        ))}
      </ul>
      {!toutes && reste > 0 && (
        <button type="button" onClick={() => setToutes(true)} className="min-h-[44px] mt-1 text-[13px] font-semibold text-brand">
          Voir toutes les parcelles ({reste} de plus)
        </button>
      )}
      {/* [CA4] Dit une fois : aucune estimation de ce qui tiendra. */}
      {om.plants_non_calcules && <div className="text-[11.5px] text-txt3 mt-[7px]">{om.plants_non_calcules}</div>}
    </section>
  )
}

// ── Le contenu, commun aux deux formes ───────────────────────────────────────

function Contenu({ lot, dateRef, nbPepinieres, onOuvrirDetail, onOuvrirCulture, levee, lecture, fragments = [] }) {
  const sansGeste = phraseLotSansGeste(lot)
  return (
    <div className="@container/fiche flex-1 min-h-0 overflow-y-auto px-4 pt-3 pb-6 min-[480px]:px-[18px] min-[480px]:pt-4 flex flex-col gap-3.5">
      <Identite lot={lot} onOuvrirCulture={onOuvrirCulture} />

      {/* [CA19, amendement du 19/10/2026] Un lot coupé dit où se trouve chaque partie. */}
      {fragments.length > 1 && (
        <section aria-label="Où se trouve ce lot" className="rounded-[12px] bg-card-alt px-[13px] py-[10px] flex flex-col gap-1">
          <span className="text-[11.5px] font-bold text-txt3">Ce lot est en {fragments.length} parties</span>
          <ul className="flex flex-col gap-0.5 text-[13px] text-txt">
            {fragments.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </section>
      )}

      {sansGeste ? (
        <div className="text-[13px] text-txt2 bg-card-alt rounded-[12px] px-[13px] py-[11px] leading-[1.45]">
          <strong className="text-txt">{sansGeste.titre}</strong> : {sansGeste.suite.charAt(0).toLowerCase()}{sansGeste.suite.slice(1)}
        </div>
      ) : (
        <Echeance lot={lot} />
      )}

      {/* [CA12] Un membre en lecture seule voit tout, sans geste. */}
      {!lecture && (
        <Gestes lot={lot} dateRef={dateRef} nbPepinieres={nbPepinieres} levee={levee} />
      )}
      {lecture && (
        <div className="text-[12.5px] text-txt3 leading-[1.5]">
          Tu es membre en lecture seule : les gestes sont réservés aux éditeurs du potager.
        </div>
      )}

      <Tracabilite lot={lot} />

      <OuLesMettre lot={lot} dateRef={dateRef} lecture={lecture} />

      {/* [CA7] Le cycle de vie existant du lot (US-061), déplacements compris (US-211). */}
      {onOuvrirDetail && (
        <button
          type="button" onClick={onOuvrirDetail}
          className="min-h-12 flex items-center justify-between gap-2 px-3.5 rounded-[12px] border border-border bg-card text-txt font-semibold text-[13.5px]"
        >
          <span className="flex items-center gap-[9px]"><BookOpen size={17} className="text-txt2" aria-hidden="true" />Détail du lot</span>
          <span className="flex items-center gap-1 text-[12px] text-txt3 font-medium">
            <span className="hidden @[24rem]/fiche:inline">cycle de vie et déplacements</span>
            <ChevronRight size={15} aria-hidden="true" />
          </span>
        </button>
      )}
    </div>
  )
}

/** [CA13] Un numéro inconnu : la fiche s'ouvre quand même, et le dit. */
export function FicheLotInconnu({ numero, onClose }) {
  return (
    <Modal title="Aller au lot" onClose={onClose} disposition="adaptative" width={460} entete={false} bodyClassName="flex flex-col flex-1 min-h-0">
      <BarreHaut forme="modale" titre="Aller au lot" onClose={onClose} />
      <div className="p-4 min-[480px]:p-[18px] flex flex-col gap-3">
        <div className="font-serif text-[19px] font-semibold text-txt">Aucun lot n° {numero} dans ce potager</div>
        <div className="text-[13px] text-txt2 leading-[1.5]">
          Vérifie le numéro écrit sur l’étiquette, ou retrouve le lot dans la liste.
        </div>
        <button
          type="button" onClick={onClose}
          className="min-h-12 rounded-[12px] border border-border bg-card text-txt font-bold text-[14px]"
        >
          Revenir à la liste des lots
        </button>
      </div>
    </Modal>
  )
}

/**
 * @param lot            Un lot tel que `GET /pepiniere/lots[/{numero}]` le rend.
 * @param forme          `panneau` | `modale` — choisie par l'écran selon son conteneur.
 * @param nbPepinieres   Pépinières du potager (`null` si inconnu : « Déplacer » absent).
 * @param dateRef        Date de référence de l'écran, passée au geste.
 * @param onOuvrirDetail Ouvre le cycle de vie du lot (CA7).
 * @param onOuvrirCulture Ouvre la fiche culture (CA3).
 * @param leveeDisponible Le geste de levée est-il livré (US-212) ? Défaut : la constante de
 *                       la lib ; la page de contrôle visuel le force pour montrer « Noter la levée ».
 */
export default function FicheLot({
  lot, forme = 'modale', nbPepinieres = null, dateRef = null, onClose, onOuvrirDetail, onOuvrirCulture,
  leveeDisponible = LEVEE_DISPONIBLE,
  // [CA19] Les parties d'un lot coupé, d'après les étiquettes du parcours (US-240).
  fragments = [],
}) {
  const { potagerActif } = usePotager()
  const lecture = !peutEnregistrer(potagerActif?.role)
  const badge = badgeEtat(lot, { lecture })
  const titre = lot.numero_lot != null ? `Lot n° ${lot.numero_lot}` : 'Godets sans semis rattaché'
  const contenu = (
    <>
      <BarreHaut forme={forme} titre={titre} badge={badge} onClose={onClose} />
      <Contenu
        lot={lot} dateRef={dateRef} nbPepinieres={nbPepinieres} onOuvrirDetail={onOuvrirDetail}
        onOuvrirCulture={onOuvrirCulture} levee={leveeDisponible}
        lecture={lecture} fragments={fragments}
      />
    </>
  )

  if (forme === 'panneau') {
    return (
      <aside
        aria-label={`Lot ${lot.numero_lot ?? ''} ${lot.culture ?? ''}`.trim()}
        className="bg-card border border-border rounded-[14px] shadow-card overflow-hidden flex flex-col min-h-0"
      >
        {contenu}
      </aside>
    )
  }
  return (
    <Modal title={titre} onClose={onClose} disposition="adaptative" width={460} entete={false} bodyClassName="flex flex-col flex-1 min-h-0">
      {contenu}
    </Modal>
  )
}

// ── [US-218, maquette HF option B] La fiche en bandeau sous la rangée ────────

const MOTIF_STADE = { levee: 'sem', godet: 'god', endurcissement: 'end', pret: 'frk' }

/**
 * La fiche du lot ouverte depuis une étiquette du kanban, sur un écran large : un
 * bandeau pleine largeur glissé sous la rangée de la pépinière, découpé sur les
 * colonnes du tableau (maquette « Ma pepiniere - HF », option B retenue). Le kanban
 * reste en place au-dessus et en dessous ; la pointe désigne l'étiquette ouverte.
 *
 * Mêmes règles que la fiche (gestes de `gestesDuLot`, échéance de l'étiquette, rien
 * d'écrit ici) ; seule la mise en page change. Au téléphone, la fiche reste plein écran.
 */
export function FicheLotBandeau({
  lot, etiquette, fragments = [], pepinieres = [], dateRef = null, nbPepinieres = null,
  onClose, onChoisirFragment, onOuvrirDetail, onOuvrirCulture,
}) {
  const { potagerActif } = usePotager()
  const lecture = !peutEnregistrer(potagerActif?.role)
  const meta = metaBandeau(lot, etiquette, pepinieres, dateRef)
  const chiffre = grandChiffre(etiquette, dateRef)
  const tete = enteteEtiquette(etiquette, lot)
  const dates = datesEtiquette(etiquette)
  const gestes = gestesDuLot(lot, { nbPepinieres })
  const principal = gestes.find((g) => g.principal) ?? null
  const autres = gestes.filter((g) => g !== principal)
  const bilan = bilanLot(lot)
  const suggestions = (etiquette?.quantites?.godets ? lot?.ou_mettre?.suggestions ?? [] : []).slice(0, 2)
  const pointe = (indexColonne(etiquette) + 0.5) / 4
  const alerte = ['retard', 'bientot', 'pret'].includes(tete.ton)
  const parties = fragments.length ? fragments : [etiquette]
  return (
    <section
      aria-label={`Lot ${lot.numero_lot ?? ''} ${lot.culture ?? ''}, fiche ouverte`.replace(/\s+/g, ' ')}
      className="relative border-t border-border bg-[linear-gradient(var(--brand-soft),var(--surface)_64px)]"
    >
      {/* La pointe : elle désigne la colonne de l'étiquette ouverte. */}
      <span
        aria-hidden="true"
        className="absolute -top-[9px] w-4 h-4 rotate-45 bg-brand-soft border-l border-t border-border"
        style={{ left: `calc(170px + (100% - 170px) * ${pointe} - 8px)` }}
      />
      <header className="flex items-center gap-2.5 pt-3.5 pb-1 pr-4 pl-[186px]">
        <span className="font-hand text-[25px] font-bold leading-none whitespace-nowrap">
          {lot.numero_lot != null ? `#${lot.numero_lot} · ` : ''}
          {onOuvrirCulture && lot.culture ? (
            <button type="button" onClick={() => onOuvrirCulture(lot.culture)} title="Ouvrir la fiche culture" className="capitalize hover:text-brand">
              {lot.culture}
            </button>
          ) : <span className="capitalize">{lot.culture}</span>}
          {lot.variete && <small className="text-[18px] font-normal text-txt2"> {lot.variete}</small>}
        </span>
        {parties.length > 1 && (
          <span className="inline-flex items-center h-[22px] px-2 rounded-full text-[11px] font-bold bg-sem-s text-sem-d">
            {parties.length} parties
          </span>
        )}
        <button
          type="button" onClick={onClose} aria-label="Fermer la fiche du lot"
          className="ml-auto w-9 h-9 rounded-[10px] bg-card-alt text-txt2 flex items-center justify-center"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </header>

      <div className="grid grid-cols-[170px_repeat(4,minmax(0,1fr))] pt-1.5 pb-[18px]">
        {/* Où est le lot, partie par partie. */}
        <div className="col-start-2 px-3.5 flex flex-col gap-2.5 min-w-0">
          <p className="text-[12px] text-txt2">
            {meta.semis}
            {meta.jour && <> · <span className="font-hand text-[16px] text-txt">{meta.jour}</span></>}
            {' '}· {meta.lieu}
          </p>
          <ul className="flex flex-col gap-1" aria-label="Les parties du lot">
            {parties.map((f) => {
              const l = ligneFragment(f, lot)
              const on = f.id === etiquette.id
              return (
                <li key={f.id}>
                  <button
                    type="button" aria-pressed={on} onClick={() => onChoisirFragment?.(f)}
                    className={`w-full flex items-center gap-2 min-h-[36px] px-2.5 rounded-[10px] text-[12.5px] text-left ${on ? 'bg-brand-soft shadow-[inset_0_0_0_1.5px_var(--brand)]' : 'bg-card-alt'}`}
                  >
                    <i aria-hidden="true" className={`w-3.5 h-3.5 rounded-[4px] shrink-0 motif-${MOTIF_STADE[l.stade]}`} />
                    <b className="font-hand text-[20px] leading-none">{l.nombre}</b>
                    <span className="min-w-0">{l.texte}</span>
                    {l.rang && <span className="ml-auto font-hand text-[15px] text-txt3">{l.rang}</span>}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>

        {/* L'échéance de la partie ouverte, et où mettre ses godets. */}
        <div className="px-3.5 border-l border-border-soft flex flex-col gap-2.5 min-w-0">
          <div className={`flex items-center gap-3 px-3 py-2.5 rounded-[12px] ${alerte ? 'bg-amber-soft' : 'bg-card-alt'}`}>
            {chiffre && (
              <span className={`font-hand text-[32px] font-bold leading-none whitespace-nowrap ${tete.ton === 'retard' ? 'text-red' : alerte ? 'text-amber' : 'text-txt2'}`}>
                {chiffre.avant && <small className="text-[16px] font-normal mr-0.5">{chiffre.avant}</small>}
                {chiffre.texte}
                {chiffre.apres && <small className="text-[16px] font-normal">{chiffre.apres}</small>}
              </span>
            )}
            <p className="text-[12px] text-txt2 min-w-0">
              <b className="block text-[13px] text-txt">{tete.libelle}</b>
              {dates}
            </p>
          </div>
          {suggestions.length > 0 && (
            <div className="rounded-[10px] bg-card-alt px-2.5 py-[7px] flex flex-col gap-0.5 text-[11.5px] text-txt2">
              <span className="text-[10.5px] font-bold text-txt3">Où les mettre</span>
              {suggestions.map((s) => (
                <div key={s.parcelle_id}>
                  <b className="text-txt">{s.parcelle}</b> · {placeEnClair(s, null)}{s.exposition?.parcelle ? ` · ${s.exposition.parcelle}` : ''}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Le geste : le suggéré en grand, les autres en tuiles. */}
        <div className="px-3.5 border-l border-border-soft flex flex-col gap-2.5 min-w-0">
          <span className="text-[10.5px] font-bold text-txt3">Le geste</span>
          {lecture ? (
            <p className="text-[12px] text-txt3">Membre en lecture seule : les gestes sont réservés aux éditeurs du potager.</p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {principal && (
                <BoutonGeste
                  geste={gestePrepare(principal)} dateRef={dateRef} ecran="pepiniere"
                  libelle={`${principal.libelle}${principal.quantite ? ` · ${principal.quantite}` : ''}`}
                  kind="primary" icone={ICONE[principal.code] ?? Check} plein afficherPhrase={false}
                  btnClassName="!min-h-[42px] text-[13px]"
                />
              )}
              {autres.length > 0 && (
                <div className="grid grid-cols-2 @[90rem]/parcours:grid-cols-4 gap-1.5">
                  {autres.map((g) => (
                    <BoutonGeste
                      key={g.code} geste={gestePrepare(g)} dateRef={dateRef} ecran="pepiniere"
                      libelle={g.code === 'declarer_perte' ? 'Perte' : g.libelle}
                      ariaLabel={`${g.libelle} le lot ${lot.numero_lot ?? ''}`.trim()}
                      kind="ghost" icone={ICONE[g.code] ?? Check} plein afficherPhrase={false}
                      btnClassName="!min-h-[54px] !flex-col !gap-1 !whitespace-normal !px-1 text-[11px] text-center leading-tight"
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Le bilan du lot et son journal complet. */}
        <div className="px-3.5 border-l border-border-soft flex flex-col gap-2.5 min-w-0">
          <span className="text-[10.5px] font-bold text-txt3">Bilan</span>
          <div
            className="flex h-2.5 rounded-[5px] overflow-hidden bg-card-alt" role="img"
            aria-label={`${bilan.barre.godet} % en godet ou en terre, ${bilan.barre.levee} % encore en levée`}
          >
            <i className="block h-full bg-god" style={{ width: `${bilan.barre.godet}%` }} />
            <i className="block h-full motif-sem" style={{ width: `${bilan.barre.levee}%` }} />
          </div>
          <p className="flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-txt2 items-baseline">
            {bilan.nombres.map((n) => (
              <span key={n.cle}><b className="font-hand text-[20px] text-txt mr-[3px]">{n.valeur ?? '—'}</b>{n.libelle}</span>
            ))}
          </p>
          {onOuvrirDetail && (
            <button
              type="button" onClick={onOuvrirDetail}
              className="flex items-center justify-between min-h-[42px] px-3 rounded-[12px] border border-border text-[12.5px] text-txt hover:border-brand"
            >
              <span className="flex items-center gap-2"><BookOpen size={16} aria-hidden="true" />Journal complet du lot</span>
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </section>
  )
}
