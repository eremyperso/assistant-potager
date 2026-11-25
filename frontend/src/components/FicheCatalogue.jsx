import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { peutEnregistrer } from '../lib/gestes.js'
import { ouvrirGastonSur } from '../lib/contexteCompagnon.js'
import { sujetCatalogue } from '../lib/ouvertureGaston.js'  // [US-358]
import { avecArticle } from '../lib/pepiniereSocle.js'
import { etatDeCatalogue, phraseAjouter } from '../lib/ficheCommune.js'
import { espacementDe } from '../lib/ficheCommune.js'
import { moisDeFrise } from '../lib/calendrierAnnee.js'
import { CalendrierAnnee, LegendeCommune } from './ui'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'

/**
 * [US-355 / CA7] La fiche d'une espèce du catalogue : la pilule « Pas encore au potager » ou « Au potager », la fenêtre, le
 * bouton **Ajouter à mon potager** (ou « Ouvrir la culture en place », qui bascule sur la fiche commune), puis le
 * calendrier, les variétés du catalogue, l'espacement et la famille.
 *
 * **Ajouter n'écrit rien** : il ouvre Gaston avec la demande pré-écrite (US-358) ; Gaston répond, puis propose à confirmer.
 * `ligne` : une espèce de `lignesCatalogue` (lib/culturesSocle.js). `onOuvrirEnPlace` : ouvre la fiche commune de la
 * culture déjà au potager.
 */
export default function FicheCatalogue({ ligne, onOuvrirEnPlace = null }) {
  const { dateRef } = useDateRef()
  const { potagerId, potagerActif } = usePotager()
  const [espacement, setEspacement] = useState(undefined)   // undefined : en lecture ; null : non renseigné
  const etat = etatDeCatalogue({ au_potager: ligne.auPotager })

  useEffect(() => {
    let annule = false
    api.ficheCulture(ligne.culture, potagerId, dateRef)
      .then((f) => { if (!annule) setEspacement(espacementDe(f)) })
      .catch(() => { if (!annule) setEspacement(null) })
    return () => { annule = true }
  }, [ligne.culture, potagerId, dateRef])

  const ecrire = peutEnregistrer(potagerActif?.role)
  // [US-358 / CA2] La phrase est pré-écrite dans le champ : le jardinier l'envoie lui-même.
  const ajouter = () => ouvrirGastonSur({ sujet: sujetCatalogue(ligne), champ: phraseAjouter(ligne.nom, avecArticle(ligne.culture)) })
  const fenetre = ligne.auPotager
    ? `Au potager${ligne.lieux.length ? ` · ${ligne.lieux.join(', ')}` : ''}`
    : (ligne.fenetre?.texte || 'Aucune fenêtre connue pour votre zone')
  const varietes = ligne.brut?.varietes || []

  return (
    <article aria-label={`Catalogue : ${ligne.nom}`} className="p-4 pb-6 text-txt">
      <div className="flex items-start gap-3 pr-11">
        <span aria-hidden="true" className="grid h-[52px] w-[52px] shrink-0 place-items-center rounded-[14px] bg-card-alt text-[28px]">{ligne.emoji}</span>
        <div className="min-w-0 flex-1">
          <h2 className="font-serif text-[21px] font-semibold leading-tight">{ligne.nom}</h2>
          <p className="mt-0.5 text-[12.5px] text-txt2">{ligne.sousTitre}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px] text-txt2">
        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${etat.dans ? 'bg-brand-soft text-brand-deep' : 'bg-card-alt text-txt2'}`}>
          {etat.pilule}
        </span>
        <span className={ligne.fenetre?.gras ? 'font-bold text-txt' : ''}>{fenetre}</span>
      </div>

      <div className="mt-3">
        {etat.dans ? (
          onOuvrirEnPlace && (
            <button
              type="button" onClick={onOuvrirEnPlace}
              className={`inline-flex min-h-[44px] w-full items-center justify-center rounded-[10px] border border-border bg-card px-4 text-[13.5px] font-semibold text-txt ${FOCUS}`}
            >
              {etat.bouton}
            </button>
          )
        ) : ecrire && (
          <button
            type="button" onClick={ajouter}
            className={`inline-flex min-h-[44px] w-full items-center justify-center gap-1.5 rounded-[10px] bg-brand px-4 text-[13.5px] font-semibold text-white hover:opacity-95 ${FOCUS}`}
          >
            <Plus size={16} aria-hidden="true" />{etat.bouton}
          </button>
        )}
      </div>

      <dl className="mt-5 flex flex-col gap-4 text-[13px]">
        <div>
          <dt className="text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">Calendrier</dt>
          <dd className="mt-1.5">
            {ligne.brut?.a_calendrier ? (
              <>
                <CalendrierAnnee mois={moisDeFrise(ligne.frise)} frise={ligne.frise} moisCourant={new Date().getMonth()} initiales />
                <LegendeCommune sujet="un mois" calendrier className="mt-2" />
              </>
            ) : <span className="text-txt3">Aucun calendrier connu pour votre zone.</span>}
          </dd>
        </div>
        <div>
          <dt className="text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">Variétés du catalogue</dt>
          <dd className="mt-1">{varietes.length ? varietes.join(', ') : <span className="text-txt3">non renseignées</span>}</dd>
        </div>
        {espacement !== undefined && (
          <div>
            <dt className="text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">Espacement</dt>
            <dd className={`mt-1 ${espacement ? '' : 'text-txt3'}`}>{espacement || 'non renseigné'}</dd>
          </div>
        )}
        <div>
          <dt className="text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">Famille</dt>
          <dd className="mt-1">
            {ligne.famille || <span className="text-txt3">non renseignée</span>}
            {ligne.famille && !ligne.auPotager && ' · Gaston choisira une parcelle qui respecte la rotation'}
          </dd>
        </div>
      </dl>
    </article>
  )
}
