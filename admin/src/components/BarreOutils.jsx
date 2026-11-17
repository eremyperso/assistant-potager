import { useState } from 'react'
import { RefreshCw, SlidersHorizontal } from 'lucide-react'
import { PERIODES, bornes } from '../lib/periode.js'
import { jourIso } from '../lib/format.js'
import { CANAUX, CHOIX_PROVENANCE, choixDeProvenance, nombreFiltresActifs, provenanceDuChoix } from '../lib/filtres.js'

const SELECT = 'min-h-[34px] rounded-[9px] border border-border bg-card pl-2.5 pr-7 text-[13px] font-semibold text-txt'

/** Les trois sélecteurs de filtre (provenance, canal, modèle) [US-311 / CA4]. Un seul composant,
 *  deux présentations : en ligne dans la barre (≥ 900 px) ou dans le panneau replié (téléphone). */
function Selecteurs({ filtres, modeles, surChangement, empile }) {
  const choix = choixDeProvenance(filtres.provenance)
  const style = empile
    ? 'flex items-center justify-between gap-2.5 text-[13px] font-semibold text-txt'
    : 'flex flex-col gap-0.5 text-[11px] font-semibold text-txt2'
  const select = empile ? 'min-h-[40px] min-w-[170px] rounded-[9px] border border-border bg-card px-2.5 text-txt' : SELECT
  return (
    <>
      <label className={style}>Provenance
        <select value={choix} onChange={(e) => surChangement({ ...filtres, provenance: provenanceDuChoix(e.target.value) })} className={select}>
          {choix === 'autre' ? <option value="autre">sélection personnalisée</option> : null}
          {CHOIX_PROVENANCE.map((c) => <option key={c.id} value={c.id}>{c.libelle}</option>)}
        </select>
      </label>
      <label className={style}>Canal
        <select value={filtres.canal} onChange={(e) => surChangement({ ...filtres, canal: e.target.value })} className={select}>
          <option value="">tous</option>
          {CANAUX.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
      <label className={style}>Modèle
        <select value={filtres.modele} onChange={(e) => surChangement({ ...filtres, modele: e.target.value })} className={`${select} max-w-[16rem]`}>
          <option value="">tous</option>
          {filtres.modele && !modeles.includes(filtres.modele) ? <option value={filtres.modele}>{filtres.modele}</option> : null}
          {modeles.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </label>
    </>
  )
}

/**
 * Barre d'outils de la coquille [US-311 / CA4, CA5], sous le bandeau : période, filtres partagés par
 * toutes les vues, heure de dernière mise à jour et rafraîchissement. Les filtres sont en ligne à
 * partir de 900 px ; en dessous, repliés derrière « Filtres » avec le nombre de filtres actifs.
 */
export default function BarreOutils({ filtres, modeles, surFiltres, majTexte, enPanne, surRafraichir }) {
  const [ouvert, setOuvert] = useState(false)
  const actifs = nombreFiltresActifs(filtres)
  const aujourdhui = jourIso(new Date())

  function choisirPeriode(id) {
    if (id !== 'perso') { surFiltres({ ...filtres, periode: id, depuis: '', jusqu_a: '' }); return }
    const { depuis, jusqu_a } = bornes({ periode: '7j' })
    surFiltres({ ...filtres, periode: 'perso', depuis: filtres.depuis || depuis, jusqu_a: filtres.jusqu_a || jusqu_a })
  }

  function dates(champ, valeur) {
    if (!valeur) return
    const suite = { ...filtres, [champ]: valeur }
    // Deux bornes à l'envers donneraient une période vide : la seconde entraîne la première.
    if (suite.depuis > suite.jusqu_a) suite[champ === 'depuis' ? 'jusqu_a' : 'depuis'] = valeur
    surFiltres(suite)
  }

  return (
    <div className="flex flex-wrap items-center gap-2.5 border-b border-border bg-surface px-4 py-2.5 nav:px-6">
      <div role="group" aria-label="Période" className="flex max-w-full gap-[3px] overflow-x-auto rounded-[10px] bg-card-alt p-[3px]">
        {PERIODES.map((p) => (
          <button key={p.id} type="button" aria-pressed={filtres.periode === p.id} onClick={() => choisirPeriode(p.id)}
            className={`min-h-[34px] whitespace-nowrap rounded-lg px-[11px] py-[7px] text-[12.5px] font-semibold ${filtres.periode === p.id
              ? 'bg-card text-txt shadow-[0_1px_3px_rgba(0,0,0,.12)]' : 'text-txt2'}`}>
            {p.libelle}
          </button>
        ))}
      </div>

      <button type="button" aria-expanded={ouvert} aria-controls="panneau-filtres" onClick={() => setOuvert((o) => !o)}
        className="flex min-h-[38px] items-center gap-[7px] rounded-[10px] border border-border bg-card px-3 text-[13px] font-semibold nav:hidden">
        <SlidersHorizontal size={16} className="text-txt2" aria-hidden="true" />
        Filtres
        {actifs ? (
          <span aria-label={`${actifs} filtre${actifs > 1 ? 's' : ''} actif${actifs > 1 ? 's' : ''}`}
            className="grid h-5 min-w-[20px] place-items-center rounded-full bg-brand px-[5px] text-[11px] font-extrabold text-surface">{actifs}</span>
        ) : null}
      </button>

      <div className="hidden items-center gap-2 nav:flex"><Selecteurs filtres={filtres} modeles={modeles} surChangement={surFiltres} /></div>

      <span className="ml-auto flex items-center gap-1.5 text-xs text-txt2">
        <span role="status">{enPanne ? <b className="text-amber">{majTexte}</b> : majTexte}</span>
        <button type="button" onClick={surRafraichir} aria-label="Rafraîchir"
          className="grid h-[34px] w-[34px] place-items-center rounded-[10px] border border-border bg-card text-txt2">
          <RefreshCw size={17} aria-hidden="true" />
        </button>
      </span>

      {filtres.periode === 'perso' ? (
        <div className="flex w-full flex-wrap items-center gap-2 text-[13px] text-txt2">
          <label className="flex items-center gap-1.5">Du
            <input type="date" value={filtres.depuis} max={aujourdhui} onChange={(e) => dates('depuis', e.target.value)}
              className="min-h-[34px] rounded-[9px] border border-border bg-card px-2 text-txt" />
          </label>
          <label className="flex items-center gap-1.5">au
            <input type="date" value={filtres.jusqu_a} max={aujourdhui} onChange={(e) => dates('jusqu_a', e.target.value)}
              className="min-h-[34px] rounded-[9px] border border-border bg-card px-2 text-txt" />
          </label>
        </div>
      ) : null}

      {ouvert ? (
        <div id="panneau-filtres" className="grid w-full gap-2 pt-1 nav:hidden">
          <Selecteurs filtres={filtres} modeles={modeles} surChangement={surFiltres} empile />
        </div>
      ) : null}
    </div>
  )
}
