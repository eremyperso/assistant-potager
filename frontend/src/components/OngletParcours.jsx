// [US-218] L'onglet « Ma pépinière » — le parcours du plant (maquette HF
// « Ma pépinière - HF », projet Claude Design potager 2026, gelée le 19/10/2026).
//
// Un kanban emplacement × stade : les lignes sont les pépinières, les colonnes les
// stades, chaque case contient des étiquettes (une par lot, stade et emplacement,
// US-240). Au-dessus, les compteurs et la bande « Le bon moment pour semer » ; en
// bas, le tiroir des lots dormants. Sous 48rem de conteneur, le kanban devient
// quatre onglets de stade.
//
// Rien n'est calculé ici : tout vient du bloc `parcours` de `GET /pepiniere/lots`,
// mis en forme par `lib/parcours.js`. Les gestes DÉPOSENT dans la file
// (`BoutonGeste`, US-224) : une notification confirme, l'écran ne bouge pas.
// Container queries, jamais de breakpoint (CA22).
import { Fragment, useState } from 'react'
import {
  Archive, ArrowRightLeft, Bean, ChevronRight, CircleHelp, CloudDrizzle, Copy, Flame, Moon,
  Plus, Shovel, Snowflake, Sprout, Sun, X,
} from 'lucide-react'
import BoutonGeste from './BoutonGeste.jsx'
import DateRefPicker from './DateRefPicker.jsx'
import { Btn } from './ui'
import { gestePrepare, estCloture, estTermine } from '../lib/ficheLot.js'
import { peutEnregistrer } from '../lib/gestes.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { FicheLotBandeau } from './FicheLot.jsx'
import {
  STADES, aideDuree, bandeSemer, basculerCompteur, caseVide, cleLigneDe, compteursBarre, datesEtiquette, etiquettesDuLot,
  enteteEtiquette, enteteMois, fragmentsLies, gesteSemer, gestesDormant, gestesEtiquette, grandChiffre,
  kanban, lienAutreOnglet, lienFragment, miseEnEvidence, nomAccessible, nomEtiquette,
  ongletStadeParDefaut, ouMettreEtiquette, pastillePepiniere, pepiniereChoisie, phraseDuree,
  phraseProchaineOuverture, phraseRanger, phraseReplies, quantitesEtiquette, regleEtiquette,
  repereFragment, resteDormant, resumeLigne, typeEnClair,
} from '../lib/parcours.js'

const ICONE_GESTE = { repiquer: Sprout, mettre_en_terre: Shovel, cloturer: Archive, ranger: ArrowRightLeft }
const ICONE_COMPTEUR = { a_repiquer: Sprout, a_sortir: Shovel, endurcit: Sun, a_semer: Bean, dormants: Moon }
const ICONE_TYPE = { chaude: Flame, froide: Snowflake }
const FOND_TYPE = { chaude: 'fond-chaude', froide: 'fond-froide' }
const TEINTE_TYPE = {
  chaude: 'bg-amber-soft text-amber', froide: 'bg-blue-soft text-blue',
}

/** La pastille du type de pépinière : un mot et une icône, jamais la seule couleur. */
function PastilleType({ type, court = false }) {
  const Icone = ICONE_TYPE[type] ?? CircleHelp
  const libelle = court ? (type ?? 'type ?') : typeEnClair(type)
  return (
    <span className={`inline-flex items-center gap-1 h-[22px] px-2 rounded-full text-[11px] font-bold whitespace-nowrap ${TEINTE_TYPE[type] ?? 'bg-card-alt text-txt2 outline-dashed outline-1 outline-txt3'}`}>
      <Icone size={13} aria-hidden="true" />{libelle}
    </span>
  )
}

/** Le motif d'un stade : la trame dit le stade en niveaux de gris (RT4). */
const Motif = ({ stade, className = 'w-3.5 h-3.5' }) => (
  <i aria-hidden="true" className={`inline-block rounded-[4px] shrink-0 motif-${STADES.find((s) => s.cle === stade)?.motif} ${className}`} />
)

// ── La barre ────────────────────────────────────────────────────────────────

function Compteur({ c, actif, onAppui }) {
  const Icone = ICONE_COMPTEUR[c.cle]
  const teinte = !c.actif ? 'bg-card-alt text-txt3 opacity-85'
    : c.cle === 'dormants' ? 'bg-violet-soft text-violet'
      : c.alerte ? 'bg-red-soft text-red'
        : c.cle === 'a_sortir' ? 'bg-amber-soft text-amber'
          : 'bg-brand-soft text-brand-text'
  const contenu = (
    <>
      <span className="w-[26px] h-[26px] rounded-full bg-card flex items-center justify-center" aria-hidden="true">
        <Icone size={15} />
      </span>
      <b className="font-hand text-[21px] leading-none">{c.total}</b>
      {c.texte}
      {c.alerte && <span className="sr-only"> dont en retard</span>}
    </>
  )
  const classe = `inline-flex items-center gap-[7px] min-h-[36px] pl-[5px] pr-[13px] rounded-full text-[12px] font-semibold whitespace-nowrap ${teinte} ${actif ? 'ring-2 ring-txt' : ''}`
  if (!c.actif) return <span className={classe}>{contenu}</span>
  return (
    <button type="button" className={classe} onClick={() => onAppui(c)} aria-pressed={c.surligne ? actif : undefined}>
      {contenu}
    </button>
  )
}

// ── La bande « Le bon moment pour semer » ───────────────────────────────────

function TuileSemer({ t, dateRef }) {
  return (
    <li className="flex flex-col gap-1.5 rounded-xl p-3 fenetre-semis @container/tuile">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-serif text-[15px] font-bold text-txt">{t.nom}</span>
        {t.reste && <span className="font-hand text-[18px] font-bold text-sem-d whitespace-nowrap">{t.reste}</span>}
      </div>
      {t.part != null && (
        <div className="h-2 rounded-full bg-card relative overflow-hidden" role="img" aria-label={`${t.part} % de la fenêtre écoulée`}>
          <i className="absolute inset-y-0 left-0 rounded-full motif-sem" style={{ width: `${t.part}%` }} />
        </div>
      )}
      <span className="text-[11.5px] text-txt2">{t.fenetre}</span>
      {/* [US-220 / CA8] Deux types de pépinière : un niveau pour chacun, en mots. */}
      {t.niveaux.length > 0 && <span className="text-[11.5px] text-txt2 leading-snug">{t.niveaux.join(' · ')}</span>}
      <div className="flex items-center justify-between gap-2 mt-auto">
        <span className="text-[12px] text-txt min-w-0 truncate">{t.varietes.join(', ') || 'variété non précisée'}</span>
        <BoutonGeste
          geste={gesteSemer(t)} dateRef={dateRef} ecran="pepiniere" libelle="Semer" icone={Plus}
          kind="primary" small afficherPhrase={false} btnClassName="min-h-[44px]"
          ariaLabel={`Semer ${t.culture} en pépinière`}
        />
      </div>
    </li>
  )
}

function BandeSemer({ bande, dateRef }) {
  const [deplie, setDeplie] = useState(false)
  if (!bande) return null
  const { tuiles, replies, calendrier } = bande
  const phrase = phraseReplies(replies)
  return (
    <section id="bande-semer" aria-labelledby="titre-bande-semer" className="@container/bande bg-card border border-border rounded-[18px] shadow-card scroll-mt-4">
      <div className="grid gap-3 p-3.5 @[48rem]/bande:grid-cols-[250px_minmax(0,1fr)] @[48rem]/bande:gap-[22px] @[48rem]/bande:px-[22px] @[48rem]/bande:py-[18px] items-center">
        <div>
          <h3 id="titre-bande-semer" className="font-hand text-[24px] @[48rem]/bande:text-[31px] font-bold leading-none text-sem-d">
            Le bon moment pour semer
          </h3>
          <ul className="hidden @[48rem]/bande:flex flex-col gap-[3px] mt-2 text-[11.5px] text-txt2">
            {['fenêtre de semis en pépinière ouverte', 'graines de la culture en stock', 'aucun lot de la culture en cours'].map((c) => (
              <li key={c} className="flex items-center gap-[7px]"><i aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-sem" />{c}</li>
            ))}
          </ul>
        </div>
        <div className="min-w-0">
          {tuiles.length > 0 && (
            <ul className="grid gap-2 grid-cols-1 @[32rem]/bande:grid-cols-2 @[64rem]/bande:grid-cols-3">
              {tuiles.map((t) => <TuileSemer key={t.culture} t={t} dateRef={dateRef} />)}
            </ul>
          )}
          {phrase && (
            <p className="text-[12.5px] text-txt2 mt-2">
              {phrase}
              {!deplie && replies.length > 1 && (
                <> · <button type="button" className="font-semibold text-brand-text underline underline-offset-2 min-h-[32px]" onClick={() => setDeplie(true)}>Voir les {replies.length} ›</button></>
              )}
            </p>
          )}
          {deplie && (
            <ul className="flex flex-wrap gap-1.5 mt-2">
              {replies.map((r) => <li key={r} className="text-[12px] rounded-md px-2 py-0.5 bg-card-alt text-txt capitalize">{r}</li>)}
            </ul>
          )}
          {calendrier && <CalendrierSemis calendrier={calendrier} />}
        </div>
      </div>
    </section>
  )
}

const moisLong = (aaaamm) => (aaaamm ? new Date(`${aaaamm}-15T12:00:00`).toLocaleDateString('fr-FR', { month: 'long' }) : '')

/** Rien à semer : la bande dit quand ça rouvre, mois par mois (maquette HF). */
function CalendrierSemis({ calendrier }) {
  const [present, ...suite] = calendrier.mois
  const prochain = calendrier.mois.find((m) => m.s_ouvrent.length)
  return (
    <>
      <p className="text-[13.5px] font-semibold mb-2.5">
        Aucune culture à semer en {moisLong(present?.mois)}
        <span className="font-normal text-txt2"> · zone {calendrier.zone}. {phraseProchaineOuverture(calendrier)}</span>
      </p>
      {/* Téléphone : la prochaine ouverture, en une ligne. */}
      {prochain && (
        <div className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 fenetre-semis @[40rem]/bande:hidden">
          <span className="font-hand text-[22px] font-bold text-sem-d leading-none whitespace-nowrap">dans {prochain.dans_jours} j</span>
          <p className="text-[12px] text-txt">
            <b>{prochain.libelle}</b> · {prochain.s_ouvrent.slice(0, 5).join(', ')}
            {prochain.s_ouvrent.length > 5 ? ` et ${prochain.s_ouvrent.length - 5} autres` : ''} en pépinière
          </p>
        </div>
      )}
      <ol className="hidden @[40rem]/bande:grid grid-cols-6 gap-1.5" aria-label="Ouvertures des six prochains mois">
        {[present, ...suite].filter(Boolean).map((m) => {
          const t = enteteMois(m)
          const ouvert = m.s_ouvrent.length > 0
          return (
            <li key={m.mois} className={`rounded-xl px-2.5 py-2 min-h-[96px] flex flex-col gap-1 ${!m.dans_jours ? 'bg-surface border-[1.5px] border-dashed border-border' : ouvert ? 'fenetre-semis' : 'bg-card-alt'}`}>
              <div className={`flex justify-between items-baseline text-[11px] font-bold ${ouvert ? 'text-sem-d' : !m.dans_jours ? 'text-txt' : 'text-txt3'}`}>
                <span className="capitalize">{t.libelle}</span>
                {(ouvert || !m.dans_jours) && <span className={`font-hand text-[15px] ${ouvert ? 'text-sem-d' : 'text-txt2'}`}>{t.repere}</span>}
              </div>
              {ouvert ? (
                <ul className="flex flex-wrap gap-[3px]">
                  {m.s_ouvrent.map((c) => <li key={c} className="text-[11px] bg-card rounded-md px-1.5 py-px text-txt">{c}</li>)}
                  {m.encore_ouvertes > 0 && <li className="text-[11px] px-1.5 text-sem-d">+ {m.encore_ouvertes} encore ouvertes</li>}
                </ul>
              ) : (
                <span className="text-[11.5px] text-txt3 italic">{m.encore_ouvertes ? `${m.encore_ouvertes} encore ouvertes` : 'aucune'}</span>
              )}
            </li>
          )
        })}
      </ol>
    </>
  )
}

// ── L'étiquette ─────────────────────────────────────────────────────────────

function Regle({ regle }) {
  if (!regle) return null
  if (regle.type === 'sept') {
    return (
      <div className="flex gap-[2px]" role="img" aria-label={`Endurcissement : jour ${regle.jour} sur ${regle.sur}`}>
        {Array.from({ length: regle.sur }, (_, i) => (
          <i key={i} className={`h-2.5 flex-1 rounded-[3px] ${i < regle.jour ? 'motif-end' : 'bg-card-alt'} ${i === regle.jour - 1 ? 'outline outline-2 outline-red' : ''}`} />
        ))}
      </div>
    )
  }
  return (
    <div className="h-2.5 rounded-full bg-card-alt relative my-1" aria-hidden="true">
      <i className="absolute inset-y-0 left-0 rounded-full motif-god opacity-80" style={{ width: `${regle.ecoule}%` }} />
      <em className="absolute inset-y-0 rounded-full regle-fourchette" style={{ left: `${regle.du}%`, width: `${regle.largeur}%` }} />
      <b className="absolute -top-1 -bottom-1 w-[3px] rounded-sm bg-red" style={{ left: `calc(${regle.ref}% - 1.5px)` }} />
    </div>
  )
}

function PhraseDuree({ etiquette }) {
  const [ouverte, setOuverte] = useState(false)
  const [copiee, setCopiee] = useState(false)
  const phrase = phraseDuree(etiquette)
  if (!phrase) return null
  if (!ouverte) {
    return (
      <button type="button" onClick={(e) => { e.stopPropagation(); setOuverte(true) }}
        className="inline-flex items-center min-h-[32px] px-3 rounded-[10px] bg-brand-soft text-brand-text text-[12.5px] font-semibold" aria-expanded="false">
        Renseigner la durée
      </button>
    )
  }
  return (
    <div className="flex flex-col gap-1 rounded-[10px] bg-card-alt p-2 w-full" onClick={(e) => e.stopPropagation()}>
      <span className="text-[11.5px] text-txt2">Dites ou tapez au compagnon :</span>
      <div className="flex items-center gap-1.5">
        <code className="flex-1 min-w-0 text-[12px] text-txt break-words select-all">{phrase}</code>
        <button type="button" className="min-h-[32px] min-w-[32px] inline-flex items-center justify-center rounded-lg border border-border bg-card"
          aria-label="Copier la phrase"
          onClick={() => { navigator.clipboard?.writeText(phrase).then(() => setCopiee(true), () => {}) }}>
          <Copy size={14} aria-hidden="true" />
        </button>
      </div>
      <span className="text-[11px] text-txt3">{copiee ? 'Phrase copiée.' : aideDuree(etiquette)}</span>
    </div>
  )
}

function GestesEtiquette({ gestes, lot, dateRef, onOuvrirFiche, plein, ecriture }) {
  if (!ecriture || !gestes.length) return null
  return (
    <div className={`flex gap-1.5 flex-wrap pt-1 mt-auto ${plein ? 'flex-col' : ''}`} onClick={(e) => e.stopPropagation()}>
      {gestes.map((g) => (g.ouvreFiche ? (
        <Btn key={g.code} kind="ghost" small className={plein ? 'min-h-[48px] w-full justify-center' : 'min-h-[32px]'} aria-label={g.ariaLabel} onClick={() => onOuvrirFiche(lot)}>
          {g.libelle}
        </Btn>
      ) : (
        <BoutonGeste
          key={g.code} geste={gestePrepare(g)} dateRef={dateRef} ecran="pepiniere"
          libelle={g.libelle} ariaLabel={g.ariaLabel}
          kind={g.principal ? 'primary' : 'ghost'} small plein={plein}
          icone={ICONE_GESTE[g.code] ?? Sprout} afficherPhrase={false}
          btnClassName={plein ? '' : 'min-h-[32px]'}
        />
      )))}
    </div>
  )
}

const TON_CADRE = {
  retard: 'border-[1.5px] border-red', inconnu: 'border-dashed border-border', dormant: 'border-border',
}

function Etiquette({
  etiquette, lot, liees, eclairee, ouverte = false, attenuee, dateRef, nbPepinieres, ecriture, pepinieres,
  onSurvol, onOuvrirFiche, onAllerFragment, telephone = false, versOnglet = null,
}) {
  const tete = enteteEtiquette(etiquette, lot)
  const chiffre = grandChiffre(etiquette, dateRef)
  const nom = nomEtiquette(etiquette)
  const repere = repereFragment(etiquette)
  const q = quantitesEtiquette(etiquette)
  const dates = datesEtiquette(etiquette)
  const regle = regleEtiquette(etiquette, dateRef)
  const gestes = gestesEtiquette(etiquette, lot, { nbPepinieres })
  const ou = ouMettreEtiquette(lot, etiquette)
  const sansGesteRanger = etiquette.emplacement_id == null && !gestes.some((g) => g.code === 'ranger')
  return (
    <article
      id={`etq-${etiquette.id}`}
      tabIndex={0}
      aria-label={nomAccessible(etiquette)}
      onPointerEnter={() => onSurvol(etiquette.lot.id)}
      onPointerLeave={() => onSurvol(null)}
      onFocus={() => onSurvol(etiquette.lot.id)}
      onBlur={() => onSurvol(null)}
      aria-expanded={ouverte || undefined}
      onClick={() => lot && onOuvrirFiche(lot, etiquette)}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget && lot) { e.preventDefault(); onOuvrirFiche(lot, etiquette) } }}
      className={`relative bg-card rounded-[14px] shadow-card flex flex-col cursor-pointer border ${TON_CADRE[tete.ton] ?? 'border-border'}
        ${ouverte ? 'outline outline-[3px] outline-offset-2 outline-brand z-[1]' : eclairee ? 'outline outline-[2.5px] outline-offset-2 outline-txt' : ''} ${attenuee ? 'opacity-40' : ''}
        focus-visible:outline focus-visible:outline-[2.5px] focus-visible:outline-offset-2 focus-visible:outline-brand transition-opacity`}
    >
      {/* [maquette HF] L'étiquette dont la fiche est ouverte sous la rangée. */}
      {ouverte && (
        <span className="absolute left-2 -top-[11px] z-[2] rounded-full bg-brand text-white text-[10.5px] font-bold px-2 py-px whitespace-nowrap">
          {etiquette.lot.numero != null ? `#${etiquette.lot.numero} · ` : ''}ouvert
        </span>
      )}
      <header className={`flex justify-between items-center gap-2 px-3 py-1.5 min-h-[34px] rounded-t-[13px] text-[10.5px] font-bold uppercase tracking-[.06em] tete-${tete.ton}`}>
        <span>{tete.libelle}</span>
        {chiffre && (
          <span className="font-hand text-[22px] font-bold normal-case tracking-normal leading-none whitespace-nowrap">
            {chiffre.avant && <small className="text-[13px] font-normal mr-0.5">{chiffre.avant}</small>}
            {chiffre.texte}
            {chiffre.apres && <small className="text-[13px] font-normal ml-0.5">{chiffre.apres}</small>}
          </span>
        )}
      </header>
      <div className="px-3 pt-2.5 pb-3 flex flex-col gap-1.5 flex-1">
        <div className="font-bold text-[14px] flex items-baseline gap-1.5 flex-wrap">
          {nom.culture}
          <small className="font-medium text-txt3 text-[12px]">{[nom.variete, nom.numero].filter(Boolean).join(' · ')}</small>
          {repere && <span className="inline-flex items-center h-[18px] px-1.5 rounded-full bg-txt text-card text-[10px] font-bold">{repere}</span>}
        </div>
        <div className="text-[12.5px] font-semibold">
          {q.principal}{q.detail && <span className="font-normal text-txt2"> · {q.detail}</span>}
        </div>
        <Regle regle={regle} />
        {dates && <div className="text-[11.5px] text-txt3">{dates}</div>}
        {ou && (
          <div className="rounded-[10px] bg-card-alt px-2.5 py-[7px] flex flex-col gap-0.5 text-[11.5px] text-txt2">
            <span className="text-[10.5px] font-bold text-txt3">Où les mettre</span>
            {ou.lignes.map((l) => <div key={l.parcelle}><b className="text-txt">{l.parcelle}</b>{l.detail ? ` · ${l.detail}` : ''}</div>)}
            {ou.manque && <div className="text-amber font-semibold">{ou.manque}</div>}
          </div>
        )}
        {liees.length > 0 && (
          <div className="flex flex-wrap gap-x-3" onClick={(e) => e.stopPropagation()}>
            {liees.map((autre) => (
              <button key={autre.id} type="button" className="text-[12px] font-semibold text-brand-text underline underline-offset-2 min-h-[28px]"
                onClick={() => onAllerFragment(autre)}>
                {telephone && versOnglet?.(autre) ? lienAutreOnglet(autre, pepinieres) : lienFragment(etiquette, autre)}
              </button>
            ))}
          </div>
        )}
        {etiquette.etat === 'duree_inconnue' && ecriture && <PhraseDuree etiquette={etiquette} />}
        {sansGesteRanger && ecriture && (
          <p className="text-[11.5px] text-txt2">Dites au compagnon : « {phraseRanger(etiquette)} »</p>
        )}
        <GestesEtiquette gestes={gestes} lot={lot} dateRef={dateRef} onOuvrirFiche={onOuvrirFiche} plein={telephone} ecriture={ecriture} />
      </div>
    </article>
  )
}

// ── Les lignes ──────────────────────────────────────────────────────────────

const fondLigne = (ligne) => (ligne.sansEmplacement ? 'trame-sans-emplacement' : FOND_TYPE[ligne.type_pepiniere] ?? 'trame-sans-emplacement')

function EnteteLigne({ ligne, compact = false }) {
  const fond = fondLigne(ligne)
  if (compact) {
    return (
      <div className={`relative rounded-xl overflow-hidden min-h-[56px] ${fond}`}>
        <span className="absolute left-0 top-0 m-2 px-2.5 py-1.5 rounded-xl bg-card/90 backdrop-blur-sm shadow-card flex items-center gap-2 text-[13px] font-bold">
          {ligne.sansEmplacement ? 'Sans emplacement' : ligne.nom}
          {!ligne.sansEmplacement && <PastilleType type={ligne.type_pepiniere} court />}
        </span>
      </div>
    )
  }
  return (
    <div className="relative">
      <div className="relative m-2.5 px-3 py-2.5 rounded-xl bg-card/90 backdrop-blur-sm shadow-card flex flex-col items-start text-[13px] font-bold">
        <span className="break-words">{ligne.sansEmplacement ? 'Sans emplacement' : ligne.nom}</span>
        {!ligne.sansEmplacement && <span className="mt-1.5"><PastilleType type={ligne.type_pepiniere} /></span>}
        <small className="block font-normal text-txt3 text-[11.5px] mt-1">{resumeLigne(ligne)}</small>
      </div>
    </div>
  )
}

// ── Le tiroir ───────────────────────────────────────────────────────────────

function Tiroir({ dormants, lotsParId, dateRef, nbPepinieres, ecriture, onOuvrirFiche, ouvert, onOuvrir }) {
  const n = dormants.length
  if (!n) {
    return (
      <div className="bg-violet-soft rounded-[18px] px-[18px] py-3 flex flex-wrap items-baseline gap-2 text-[13px]">
        <span className="font-hand text-[22px] text-violet">0</span><b>lot dormant</b>
        <span className="text-txt2">· aucun lot sans geste depuis plus de 60 jours</span>
      </div>
    )
  }
  return (
    <section id="tiroir-dormants" aria-labelledby="titre-tiroir" className="@container/tiroir bg-violet-soft rounded-[18px] p-3 @[40rem]/tiroir:px-5 @[40rem]/tiroir:pt-[18px] @[40rem]/tiroir:pb-5 flex flex-col gap-3.5 scroll-mt-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h3 id="titre-tiroir" className="font-serif text-[16px] @[40rem]/tiroir:text-[18px] font-bold text-txt">
          <span className="font-hand text-[24px] text-violet mr-1">{n}</span>
          {n > 1 ? 'lots dormants' : 'lot dormant'}
        </h3>
        <p className="text-[12.5px] text-txt2 flex-1 min-w-[12rem]">
          Aucun geste depuis plus de 60 jours · comptés dans les stocks tant qu'ils ne sont pas réglés
        </p>
        {!ouvert && (
          <button type="button" onClick={onOuvrir} className="@[40rem]/tiroir:hidden min-h-[44px] px-3 rounded-[10px] bg-card text-[13px] font-semibold inline-flex items-center gap-1" aria-expanded="false" aria-controls="tiroir-contenu">
            Ouvrir <ChevronRight size={15} aria-hidden="true" />
          </button>
        )}
      </div>
      {/* Au large, le tiroir est ouvert ; au téléphone, « Ouvrir › » le déplie (CA22). */}
      {(
        <ul id="tiroir-contenu" className={`${ouvert ? 'grid' : 'hidden'} @[40rem]/tiroir:grid gap-3 grid-cols-1 @[40rem]/tiroir:grid-cols-2 @[64rem]/tiroir:grid-cols-3`}>
          {dormants.map((d) => {
            const lot = lotsParId.get(d.lot.id)
            const gestes = gestesDormant(d, lot, { nbPepinieres })
            return (
              <li key={d.lot.id}>
                <article
                  tabIndex={0} onClick={() => lot && onOuvrirFiche(lot)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && e.target === e.currentTarget && lot) onOuvrirFiche(lot) }}
                  aria-label={`Lot ${d.lot.numero ?? ''}, ${d.lot.culture}, dormant depuis ${d.jours_sans_geste} jours, ${resteDormant(d)}`}
                  className="bg-card border border-border rounded-[14px] shadow-card flex flex-col cursor-pointer h-full focus-visible:outline focus-visible:outline-[2.5px] focus-visible:outline-brand"
                >
                  <header className="flex justify-between items-center gap-2 px-3 py-1.5 min-h-[34px] rounded-t-[13px] text-[10.5px] font-bold uppercase tracking-[.06em] tete-dormant">
                    <span>Dormant{d.a_des_godets ? ' · godets' : ''}</span>
                    {d.jours_sans_geste != null && <span className="font-hand text-[22px] font-bold normal-case tracking-normal leading-none">{d.jours_sans_geste} j</span>}
                  </header>
                  <div className="px-3 pt-2.5 pb-3 flex flex-col gap-1.5 flex-1">
                    <div className="font-bold text-[14px] flex items-baseline gap-1.5 flex-wrap capitalize">
                      {d.lot.culture}
                      <small className="font-medium text-txt3 text-[12px] normal-case">{[d.lot.variete, d.lot.numero != null ? `#${d.lot.numero}` : null].filter(Boolean).join(' · ')}</small>
                    </div>
                    <div className="text-[12.5px] font-semibold">{resteDormant(d)}</div>
                    {d.lot.date_semis && <div className="text-[11.5px] text-txt3">semé le {new Date(d.lot.date_semis).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}</div>}
                    {ecriture && gestes.length > 0 && (
                      <div className="flex gap-1.5 flex-wrap pt-1 mt-auto" onClick={(e) => e.stopPropagation()}>
                        {gestes.map((g) => (
                          <BoutonGeste
                            key={g.code} geste={gestePrepare(g)} dateRef={dateRef} ecran="pepiniere"
                            libelle={g.libelle} ariaLabel={g.ariaLabel} kind={g.principal ? 'primary' : 'ghost'} small
                            icone={ICONE_GESTE[g.code] ?? Archive} afficherPhrase={false} btnClassName="min-h-[44px]"
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

// ── L'onglet ────────────────────────────────────────────────────────────────

/**
 * @param data     réponse de `GET /pepiniere/lots` (bloc `parcours`, `lots`, `pepinieres`)
 * @param etat     `{ filtre, compteur, stade, tiroir }` — l'état d'écran rendu tel quel au retour (RT12)
 * @param meteo    `GET /meteo`, facultative : la pastille ne s'affiche que si elle est lue
 */
export default function OngletParcours({
  data, etat, setEtat, dateRef, nbPepinieres, lotSelectionne, onOuvrirLot, onVoirLots, meteo = null,
  // [maquette HF, option B] La fiche ouverte en bandeau sous sa rangée : `{ lot, etiquette }`.
  ouvert = null, onFermerFiche, onChoisirFragment, onOuvrirDetail, onOuvrirCulture,
}) {
  const { potagerActif } = usePotager()
  const ecriture = peutEnregistrer(potagerActif?.role)
  const [lie, setLie] = useState(null)
  const parcours = data?.parcours ?? {}
  const ref = data?.date_ref_effective ?? dateRef
  const { lignes, colonnes } = kanban(parcours, { filtre: etat.filtre })
  const etiquettes = parcours.etiquettes ?? []
  const lotsParId = new Map((data?.lots ?? []).map((l) => [l.lot_id, l]))
  const compteurs = compteursBarre(parcours.compteurs)
  const bande = bandeSemer(parcours)
  const pepinieres = parcours.pepinieres ?? []
  const choisie = pepiniereChoisie(parcours, etat.filtre)
  const pastille = pastillePepiniere(pepinieres)
  const stadeMobile = etat.stade && colonnes.some((c) => c.cle === etat.stade) ? etat.stade : ongletStadeParDefaut(colonnes)
  const termines = (data?.lots ?? []).filter((l) => estTermine(l) || estCloture(l))

  function appuiCompteur(c) {
    if (c.surligne) setEtat({ compteur: basculerCompteur(etat.compteur, c.cle) })
    else if (c.cle === 'a_semer') document.getElementById('bande-semer')?.scrollIntoView({ behavior: 'smooth' })
    else if (c.cle === 'dormants') {
      setEtat({ tiroir: true })
      requestAnimationFrame(() => document.getElementById('tiroir-dormants')?.scrollIntoView({ behavior: 'smooth' }))
    }
  }

  function allerFragment(autre) {
    // Téléphone : le fragment peut être dans un autre onglet de stade (CA22).
    if (autre.stade !== stadeMobile) setEtat({ stade: autre.stade })
    requestAnimationFrame(() => {
      const cibles = document.querySelectorAll(`[id="etq-${autre.id}"]`)
      const visible = [...cibles].find((n) => n.offsetParent !== null)
      visible?.focus()
      visible?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }

  const etiquetteProps = (e, telephone = false) => ({
    etiquette: e, lot: lotsParId.get(e.lot.id), liees: fragmentsLies(etiquettes, e),
    eclairee: lie != null && lie === e.lot.id && (e.fragment?.total ?? 1) > 1 || lotSelectionne === e.lot.id,
    ouverte: !telephone && ouvert?.etiquette?.id === e.id,
    attenuee: miseEnEvidence(e, etat.compteur) === false,
    dateRef: ref, nbPepinieres, ecriture, pepinieres, telephone,
    onSurvol: setLie, onOuvrirFiche: onOuvrirLot, onAllerFragment: allerFragment,
    versOnglet: (autre) => autre.stade !== e.stade,
  })

  const aucunLot = !etiquettes.length && !(parcours.dormants ?? []).length

  return (
    <div className="@container/parcours flex flex-col gap-[18px]">
      {/* [CA2-CA4] La barre : date, météo, pépinière, compteurs. */}
      <div className="flex items-center gap-3 flex-wrap">
        <DateRefPicker />
        {meteo?.label && (
          <span className="hidden @[40rem]/parcours:inline-flex items-center gap-[7px] min-h-[34px] px-3 rounded-[10px] bg-blue-soft text-blue text-[12.5px] font-semibold whitespace-nowrap">
            <CloudDrizzle size={16} aria-hidden="true" />{meteo.label}
            {meteo.previsions?.[0] && <span className="font-medium"> · {meteo.previsions[0].temp_min} à {meteo.previsions[0].temp_max} °C</span>}
          </span>
        )}
        {pastille ? (
          <span className="inline-flex items-center min-h-[34px] px-3 rounded-[10px] border border-border bg-card text-[12px] font-semibold tracking-[.03em] text-txt2">{pastille}</span>
        ) : pepinieres.length > 1 && (
          <label className="inline-flex items-center gap-2 min-h-[34px] text-[12.5px] font-semibold">
            <span className="sr-only">Pépinière affichée</span>
            <select
              value={choisie ? String(choisie.id) : ''}
              onChange={(e) => setEtat({ filtre: e.target.value || null })}
              className="min-h-[34px] px-3 rounded-[10px] border border-border bg-card text-txt"
            >
              <option value="">Toutes les pépinières</option>
              {pepinieres.map((p) => <option key={p.id} value={String(p.id)}>{p.nom}</option>)}
            </select>
          </label>
        )}
        {choisie && (
          <button type="button" onClick={() => setEtat({ filtre: null })}
            className="inline-flex items-center gap-1.5 min-h-[34px] px-3 rounded-full bg-brand-soft text-brand-text text-[12.5px] font-semibold">
            {choisie.nom} <X size={13} aria-hidden="true" /><span className="sr-only">— retirer le filtre de pépinière</span>
          </button>
        )}
        <span className="flex-1" />
        <div className="flex gap-1.5 flex-wrap" aria-label="Ce qu'il y a à faire">
          {compteurs.map((c) => <Compteur key={c.cle} c={c} actif={etat.compteur === c.cle} onAppui={appuiCompteur} />)}
        </div>
      </div>

      <BandeSemer bande={bande} dateRef={ref} />

      {aucunLot ? (
        <div className="flex flex-col items-center gap-2 py-10 text-txt3">
          <Sprout size={32} aria-hidden="true" />
          <p className="text-[15px]">Aucun lot en cours</p>
        </div>
      ) : (
        <>
          {/* [CA8-CA11, CA24] Le kanban, un tableau : lignes = pépinières, colonnes = stades. */}
          <div className="hidden @[48rem]/parcours:block bg-card border border-border rounded-[18px] shadow-card overflow-hidden">
            <table className="w-full table-fixed border-collapse">
              <caption className="sr-only">Les lots par emplacement et par stade</caption>
              <colgroup><col className="w-[170px]" />{STADES.map((s) => <col key={s.cle} />)}</colgroup>
              <thead>
                <tr className="border-b border-border">
                  <th scope="col" className="px-3.5 py-3 text-left text-[11.5px] font-bold text-txt2">Emplacement</th>
                  {colonnes.map((c) => (
                    <th key={c.cle} scope="col" className="px-3.5 py-3 border-l border-border-soft text-left">
                      <span className="flex items-center justify-between gap-2 text-[11.5px] font-bold text-txt2">
                        <span className="flex items-center gap-2"><Motif stade={c.cle} />{c.libelle}</span>
                        <b className={`font-hand text-[21px] leading-none ${c.cle === 'pret' && c.total ? 'text-frk-d' : c.alerte ? 'text-red' : 'text-txt3'}`}>
                          {c.total}<span className="sr-only"> étiquette{c.total > 1 ? 's' : ''}</span>
                        </b>
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lignes.map((l, i) => (
                  <Fragment key={l.cle}>
                  <tr className="border-t border-border align-top">
                    <th scope="row" className={`p-0 text-left font-normal align-top min-h-[200px] ${fondLigne(l)}`}>
                      <EnteteLigne ligne={l} />
                    </th>
                    {STADES.map((s) => (
                      <td key={s.cle} className="p-2.5 border-l border-border-soft align-top">
                        <div className="flex flex-col gap-2.5">
                          {l.cases[s.cle].length ? l.cases[s.cle].map((e) => <Etiquette key={e.id} {...etiquetteProps(e)} />) : (
                            <p className="border-[1.5px] border-dashed border-border rounded-xl px-3 py-2.5 text-[12px] text-txt3 italic">
                              {caseVide(s.cle, l)}
                            </p>
                          )}
                        </div>
                      </td>
                    ))}
                  </tr>
                  {/* [maquette HF, option B] La fiche du lot ouvert, sous SA rangée — ou sous la
                      dernière si sa rangée est filtrée. */}
                  {ouvert && (cleLigneDe(ouvert.etiquette) === l.cle
                    || (i === lignes.length - 1 && !lignes.some((x) => x.cle === cleLigneDe(ouvert.etiquette)))) && (
                    <tr>
                      <td colSpan={STADES.length + 1} className="p-0">
                        <FicheLotBandeau
                          lot={ouvert.lot} etiquette={ouvert.etiquette}
                          fragments={etiquettesDuLot(parcours, ouvert.etiquette.lot.id)}
                          pepinieres={pepinieres} dateRef={ref} nbPepinieres={nbPepinieres}
                          onClose={onFermerFiche} onChoisirFragment={onChoisirFragment}
                          onOuvrirDetail={onOuvrirDetail} onOuvrirCulture={onOuvrirCulture}
                        />
                      </td>
                    </tr>
                  )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {/* [CA21, CA22] Téléphone : quatre onglets de stade, étiquettes groupées par pépinière. */}
          <div className="@[48rem]/parcours:hidden flex flex-col gap-3">
            <div role="tablist" aria-label="Stades" className="grid grid-cols-4 gap-1">
              {colonnes.map((c) => {
                const on = c.cle === stadeMobile
                return (
                  <button
                    key={c.cle} type="button" role="tab" aria-selected={on}
                    onClick={() => setEtat({ stade: c.cle })}
                    className={`relative min-h-[56px] rounded-xl border flex flex-col items-center justify-center gap-0.5 text-[10.5px] font-bold ${on ? 'bg-txt border-txt text-card' : 'bg-card border-border text-txt2'}`}
                  >
                    <b className={`font-hand text-[21px] leading-none flex items-center gap-[5px] ${on ? 'text-card' : 'text-txt3'}`}>
                      <Motif stade={c.cle} className="w-2.5 h-2.5" />{c.total}
                    </b>
                    {c.court}
                    {c.alerte && <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red" aria-label="contient un retard" />}
                  </button>
                )
              })}
            </div>
            <div role="tabpanel" className="flex flex-col gap-3">
              {lignes.map((l) => {
                const siennes = l.cases[stadeMobile]
                return (
                  <section key={l.cle} aria-label={l.sansEmplacement ? 'Sans emplacement' : l.nom} className="flex flex-col gap-2">
                    <EnteteLigne ligne={l} compact />
                    {siennes.length ? siennes.map((e) => <Etiquette key={e.id} {...etiquetteProps(e, true)} />) : (
                      <p className="rounded-[14px] border-[1.5px] border-dashed border-border px-3 py-2.5 text-[12.5px] text-txt2 bg-surface">
                        {caseVide(stadeMobile, l)}
                      </p>
                    )}
                  </section>
                )
              })}
            </div>
          </div>
        </>
      )}

      <Tiroir
        dormants={parcours.dormants ?? []} lotsParId={lotsParId} dateRef={ref} nbPepinieres={nbPepinieres}
        ecriture={ecriture} onOuvrirFiche={onOuvrirLot}
        ouvert={Boolean(etat.tiroir)} onOuvrir={() => setEtat({ tiroir: true })}
      />

      {termines.length > 0 && (
        <p className="text-[12px] text-txt2">
          <b className="text-txt">{termines.length} lot{termines.length > 1 ? 's' : ''} terminé{termines.length > 1 ? 's' : ''}</b>
          {' '}: {termines.slice(0, 4).map((l) => `${String(l.culture ?? '').toLowerCase()}${l.numero_lot != null ? ` #${l.numero_lot}` : ''}`).join(', ')}
          {termines.length > 4 ? '…' : ''}. <button type="button" className="font-semibold text-brand-text underline underline-offset-2" onClick={onVoirLots}>Visibles dans Lots</button>
        </p>
      )}
    </div>
  )
}
