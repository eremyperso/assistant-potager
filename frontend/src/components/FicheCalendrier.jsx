import { useEffect, useRef, useState } from 'react'
import { CalendarDays, MapPin, ShoppingBasket, Clock } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  Modal, Btn, Badge, InfoBanner, MonthStrip, BlocConfiance, SelecteurAction,
} from './ui'
import ModalModifierPotager from './ModalModifierPotager.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import {
  actionsDeFiche, meilleureCandidate, meteoIndeterminee, recolteLisible, dateLongue,
  LIBELLE_ENREGISTRER,
} from '../lib/confiance.js'
import {
  fenetreDeAction, seriesDeCulture, friseDeFiche, attributionDeFiche,
} from '../lib/ficheCalendrier.js'
import { zoneAffichable, TIRET } from '../lib/calendrier.js'
import { moisDeLaDate } from '../lib/plan.js'

/**
 * [US-183] Fiche calendrier d'une culture — maquette gelée du 18/09/2026.
 *
 * Trois parties, dans cet ordre : 1) semer ou planter, 2) déjà en terre,
 * 3) la frise, en pied — la fiche sert d'abord à décider, la frise confirme.
 *
 * [CA13] Au plus DEUX lectures, et aucune quand l'écran d'origine les a déjà
 * faites : `calendriers` (réponse de `GET /plan/calendriers`, projections
 * comprises) et `confiances` (réponse de `GET /plan/confiances/candidates`)
 * sont passés par l'écran d'origine quand il les a ; sinon (`undefined`, y
 * compris après un échec de l'écran), la fiche les lit elle-même, une fois.
 * Une lecture échouée ici laisse la fiche ouverte avec ce qu'elle a (CA14).
 *
 * [CA6] ⚠️ Le bouton d'enregistrement n'est rendu que si l'appelant fournit
 * `onEnregistrer` : la PWA n'a pas encore de flux d'enregistrement, et la fiche
 * n'en crée pas un (« aucun nouveau chemin d'écriture »).
 */
export default function FicheCalendrier({
  culture, dateRef, potagerId, parcelleId = null,
  calendriers: calendriersFournis, confiances: confiancesFournies,
  onEnregistrer, onClose,
}) {
  const [calendriers, setCalendriers] = useState(calendriersFournis)
  const [confiances, setConfiances] = useState(confiancesFournies)
  const [chargement, setChargement] = useState(
    calendriersFournis === undefined || confiancesFournies === undefined,
  )

  useEffect(() => {
    if (!chargement) return undefined
    let annule = false
    Promise.allSettled([
      calendriersFournis === undefined ? api.calendriersPlan([culture], potagerId, dateRef) : null,
      confiancesFournies === undefined ? api.confiancesPlan([culture], potagerId, dateRef) : null,
    ]).then(([cal, conf]) => {
      if (annule) return
      // [CA14] Une lecture échouée laisse `null` : frise neutre ou confiance
      // absente, jamais une valeur de repli.
      if (calendriersFournis === undefined) setCalendriers(cal.status === 'fulfilled' ? cal.value : null)
      if (confiancesFournies === undefined) setConfiances(conf.status === 'fulfilled' ? conf.value : null)
      if (cal.status === 'rejected') console.warn('[US-183] Calendrier indisponible', cal.reason)
      if (conf.status === 'rejected') console.warn('[US-183] Confiance indisponible', conf.reason)
      setChargement(false)
    })
    return () => { annule = true }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps -- une ouverture, une lecture

  const zone = zoneAffichable(calendriers)?.zone
  const sousTitre = ['toutes variétés', zone && `zone ${zone}`, dateRef && `au ${dateLongue(dateRef)}`]
    .filter(Boolean).join(' · ')

  return (
    <Modal
      title={culture ? culture.charAt(0).toUpperCase() + culture.slice(1) : ''}
      icon={CalendarDays}
      sub={sousTitre}
      onClose={onClose}
      disposition="adaptative"
      bodyClassName="p-[17px] overflow-y-auto min-h-0 flex-1"
      foot={
        <div className="flex items-center justify-between gap-2.5">
          <span className="text-[11.5px] text-txt3 leading-snug">Projections indicatives, recalculées à chaque ouverture.</span>
          <Btn onClick={onClose}>Fermer</Btn>
        </div>
      }
    >
      {chargement ? (
        // [CA13] Un état de chargement, jamais des tirets qui se remplissent.
        <div role="status" className="flex flex-col gap-3 animate-pulse" aria-label="Chargement de la fiche">
          <div className="h-3 w-32 rounded bg-card-alt" />
          <div className="h-10 rounded-[11px] bg-card-alt" />
          <div className="h-28 rounded-[14px] bg-card-alt" />
          <div className="h-3 w-40 rounded bg-card-alt" />
          <div className="h-6 rounded bg-card-alt" />
        </div>
      ) : (
        <CorpsFiche
          culture={culture}
          dateRef={dateRef}
          parcelleId={parcelleId}
          calendriers={calendriers}
          entree={confiances?.cultures?.[culture] ?? null}
          confianceLue={confiances != null}
          onEnregistrer={onEnregistrer}
        />
      )}
    </Modal>
  )
}

function BlocTitre({ children, sub }) {
  return (
    <div className="mb-2.5">
      <h3 className="text-[11px] font-bold text-txt3 uppercase tracking-[.06em]">{children}</h3>
      {sub && <div className="text-[12px] text-txt3 mt-[3px] leading-[1.45]">{sub}</div>}
    </div>
  )
}

function CorpsFiche({ culture, dateRef, parcelleId, calendriers, entree, confianceLue, onEnregistrer }) {
  const series = seriesDeCulture(calendriers, culture, parcelleId)
  const frise = friseDeFiche(calendriers, culture, series)
  const attribution = attributionDeFiche(calendriers)
  return (
    <div className="flex flex-col gap-[18px]">
      <section>
        <BlocTitre>Semer ou planter</BlocTitre>
        <PartieSemerPlanter
          culture={culture} dateRef={dateRef} calendriers={calendriers}
          entree={entree} confianceLue={confianceLue} onEnregistrer={onEnregistrer}
        />
      </section>

      {/* [CA10] Sans série en terre, la partie est absente — pas un bloc vide. */}
      {series.length > 0 && (
        <section>
          <BlocTitre sub="La plus ancienne en tête.">Déjà en terre · {series.length}</BlocTitre>
          <div className="flex flex-col gap-[9px]">
            {series.map((s, i) => <CarteSerie key={`${s.parcelleId}-${s.variete}-${i}`} s={s} />)}
          </div>
        </section>
      )}

      <section>
        <BlocTitre>{frise.titre}</BlocTitre>
        {frise.recalee ? (
          <MonthStrip
            pepiniere={frise.frise.pepiniere} pleineTerre={frise.frise.pleineTerre}
            plantation={frise.frise.plantation} croissance={frise.frise.croissance} rec={frise.frise.rec}
            moisCourant={moisDeLaDate(dateRef)} legend
          />
        ) : (
          <MonthStrip
            pepiniere={frise.frise.pepiniere} pleineTerre={frise.frise.pleineTerre}
            plantation={frise.frise.plantation} rec={frise.frise.rec}
            moisCourant={moisDeLaDate(dateRef)} legend
          />
        )}
        {/* [CA16] L'attribution du référentiel, une seule fois — et seulement
            quand des valeurs du référentiel s'affichent (frise non neutre). */}
        {attribution && !frise.frise.degrade && (
          <div className="text-[11px] text-txt3 mt-2.5">Source : {attribution}</div>
        )}
      </section>
    </div>
  )
}

/** [CA4-CA7] Partie 1 : sélecteur, fenêtre, confiance, récolte attendue. */
function PartieSemerPlanter({ culture, dateRef, calendriers, entree, confianceLue, onEnregistrer }) {
  const actions = actionsDeFiche(entree)
  // [CA4] Pré-positionné sur la meilleure confiance ; à égalité, la règle de la frise.
  const [choisie, setChoisie] = useState(() => meilleureCandidate(actions)?.action ?? null)
  const [localiser, setLocaliser] = useState(false)
  const { potagerActif } = usePotager()

  // [CA14] Confiance illisible : on le dit, sans rien estimer.
  if (!confianceLue) {
    return <p className="text-[12.5px] text-txt3">Le niveau de confiance n’a pas pu être lu pour le moment.</p>
  }
  // [CA4] Aucune fenêtre de semis ni de plantation pour la zone.
  if (!entree?.a_calendrier || actions.length === 0) {
    const zone = zoneAffichable(calendriers)?.zone
    return (
      <div className="bg-card-alt rounded-[14px] px-[15px] py-3.5">
        <div className="text-[13px] text-txt leading-[1.55]">
          Aucun calendrier pour {culture.toLowerCase()} dans {zone ? `la zone ${zone}` : 'ta zone'} : la confiance ne peut pas être évaluée.
        </div>
        <div className="mt-[9px] text-[12.5px] font-semibold text-brand-text">
          Pour compléter la fenêtre, dis-le au bot : « /calendrier fenetre {culture.toLowerCase()} … »
        </div>
      </div>
    )
  }

  const a = actions.find((x) => x.action === choisie) || actions[0]
  const recolte = recolteLisible(a)
  const note = (a.avertissements || []).join(' ') || null
  return (
    <>
      <SelecteurAction actions={actions} value={a.action} onChange={setChoisie} />
      <div className="text-[12.5px] text-txt2 mb-2.5 leading-normal">
        Fenêtre conseillée{zoneAffichable(calendriers)?.zone ? ` en zone ${zoneAffichable(calendriers).zone}` : ''} :{' '}
        <strong className="text-txt font-bold">{fenetreDeAction(calendriers, culture, a.action)}</strong>
      </div>
      {/* Même évaluation que la pastille de la tuile : deux valeurs différentes
          pour la même culture au même instant seraient un bug. */}
      <BlocConfiance key={a.action} confiance={a} note={note} />
      <div className="flex items-start gap-[9px] mt-3">
        <ShoppingBasket size={17} className="text-amber shrink-0" aria-hidden="true" />
        <div className="flex-1 min-w-0 text-[13px] text-txt leading-normal">
          Récolte attendue <strong className="font-bold">{recolte}</strong> si le geste est fait le {dateLongue(dateRef)}.
          {recolte === TIRET && (
            <div className="text-[11.5px] text-txt3 mt-[3px]">La durée jusqu’à la récolte n’est pas renseignée pour ce geste : rien n’est projeté.</div>
          )}
        </div>
      </div>
      {/* [CA7] Même parcours que l'invitation d'US-076 : la modale du potager. */}
      {meteoIndeterminee(a) && (
        <div className="mt-3">
          <InfoBanner
            tint="blue"
            icon={MapPin}
            dismissible={false}
            title="Potager non localisé"
            body="Sans localisation, la météo n’est pas lue : deux règles restent indéterminées et la troisième étoile est inaccessible."
            action={potagerActif ? <Btn small icon={MapPin} onClick={() => setLocaliser(true)}>Localiser</Btn> : null}
          />
        </div>
      )}
      {onEnregistrer && (
        <div className="flex justify-end mt-3">
          <Btn kind="primary" onClick={() => onEnregistrer({ culture, action: a.action, date: dateRef })}>
            {LIBELLE_ENREGISTRER[a.action]}
          </Btn>
        </div>
      )}
      {localiser && potagerActif && (
        <ModalModifierPotager potager={potagerActif} onClose={() => setLocaliser(false)} />
      )}
    </>
  )
}

function SerieStat({ label, value }) {
  return (
    <div className="min-w-0">
      <div className="text-[9.5px] font-bold text-txt3 uppercase tracking-[.04em]">{label}</div>
      <div className={`text-[13.5px] mt-0.5 leading-[1.3] ${value ? 'font-bold text-txt' : 'font-medium text-txt3'}`}>{value || TIRET}</div>
    </div>
  )
}

/** [CA8, CA9] Une série en terre : parcelle, origine, trois repères, écart éventuel. */
function CarteSerie({ s }) {
  const ref = useRef(null)
  // [CA2] Ouverte depuis une tuile, la fiche amène sa série sous les yeux.
  useEffect(() => { if (s.enAvant) ref.current?.scrollIntoView?.({ block: 'nearest' }) }, [s.enAvant])
  const bordure = s.enAvant ? 'border-solid border-brand' : s.levee ? 'border-solid border-border' : 'border-dashed border-border'
  return (
    <div ref={ref} className={`bg-card border rounded-[13px] p-[13px] ${bordure}`}>
      <div className="flex items-center gap-2 flex-wrap">
        <MapPin size={15} className="text-txt3" aria-hidden="true" />
        <span className="font-serif text-[14.5px] font-semibold text-txt">{s.parcelle}</span>
        {s.variete && <span className="font-serif italic text-[12.5px] text-txt3">{s.variete}</span>}
        {s.origineLisible && <Badge tint={s.origine === 'plantation' ? 'brand' : 'blue'}>{s.origineLisible}</Badge>}
        {s.enAvant && <span className="sr-only">(série de la parcelle consultée)</span>}
      </div>
      <div className="grid grid-cols-3 gap-2.5 mt-[11px] pt-2.5 border-t border-border-soft">
        <SerieStat label="Levée attendue" value={s.levee} />
        <SerieStat label={s.recolteLibelle} value={s.recolte} />
        <SerieStat label="Reste à courir" value={s.reste} />
      </div>
      {s.ecart && (
        <div className="flex items-center gap-[7px] mt-2.5 bg-amber-soft rounded-[9px] px-2.5 py-[7px]">
          <Clock size={14} className="text-amber shrink-0" aria-hidden="true" />
          <span className="text-[12px] text-amber dark:text-txt leading-[1.4]">{s.ecart}</span>
        </div>
      )}
      {s.raisonSansProjection && (
        <div className="text-[11.5px] text-txt3 mt-[9px] leading-normal">{s.raisonSansProjection}</div>
      )}
      {s.autresSeries > 0 && (
        <div className="text-[11.5px] text-txt3 mt-[9px]">
          {s.autresSeries === 1 ? 'Une autre série en place dans cette parcelle.' : `${s.autresSeries} autres séries en place dans cette parcelle.`}
        </div>
      )}
    </div>
  )
}
