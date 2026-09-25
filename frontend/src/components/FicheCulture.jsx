import { useEffect, useState } from 'react'
import { Leaf, CalendarDays, MapPin, ShoppingBasket, BookOpen, AlertTriangle, ChevronDown } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Btn, Badge, InfoBanner, MonthStrip, PastillePhase } from './ui'
import FicheCalendrier from './FicheCalendrier.jsx'
import {
  sectionMaintenant, etatAuPotager, lignesReferentiel, groupesVoisinages, badgeContexte, sourcesDeFiche,
} from '../lib/ficheCulture.js'
import { dateLongue } from '../lib/confiance.js'
import { friseDeCulture, zoneAffichable, TIRET } from '../lib/calendrier.js'
import { moisDeLaDate } from '../lib/plan.js'

/**
 * [US-207] Fiche culture — six sections, dans l'ordre d'utilité : Maintenant,
 * Calendrier de la zone, Référentiel, Variétés cultivées, Voisinages,
 * Bioagresseurs. Elle renvoie à la fiche calendrier (US-183) sans la
 * dupliquer : « Ouvrir la fiche calendrier » l'empile par-dessus.
 *
 * [CA3] Trois lectures au plus : la composition (US-206, toujours lue ici) et,
 * quand l'écran d'origine ne les a pas déjà, le calendrier de zone et la
 * confiance — en parallèle, une fois, comme la fiche calendrier.
 *
 * [CA12] Une lecture échouée laisse la fiche ouverte avec ce qu'elle a :
 * chaque section touchée par l'échec écrit « Cette section n'a pas pu être
 * lue » à sa place plutôt que de disparaître.
 */
export default function FicheCulture({
  culture, dateRef, potagerId, parcelleId = null, nomParcelle = null, rang = null,
  calendriers: calendriersFournis, confiances: confiancesFournies,
  ecran = null, onClose,
}) {
  const [fiche, setFiche] = useState(null)
  const [ficheEchouee, setFicheEchouee] = useState(false)
  const [calendriers, setCalendriers] = useState(calendriersFournis)
  const [confiances, setConfiances] = useState(confiancesFournies)
  const [chargement, setChargement] = useState(true)
  const [essai, setEssai] = useState(0)
  const [calendrierOuvert, setCalendrierOuvert] = useState(false)

  useEffect(() => {
    let annule = false
    setChargement(true)
    Promise.allSettled([
      api.ficheCulture(culture, potagerId, dateRef),
      calendriersFournis === undefined ? api.calendriersPlan([culture], potagerId, dateRef) : null,
      confiancesFournies === undefined ? api.confiancesPlan([culture], potagerId, dateRef) : null,
    ]).then(([f, cal, conf]) => {
      if (annule) return
      setFiche(f.status === 'fulfilled' ? f.value : null)
      setFicheEchouee(f.status === 'rejected')
      if (calendriersFournis === undefined) setCalendriers(cal.status === 'fulfilled' ? cal.value : null)
      if (confiancesFournies === undefined) setConfiances(conf.status === 'fulfilled' ? conf.value : null)
      if (f.status === 'rejected') console.warn('[US-207] Fiche culture indisponible', f.reason)
      if (cal?.status === 'rejected') console.warn('[US-207] Calendrier indisponible', cal.reason)
      if (conf?.status === 'rejected') console.warn('[US-207] Confiance indisponible', conf.reason)
      setChargement(false)
    })
    return () => { annule = true }
  }, [essai])  // eslint-disable-line react-hooks/exhaustive-deps -- une ouverture (ou un « Réessayer »), une lecture

  const zone = zoneAffichable(calendriers)?.zone
  const sousTitre = [
    ficheEchouee ? null : (fiche?.fiche_absente ? 'hors référentiel' : fiche?.famille),
    zone && `zone ${zone}`,
    dateRef && `au ${dateLongue(dateRef)}`,
  ].filter(Boolean).join(' · ')
  const badge = badgeContexte({ nomParcelle, rang })

  return (
    <>
      <Modal
        title={culture ? culture.charAt(0).toUpperCase() + culture.slice(1) : ''}
        icon={Leaf}
        sub={sousTitre}
        onClose={onClose}
        disposition="adaptative"
        width={560}
        bodyClassName="p-[17px] overflow-y-auto min-h-0 flex-1 @container/fiche-culture"
        foot={
          <div className="flex items-center justify-between gap-2.5">
            <span className="text-[11.5px] text-txt3 leading-snug">{sourcesDeFiche(fiche) || ''}</span>
            <Btn onClick={onClose}>Fermer</Btn>
          </div>
        }
      >
        {badge && (
          <div className="mb-3">
            <Badge tint="brand"><MapPin size={12} strokeWidth={2} />{badge}</Badge>
          </div>
        )}
        {chargement ? (
          // [CA3] Un état de chargement, jamais des tirets qui se remplissent.
          <div role="status" className="flex flex-col gap-3 animate-pulse" aria-label="Chargement de la fiche">
            <div className="h-3 w-32 rounded bg-card-alt" />
            <div className="h-24 rounded-[14px] bg-card-alt" />
            <div className="h-10 rounded-[11px] bg-card-alt" />
            <div className="h-3 w-40 rounded bg-card-alt" />
          </div>
        ) : (
          <CorpsFiche
            culture={culture} dateRef={dateRef} parcelleId={parcelleId}
            fiche={fiche} ficheEchouee={ficheEchouee}
            calendriers={calendriers} confiances={confiances}
            onReessayer={() => setEssai((n) => n + 1)}
            onOuvrirCalendrier={() => setCalendrierOuvert(true)}
          />
        )}
      </Modal>
      {calendrierOuvert && (
        <FicheCalendrier
          culture={culture} dateRef={dateRef} potagerId={potagerId} parcelleId={parcelleId}
          calendriers={calendriers} confiances={confiances}
          ecran={ecran} onClose={() => setCalendrierOuvert(false)}
        />
      )}
    </>
  )
}

function BlocTitre({ children, n }) {
  return (
    <h3 className="text-[11px] font-bold text-txt3 uppercase tracking-[.06em] mb-2.5">
      {children}{n != null ? ` · ${n}` : ''}
    </h3>
  )
}

function NonLue() {
  return (
    <div className="text-[12.5px] text-txt3 border border-dashed border-border rounded-[10px] px-3 py-2.5">
      Cette section n’a pas pu être lue.
    </div>
  )
}

function Absence({ children }) {
  return (
    <div className="text-[12.5px] text-txt2 bg-card-alt rounded-[10px] px-3 py-2.5 leading-[1.5]">{children}</div>
  )
}

function CorpsFiche({ culture, dateRef, parcelleId, fiche, ficheEchouee, calendriers, confiances, onReessayer, onOuvrirCalendrier }) {
  if (fiche?.fiche_absente) {
    return (
      <div className="flex flex-col gap-[22px]">
        <InfoBanner
          tint="blue" icon={BookOpen} dismissible={false}
          title="Fiche absente du référentiel"
          body={`${culture} n’est pas connue du référentiel : ni calendrier, ni caractéristiques, ni voisinages. Ce que tu cultives reste listé ci-dessous.`}
        />
        <SectionVarietes fiche={fiche} />
      </div>
    )
  }

  const entree = confiances?.cultures?.[culture] ?? null
  const confianceLue = confiances !== null && confiances !== undefined

  return (
    <div className="flex flex-col gap-[22px]">
      {ficheEchouee && (
        <InfoBanner
          tint="amber" icon={AlertTriangle} dismissible={false}
          title="Lecture incomplète"
          body="La composition de la fiche n’a pas pu être lue. « Maintenant » et la frise restent servies par l’écran d’origine."
          action={<Btn small onClick={onReessayer}>Réessayer</Btn>}
        />
      )}

      <SectionMaintenant
        entree={entree} calendriers={calendriers} culture={culture} confianceLue={confianceLue}
        varietesCultivees={fiche?.varietes_cultivees} onOuvrirCalendrier={onOuvrirCalendrier}
      />

      <SectionCalendrier calendriers={calendriers} culture={culture} dateRef={dateRef} />

      {ficheEchouee ? (
        <>
          <section><BlocTitre>Référentiel</BlocTitre><NonLue /></section>
          <section><BlocTitre>Variétés cultivées</BlocTitre><NonLue /></section>
          <section><BlocTitre>Voisinages</BlocTitre><NonLue /></section>
          <section><BlocTitre>Bioagresseurs</BlocTitre><NonLue /></section>
        </>
      ) : (
        <>
          <SectionReferentiel fiche={fiche} />
          <SectionVarietes fiche={fiche} />
          <SectionVoisinages fiche={fiche} />
          <SectionBioagresseurs fiche={fiche} />
        </>
      )}
    </div>
  )
}

/** [CA4] Le geste le mieux noté, ouvert ou non, et l'état au potager. */
function SectionMaintenant({ entree, calendriers, culture, confianceLue, varietesCultivees, onOuvrirCalendrier }) {
  const m = sectionMaintenant({ entree, calendriers, culture, confianceLue })
  const etatPotager = etatAuPotager(varietesCultivees)
  return (
    <section>
      <BlocTitre>Maintenant</BlocTitre>
      <div className="bg-card-alt rounded-[14px] px-[15px] py-3.5">
        {m.etat === 'illisible' && (
          <div className="text-[13px] text-txt2">Le niveau de confiance n’a pas pu être lu pour le moment.</div>
        )}
        {m.etat === 'sans_calendrier' && (
          <div className="text-[13px] text-txt2 leading-[1.55]">
            Aucun calendrier pour {(culture || '').toLowerCase()} dans ta zone : la confiance ne peut pas être évaluée.
          </div>
        )}
        {m.etat === 'ouverte' && (
          <>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-[15px] font-bold text-txt">{m.geste} maintenant</span>
              <span aria-hidden="true" className="text-amber">{'★'.repeat(m.etoiles)}{'☆'.repeat(3 - m.etoiles)}</span>
              <span className="sr-only">{m.etoiles} étoile{m.etoiles > 1 ? 's' : ''} sur 3</span>
            </div>
            <div className="text-[12.5px] text-txt2 mt-1">Fenêtre conseillée : <strong className="text-txt font-bold">{m.fenMois}</strong></div>
            {m.recolteAttendue && m.recolteAttendue !== TIRET && (
              <div className="flex items-start gap-2 mt-2">
                <ShoppingBasket size={16} className="text-amber shrink-0" aria-hidden="true" />
                <span className="text-[12.5px] text-txt leading-[1.5]">Récolte attendue <strong className="font-bold">{m.recolteAttendue}</strong> si le geste est fait aujourd’hui.</span>
              </div>
            )}
          </>
        )}
        {m.etat === 'fermee' && (
          <>
            <div className="text-[15px] font-bold text-txt">Rien à semer ni planter ce mois-ci</div>
            <div className="text-[12.5px] text-txt2 mt-1">Prochaine fenêtre : <strong className="text-txt font-bold">{m.geste} {m.fenMois}</strong></div>
          </>
        )}
        {(m.etat === 'ouverte' || m.etat === 'fermee') && m.meteoIndeterminee && (
          <div className="text-[11.5px] text-txt3 mt-1.5">La météo n’a pas pu être lue : la troisième étoile est indéterminée.</div>
        )}
        <div className="flex items-center gap-2 mt-3 pt-2.5 border-t border-border text-[12.5px] text-txt">
          <MapPin size={15} className="text-txt3" aria-hidden="true" />{etatPotager}
        </div>
      </div>
      <div className="flex justify-end mt-2.5">
        <Btn kind="soft" icon={CalendarDays} onClick={onOuvrirCalendrier}>Ouvrir la fiche calendrier</Btn>
      </div>
    </section>
  )
}

/** [CA5] La frise conseillée — sa version recalée vit dans la fiche calendrier. */
function SectionCalendrier({ calendriers, culture, dateRef }) {
  const frise = friseDeCulture(calendriers, culture)
  return (
    <section>
      <BlocTitre>Calendrier de la zone</BlocTitre>
      {frise.degrade ? (
        <Absence>Aucune fenêtre connue pour cette zone.</Absence>
      ) : (
        <>
          <MonthStrip pepiniere={frise.pepiniere} pleineTerre={frise.pleineTerre} plantation={frise.plantation}
            rec={frise.rec} moisCourant={moisDeLaDate(dateRef)} legend />
          <div className="text-[11.5px] text-txt3 mt-2">
            Calendrier conseillé. Le calendrier recalé sur tes séries est dans la fiche calendrier.
          </div>
        </>
      )}
    </section>
  )
}

/** [CA6, CA19] Neuf lignes fixes, deux colonnes qui passent à une sous 400px de conteneur. */
function SectionReferentiel({ fiche }) {
  const lignes = lignesReferentiel(fiche)
  return (
    <section>
      <BlocTitre>Référentiel</BlocTitre>
      <div className="grid grid-cols-2 @[400px]/fiche-culture:grid-cols-1 gap-x-3 gap-y-2.5">
        {lignes.map((l) => (
          <div key={l.cle} className="min-w-0">
            <div className="text-[11.5px] text-txt3">{l.libelle}</div>
            <div className={`text-[13px] mt-0.5 ${l.valeur ? 'font-semibold text-txt' : 'font-normal text-txt3'}`}>
              {l.valeur || 'non renseigné'}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

/** [CA7] Une variété seulement en pépinière n'est jamais masquée. */
function SectionVarietes({ fiche }) {
  const varietes = fiche?.varietes_cultivees || []
  return (
    <section>
      <BlocTitre n={varietes.length}>Variétés cultivées</BlocTitre>
      {varietes.length === 0 ? (
        <Absence>Pas au potager en ce moment.</Absence>
      ) : (
        <div className="flex flex-col gap-[7px]">
          {varietes.map((v) => (
            <div key={v.variete} className="border border-border rounded-[12px] px-3 py-2.5">
              <div className="font-serif italic text-[14px] text-txt">{v.nom_variete || v.variete}</div>
              <div className="flex flex-col gap-1.5 mt-1.5">
                {v.parcelles.map((p) => (
                  <div key={p.parcelle_id} className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="text-[12.5px] font-semibold text-brand-text">{p.nom_parcelle || TIRET}</span>
                    <PastillePhase ligne={p} />
                  </div>
                ))}
                {(v.lots_pepiniere || []).map((lot) => (
                  <div key={lot.numero} className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="text-[12.5px] font-semibold text-brand-text">lot #{lot.numero}{lot.emplacement ? ` · ${lot.emplacement}` : ''}</span>
                    {lot.stade && <span className="text-[11.5px] text-txt2">{lot.stade}</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function PastilleVoisinage({ plus, texte, trad = false }) {
  const base = 'inline-flex items-center gap-1 text-[12px] font-semibold rounded-full px-2.5 py-[3px]'
  const cls = trad
    ? `${base} bg-transparent border border-dashed ${plus ? 'border-brand text-brand-text' : 'border-red text-red'}`
    : `${base} ${plus ? 'bg-brand-soft text-brand-text' : 'bg-red-soft text-red'} border border-transparent`
  return <span className={cls}>{plus ? '+' : '−'} {texte}</span>
}

/** [CA22] Quatre groupes : favorables/défavorables établis, puis en pointillé la pratique traditionnelle. */
function SectionVoisinages({ fiche }) {
  const g = groupesVoisinages(fiche?.associations)
  const vide = !fiche?.associations_connues
  return (
    <section>
      <BlocTitre>Voisinages</BlocTitre>
      {vide ? (
        <Absence>Aucun voisinage connu pour cette culture. Ce n’est pas une absence de conflit.</Absence>
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5">
            {g.favorablesEtablis.map((a) => <PastilleVoisinage key={a.autre_partie} plus texte={a.autre_partie} />)}
            {g.defavorablesEtablis.map((a) => <PastilleVoisinage key={a.autre_partie} texte={a.autre_partie} />)}
          </div>
          {(g.favorablesTrad.length + g.defavorablesTrad.length) > 0 && (
            <>
              <div className="text-[11.5px] text-txt3 mt-2.5 mb-1.5">Selon la pratique traditionnelle, sans preuve établie</div>
              <div className="flex flex-wrap gap-1.5">
                {g.favorablesTrad.map((a) => <PastilleVoisinage key={a.autre_partie} plus trad texte={a.autre_partie} />)}
                {g.defavorablesTrad.map((a) => <PastilleVoisinage key={a.autre_partie} trad texte={a.autre_partie} />)}
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}

/** [CA23] Cinq bioagresseurs visibles, « + N autres » déplie le reste, sans lecture de plus. */
function SectionBioagresseurs({ fiche }) {
  const [tout, setTout] = useState(false)
  const bio = fiche?.bioagresseurs || []
  const visibles = tout ? bio : bio.slice(0, 5)
  return (
    <section>
      <BlocTitre n={fiche?.bioagresseurs_total ?? bio.length}>Bioagresseurs</BlocTitre>
      {!fiche?.bioagresseurs_connus ? (
        <Absence>Je n’ai pas l’information pour cette culture. Ce n’est pas une absence de risque.</Absence>
      ) : (
        <div className="flex flex-col gap-1.5">
          {visibles.map((b) => (
            <div key={b.nom_scientifique || b.nom_commun_fr} className="bg-card-alt rounded-[11px] px-3 py-2.5">
              <div className="flex items-center gap-2 flex-wrap">
                <strong className="text-[13px] text-txt">{b.nom_commun_fr}</strong>
                <span className="text-[11.5px] text-txt3">{b.categorie}</span>
                {b.periode_risque && (
                  <span className="ml-auto text-[11.5px] font-semibold text-txt2 bg-card border border-border rounded-full px-2.5 py-0.5 whitespace-nowrap">
                    risque : {b.periode_risque}
                  </span>
                )}
              </div>
              {b.description_symptome && <div className="text-[12px] text-txt2 mt-1 leading-[1.45]">{b.description_symptome}</div>}
            </div>
          ))}
          {bio.length > 5 && !tout && (
            <button onClick={() => setTout(true)} className="self-start inline-flex items-center gap-1 text-[12.5px] font-semibold text-brand-text mt-0.5">
              + {bio.length - 5} autres<ChevronDown size={14} strokeWidth={2} aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </section>
  )
}
