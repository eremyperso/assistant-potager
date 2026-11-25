import { useEffect, useState } from 'react'
import { AlertTriangle, BookOpen } from 'lucide-react'
import { api } from '../lib/api.js'
import { InfoBanner, Btn } from './ui'
import FicheCalendrier from './FicheCalendrier.jsx'
import {
  BlocTitre, NonLue, SectionMaintenant, SectionCalendrier, SectionReferentiel, SectionVarietes,
  SectionVoisinages, SectionBioagresseurs,
} from './FicheCulture.jsx'
import { espacementDe, rotationDe, MESSAGE_LECTURE_INCOMPLETE } from '../lib/ficheCommune.js'
import { sourcesDeFiche } from '../lib/ficheCulture.js'

/**
 * [US-355 / CA3] L'onglet Référence de la fiche commune : le calendrier de l'espèce, l'espacement, la rotation,
 * puis les sections de la fiche culture (US-207) — Maintenant, Référentiel, Variétés cultivées, Voisinages,
 * Bioagresseurs — sans perte de ses critères. Une section non lue le dit à SA place (US-207 / CA12) ; « Ouvrir la
 * fiche calendrier » empile toujours `FicheCalendrier` (US-183).
 *
 * Trois lectures au plus, en parallèle, UNE fois à l'ouverture de l'onglet : la composition de la fiche, le
 * calendrier de zone et la confiance. Aucune règle n'est recalculée ici.
 */
export default function ReferenceCulture({ culture, dateRef, potagerId, parcelleId = null, onOuvrirLot = null, ecran = null }) {
  const [fiche, setFiche] = useState(null)
  const [ficheEchouee, setFicheEchouee] = useState(false)
  const [calendriers, setCalendriers] = useState(null)
  const [confiances, setConfiances] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [essai, setEssai] = useState(0)
  const [calendrierOuvert, setCalendrierOuvert] = useState(false)

  useEffect(() => {
    let annule = false
    setChargement(true)
    Promise.allSettled([
      api.ficheCulture(culture, potagerId, dateRef),
      api.calendriersPlan([culture], potagerId, dateRef),
      api.confiancesPlan([culture], potagerId, dateRef),
    ]).then(([f, cal, conf]) => {
      if (annule) return
      setFiche(f.status === 'fulfilled' ? f.value : null)
      setFicheEchouee(f.status === 'rejected')
      setCalendriers(cal.status === 'fulfilled' ? cal.value : null)
      setConfiances(conf.status === 'fulfilled' ? conf.value : null)
      if (f.status === 'rejected') console.warn('[US-355] Fiche culture indisponible', f.reason)
      setChargement(false)
    })
    return () => { annule = true }
  }, [essai, culture, dateRef, potagerId])

  if (chargement) {
    return (
      <div role="status" className="flex animate-pulse flex-col gap-3" aria-label="Chargement de la référence">
        <div className="h-3 w-32 rounded bg-card-alt" />
        <div className="h-16 rounded-[14px] bg-card-alt" />
        <div className="h-10 rounded-[11px] bg-card-alt" />
        <div className="h-3 w-40 rounded bg-card-alt" />
      </div>
    )
  }

  const entree = confiances?.cultures?.[culture] ?? null
  const confianceLue = confiances !== null && confiances !== undefined
  const espacement = espacementDe(fiche)
  const rotation = rotationDe(fiche)

  return (
    <div className="flex flex-col gap-[22px]" data-onglet-reference="">
      {ficheEchouee && (
        <InfoBanner
          tint="amber" icon={AlertTriangle} dismissible={false}
          title="Lecture incomplète" body={MESSAGE_LECTURE_INCOMPLETE}
          action={<Btn small onClick={() => setEssai((n) => n + 1)}>Réessayer</Btn>}
        />
      )}
      {fiche?.fiche_absente && (
        <InfoBanner
          tint="blue" icon={BookOpen} dismissible={false}
          title="Fiche absente du référentiel"
          body={`${culture} n’est pas connue du référentiel : ni calendrier, ni caractéristiques, ni voisinages. Ce que tu cultives reste listé ci-dessous.`}
        />
      )}

      {!fiche?.fiche_absente && (
        <>
          <div>
            <SectionCalendrier calendriers={calendriers} culture={culture} dateRef={dateRef} titre="Calendrier de l’espèce" />
            <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3.5 gap-y-1.5 text-[13px]">
              <dt className="text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2">Espacement</dt>
              <dd className={espacement ? 'text-txt' : 'text-txt3'}>{ficheEchouee ? 'non lu' : (espacement || 'non renseigné')}</dd>
              <dt className="text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2">Rotation</dt>
              <dd className={rotation ? 'text-txt' : 'text-txt3'}>{ficheEchouee ? 'non lue' : (rotation || 'non renseignée')}</dd>
            </dl>
          </div>

          <SectionMaintenant
            entree={entree} calendriers={calendriers} culture={culture} confianceLue={confianceLue}
            varietesCultivees={fiche?.varietes_cultivees} onOuvrirCalendrier={() => setCalendrierOuvert(true)}
          />
        </>
      )}

      {ficheEchouee ? (
        <>
          <section><BlocTitre>Référentiel</BlocTitre><NonLue /></section>
          <section><BlocTitre>Variétés cultivées</BlocTitre><NonLue /></section>
          <section><BlocTitre>Voisinages</BlocTitre><NonLue /></section>
          <section><BlocTitre>Bioagresseurs</BlocTitre><NonLue /></section>
        </>
      ) : fiche?.fiche_absente ? (
        <SectionVarietes fiche={fiche} onOuvrirLot={onOuvrirLot} />
      ) : (
        <>
          <SectionReferentiel fiche={fiche} />
          <SectionVarietes fiche={fiche} onOuvrirLot={onOuvrirLot} />
          <SectionVoisinages fiche={fiche} />
          <SectionBioagresseurs fiche={fiche} />
        </>
      )}

      {sourcesDeFiche(fiche) && <p className="text-[11.5px] leading-snug text-txt3">{sourcesDeFiche(fiche)}</p>}

      {calendrierOuvert && (
        <FicheCalendrier
          culture={culture} dateRef={dateRef} potagerId={potagerId} parcelleId={parcelleId}
          calendriers={calendriers} confiances={confiances}
          ecran={ecran} onEnregistrer={() => setCalendrierOuvert(false)} onClose={() => setCalendrierOuvert(false)}
        />
      )}
    </div>
  )
}
