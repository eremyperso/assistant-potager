// [US-334 / M4, CA4] L'assistant de la première ouverture de l'éditeur du plan.
//
// Quatre étapes enchaînées — emprise, nord, fond, pose — dont chacune peut être passée. Il ne fait que
// poser l'état de l'éditeur (`lib/editeurPlan.js`) : rien n'est écrit avant « Enregistrer » (E5).
import { useState } from 'react'
import { Check } from 'lucide-react'
import { Btn } from './ui'
import {
  definirEmprise, orienter, poser, aPlacer, empriseDe, texteMetres, DIRECTIONS,
} from '../lib/editeurPlan.js'
import { ETAPES, empriseProposee, texteProposition, dispositionEnRangees, DUREE_MISE_EN_PLACE } from '../lib/miseEnPlace.js'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'
const CLASSE_SAISIE = `min-h-[36px] w-24 rounded-lg border border-border bg-card px-2.5 text-[13px] text-txt ${FOCUS}`

const valeurSaisie = (t) => {
  const v = parseFloat(String(t).replace(',', '.'))
  return Number.isFinite(v) ? v : null
}

export default function AssistantMiseEnPlace({ etat, appliquer, plan, emprise, annoncer = () => {}, onTerminer }) {
  const [etape, setEtape] = useState(0)
  const proposition = empriseProposee(plan)
  const depart = empriseDe(etat, proposition || { longueur: emprise?.longueur || 20, largeur: emprise?.largeur || 12 })
  const [saisie, setSaisie] = useState({ longueur: String(depart.longueur), largeur: String(depart.largeur) })
  const courante = ETAPES[etape]
  const derniere = etape === ETAPES.length - 1
  const libres = aPlacer(etat)

  const suivante = () => {
    if (derniere) { onTerminer?.(); return }
    setEtape(etape + 1)
    annoncer(`Étape ${etape + 2} sur ${ETAPES.length} : ${ETAPES[etape + 1].titre}`)
  }
  const validerEmprise = () => {
    const L = valeurSaisie(saisie.longueur)
    const l = valeurSaisie(saisie.largeur)
    if (L && l) appliquer((s) => definirEmprise(s, { longueur: L, largeur: l }))
    suivante()
  }
  const toutPoser = () => {
    const base = empriseDe(etat, depart)
    const places = dispositionEnRangees(libres, base)
    appliquer((s) => places.reduce((acc, p) => poser(acc, p.id, p.x, p.y), s))
    annoncer(`${places.length} parcelle${places.length > 1 ? 's posées' : ' posée'} sur le plan : ajustez-les, puis enregistrez.`)
  }
  const emprisePosee = etat.potager.emprise?.longueur && etat.potager.emprise?.largeur

  return (
    <section aria-label="Mise en place du plan" data-assistant-mise-en-place
      className="flex flex-col gap-3 rounded-xl border border-brand bg-brand-soft/40 px-4 py-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[11.5px] font-bold uppercase tracking-[.05em] text-brand-text">
            Mettre en place le plan · {DUREE_MISE_EN_PLACE}
          </p>
          <h3 className="font-serif text-[16px] font-semibold text-txt">
            Étape {etape + 1} sur {ETAPES.length} · {courante.titre}
          </h3>
        </div>
        <ol aria-label="Étapes" className="flex items-center gap-1.5">
          {ETAPES.map((e, i) => (
            <li key={e.id} aria-current={i === etape ? 'step' : undefined}
              className={`inline-flex min-h-[26px] items-center gap-1 rounded-full px-2.5 text-[11.5px] font-semibold
                ${i === etape ? 'bg-brand text-white' : i < etape ? 'bg-card text-brand-text' : 'bg-card text-txt3'}`}>
              {i < etape && <Check size={12} aria-hidden="true" />}{e.libelle}
            </li>
          ))}
        </ol>
      </header>

      <p className="text-[12.5px] text-txt2">{courante.aide}</p>

      {courante.id === 'emprise' && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-[12px] font-semibold text-txt2" htmlFor="mep-longueur">
              Longueur (m)
              <input id="mep-longueur" type="number" min="1" step="0.5" className={CLASSE_SAISIE} value={saisie.longueur}
                onChange={(e) => setSaisie({ ...saisie, longueur: e.target.value })} />
            </label>
            <span aria-hidden="true" className="pb-2 text-txt3">×</span>
            <label className="flex flex-col gap-1 text-[12px] font-semibold text-txt2" htmlFor="mep-largeur">
              Largeur (m)
              <input id="mep-largeur" type="number" min="1" step="0.5" className={CLASSE_SAISIE} value={saisie.largeur}
                onChange={(e) => setSaisie({ ...saisie, largeur: e.target.value })} />
            </label>
          </div>
          {proposition && !emprisePosee && <p className="text-[12px] text-txt3">{texteProposition(plan, proposition)}</p>}
        </div>
      )}

      {courante.id === 'nord' && (
        <div role="group" aria-label="Direction du nord" className="grid max-w-[360px] grid-cols-4 gap-1">
          {DIRECTIONS.map((d) => (
            <button key={d.id} type="button" aria-pressed={etat.potager.nord === d.id} title={`Nord ${d.nord}`}
              onClick={() => appliquer((s) => orienter(s, d.id))}
              className={`min-h-[34px] rounded-md border text-[12px] font-semibold ${FOCUS}
                ${etat.potager.nord === d.id ? 'border-brand bg-brand-soft text-brand-text' : 'border-border bg-card text-txt2 hover:text-txt'}`}>
              {d.libelle}
            </button>
          ))}
        </div>
      )}

      {courante.id === 'fond' && (
        <p className="w-fit rounded-lg border border-dashed border-border bg-card px-2.5 py-2 text-[12.5px] text-txt2">Sans fond</p>
      )}

      {courante.id === 'pose' && (
        <div className="flex flex-wrap items-center gap-3">
          <Btn small disabled={!libres.length} onClick={toutPoser}>
            {libres.length ? `Poser les ${libres.length} parcelle${libres.length > 1 ? 's' : ''} d’un coup` : 'Toutes les parcelles sont posées'}
          </Btn>
          <span className="text-[12px] text-txt3">
            {libres.length ? 'Elles se rangent dans l’ordre du chemin ; déplacez-les ensuite à la souris.' : `Plan de ${texteMetres(etat.potager.emprise?.longueur || depart.longueur)} × ${texteMetres(etat.potager.emprise?.largeur || depart.largeur)} m prêt : enregistrez-le.`}
          </span>
        </div>
      )}

      <footer className="flex flex-wrap items-center gap-2">
        {etape > 0 && <Btn small onClick={() => setEtape(etape - 1)}>Précédent</Btn>}
        {!derniere && (
          <button type="button" onClick={suivante} className={`rounded-md px-2 py-1 text-[12.5px] font-semibold text-txt2 hover:text-txt ${FOCUS}`}>
            Passer
          </button>
        )}
        <Btn small kind="primary" className="ml-auto" onClick={courante.id === 'emprise' ? validerEmprise : suivante}>
          {derniere ? 'Terminer' : 'Continuer'}
        </Btn>
      </footer>
    </section>
  )
}
