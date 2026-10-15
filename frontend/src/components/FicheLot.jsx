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
// compagnon confirme (`BoutonGeste`, US-196/US-224) ; le compteur de levée est une
// aide à la saisie, pas un formulaire. Les règles — quels gestes, quelles
// quantités, quel taux — vivent dans `lib/ficheLot.js`.
import { useState } from 'react'
import {
  AlertTriangle, ArrowLeftRight, Check, ChevronRight, CircleHelp, Clock, Flower2, Leaf,
  MapPin, BookOpen, Sprout, X,
} from 'lucide-react'
import { Badge, Btn, Modal } from './ui'
import BoutonGeste from './BoutonGeste.jsx'
import CompteurNumerique from './CompteurNumerique.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { peutEnregistrer } from '../lib/gestes.js'
import { emplacementLot } from '../lib/pepiniere.js'
import {
  LEVEE_DISPONIBLE, badgeEtat, dateEnClair, echeanceEnClair, gesteDeLevee, gestePrepare,
  gestesDuLot, incoherenceEnClair, joursDepuisSemis, phraseComparaison, phraseLotSansGeste, phraseSolde,
  tauxLevee, teinteTaux, tracabilite, valeurInitialeCompteur,
} from '../lib/ficheLot.js'

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

// ── Compteur de levée (CA10) ─────────────────────────────────────────────────

/**
 * « Noter la levée » en feuille basse : graines semées rappelées, nombre de levés
 * (clavier numérique ET − / +), taux à mesure avec la comparaison à la moyenne de la
 * culture, case « Levée terminée ». « Envoyer au compagnon » prépare le geste ; le
 * compteur n'écrit rien.
 */
function CompteurLevee({ lot, dateRef, onFermer }) {
  const semees = lot.graines_semees > 0 ? lot.graines_semees : null
  const [leves, setLeves] = useState(() => valeurInitialeCompteur(lot))
  const [termine, setTermine] = useState(false)
  const taux = tauxLevee(leves, semees)
  const phrase = phraseComparaison({ taux, moyenne: lot.moyenne_levee_culture ?? null, culture: lot.culture })

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center" style={{ background: 'rgba(12,18,6,.45)' }} onClick={onFermer}>
      <div
        role="dialog" aria-label="Noter la levée"
        className="w-full max-w-[520px] bg-card rounded-t-[18px] shadow-[0_-10px_40px_rgba(0,0,0,.25)] px-4 pt-3.5 pb-4 flex flex-col gap-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5">
          <div className="flex-1 min-w-0">
            <div className="font-serif text-[18px] font-semibold text-txt">Noter la levée</div>
            <div className="text-[12px] text-txt3 mt-px">
              Lot #{lot.numero_lot} · <span className="capitalize">{lot.culture}</span>{semees != null ? ` · ${semees} graines semées` : ''}
            </div>
          </div>
          <button
            type="button" onClick={onFermer} aria-label="Fermer"
            className="w-12 h-12 flex items-center justify-center rounded-[12px] bg-card-alt text-txt2"
          >
            <X size={18} />
          </button>
        </div>

        <CompteurNumerique
          valeur={leves} onChange={setLeves} max={semees} libelle="Nombre de levés"
          legende={semees != null ? `levés sur ${semees}` : 'levés'}
        />

        <div className="min-h-10 text-[13.5px] font-semibold text-txt leading-[1.4]">
          {phrase
            ? <span className={teinteTaux(taux) === 'red' ? 'text-red' : ''}>{phrase}</span>
            : <span className="text-txt3 font-medium">Le taux s’affiche à mesure du comptage.</span>}
        </div>

        <label className="flex items-center gap-[11px] min-h-12 px-3 rounded-[12px] bg-card-alt cursor-pointer">
          <input type="checkbox" checked={termine} onChange={(e) => setTermine(e.target.checked)} className="w-6 h-6 accent-brand" />
          <span className="text-[13.5px] font-semibold text-txt">Levée terminée</span>
        </label>

        <BoutonGeste
          geste={gesteDeLevee(lot, { leves: leves ?? 0, termine })}
          dateRef={dateRef} ecran="pepiniere" libelle="Envoyer au compagnon" plein desactive={leves == null}
          afficherPhrase={false}   // la phrase de levée sera définie par US-212
          btnClassName="min-h-[52px] text-[15px] font-bold"
        />
        <div className="text-[11.5px] text-txt3 text-center -mt-1">
          Rien n’est enregistré avant ta confirmation dans le compagnon.
        </div>
      </div>
    </div>
  )
}

// ── Le geste, en un appui (CA8, CA9, CA11) ───────────────────────────────────

function Gestes({ lot, dateRef, nbPepinieres, levee, compteurInitial }) {
  const gestes = gestesDuLot(lot, { nbPepinieres, levee })
  const [compteurOuvert, setCompteurOuvert] = useState(compteurInitial)
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
              {g.code === 'noter_levee' ? (
                <Btn
                  kind={p ? 'primary' : 'ghost'} icon={Icone} onClick={() => setCompteurOuvert(true)}
                  className={`w-full ${taille}`} aria-haspopup="dialog"
                >
                  {libelle}
                </Btn>
              ) : (
                <BoutonGeste
                  geste={gestePrepare(g)} dateRef={dateRef} ecran="pepiniere"
                  libelle={libelle} kind={p ? 'primary' : 'ghost'} icone={Icone}
                  plein afficherPhrase={g === principal} btnClassName={taille}
                />
              )}
              {/* Une clôture est définitive : elle dit ce qu'elle solde AVANT d'appuyer. */}
              {g.code === 'cloturer' && <p className="text-[11.5px] text-txt3 leading-snug">{phraseSolde(g.solde)}</p>}
            </div>
          )
        })}
      </div>
      {compteurOuvert && <CompteurLevee lot={lot} dateRef={dateRef} onFermer={() => setCompteurOuvert(false)} />}
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

// ── Le contenu, commun aux deux formes ───────────────────────────────────────

function Contenu({ lot, dateRef, nbPepinieres, onOuvrirDetail, onOuvrirCulture, levee, compteurInitial, lecture }) {
  const sansGeste = phraseLotSansGeste(lot)
  return (
    <div className="@container/fiche flex-1 min-h-0 overflow-y-auto px-4 pt-3 pb-6 min-[480px]:px-[18px] min-[480px]:pt-4 flex flex-col gap-3.5">
      <Identite lot={lot} onOuvrirCulture={onOuvrirCulture} />

      {sansGeste ? (
        <div className="text-[13px] text-txt2 bg-card-alt rounded-[12px] px-[13px] py-[11px] leading-[1.45]">
          <strong className="text-txt">{sansGeste.titre}</strong> : {sansGeste.suite.charAt(0).toLowerCase()}{sansGeste.suite.slice(1)}
        </div>
      ) : (
        <Echeance lot={lot} />
      )}

      {/* [CA12] Un membre en lecture seule voit tout, sans gestes ni compteur. */}
      {!lecture && (
        <Gestes lot={lot} dateRef={dateRef} nbPepinieres={nbPepinieres} levee={levee} compteurInitial={compteurInitial} />
      )}
      {lecture && (
        <div className="text-[12.5px] text-txt3 leading-[1.5]">
          Tu es membre en lecture seule : les gestes sont réservés aux éditeurs du potager.
        </div>
      )}

      <Tracabilite lot={lot} />

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
 *                       la lib ; la page de contrôle visuel le force pour montrer le compteur.
 * @param compteurInitial Ouvre le compteur de levée dès l'affichage (page de contrôle visuel).
 */
export default function FicheLot({
  lot, forme = 'modale', nbPepinieres = null, dateRef = null, onClose, onOuvrirDetail, onOuvrirCulture,
  leveeDisponible = LEVEE_DISPONIBLE, compteurInitial = false,
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
        onOuvrirCulture={onOuvrirCulture} levee={leveeDisponible} compteurInitial={compteurInitial}
        lecture={lecture}
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
