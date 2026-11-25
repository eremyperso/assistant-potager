// [US-218, US-356] L'onglet « Parcours » — où en sont mes plants.
//
// Version 2 de la maquette « Socle commun » (§2, décision D8). Sur ordinateur, une MATRICE
// emplacement × stade : en lignes la serre chaude, le châssis froid (teintés par leur type) et « Sans
// emplacement » (hachuré, « à ranger ») ; en colonnes En levée, En godet, Endurcissement, Prêt à
// sortir, chacune titrée par sa pastille et son compte. Sur mobile, UN STADE À LA FOIS (défilement
// horizontal aimanté, points qui suivent), les lots groupés par emplacement dans la colonne.
//
// La carte d'un lot (`CarteLot`) montre ce qui compte ; les gestes (repiquer, mettre en terre,
// clôturer, ranger…) vivent dans la fiche du lot, qu'elle ouvre. Rien n'est calculé ici : tout vient du
// bloc `parcours` de `GET /pepiniere/lots`, mis en forme par `lib/parcours.js` et `lib/pepiniereSocle.js`.
// Le dessin se met en page par la structure de page (`bureau`, US-353 / D7) ; chaque carte, par son
// conteneur.
import { Sprout, X } from 'lucide-react'
import CarteLot from './CarteLot.jsx'
import PagerAimante from './PagerAimante.jsx'
import { PastilleEtape } from './ui/EtapeCulture.jsx'
import { kanban, pepiniereChoisie, caseVide, ongletStadeParDefaut, superficieEnClair } from '../lib/parcours.js'
import {
  colonnesParStade, carteLot, enteteGroupe, etapeDuStadePepiniere,
} from '../lib/pepiniereSocle.js'

const FOND_LIGNE = { chaude: 'fond-chaude', froide: 'fond-froide' }
const fondLigne = (ligne) => (ligne.sansEmplacement ? 'trame-sans-emplacement' : FOND_LIGNE[ligne.type_pepiniere] ?? 'trame-sans-emplacement')

/** La pastille d'un stade, avec son libellé et son compte (« En godet · 4 »). */
function TeteDeColonne({ colonne }) {
  return (
    <span className="flex items-center gap-2 text-[12.5px] font-bold text-txt">
      <PastilleEtape etape={etapeDuStadePepiniere(colonne.cle)} petite />
      {colonne.libelle} · {colonne.total}
    </span>
  )
}

export default function OngletParcours({
  data, etat, setEtat, bureau, alertes, lotSelectionne, onOuvrirLot,
}) {
  const parcours = data?.parcours ?? {}
  const lotsParId = new Map((data?.lots ?? []).map((l) => [l.lot_id, l]))
  const k = kanban(parcours, { filtre: etat.filtre })
  const colonnes = colonnesParStade(k)
  const choisie = pepiniereChoisie(parcours, etat.filtre)
  const aucunLot = !(parcours.etiquettes ?? []).length

  const carteDe = (e) => {
    const lot = lotsParId.get(e.lot.id)
    return (
      <CarteLot
        key={e.id}
        carte={carteLot({ lot, etiquette: e, alerte: alertes.get(e.lot.id) })}
        choisie={lotSelectionne === e.lot.id}
        onOuvrir={() => lot && onOuvrirLot(lot, e)}
      />
    )
  }

  if (aucunLot) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-txt3">
        <Sprout size={32} aria-hidden="true" />
        <p className="text-[15px]">Aucun lot en cours</p>
      </div>
    )
  }

  const filtre = choisie && (
    <button
      type="button" onClick={() => setEtat({ filtre: null })}
      className="inline-flex min-h-[34px] items-center gap-1.5 self-start rounded-full bg-brand-soft px-3 text-[12.5px] font-semibold text-brand-text"
    >
      {choisie.nom} <X size={13} aria-hidden="true" /><span className="sr-only">— retirer le filtre de pépinière</span>
    </button>
  )

  // ── Mobile : un stade à la fois ──────────────────────────────────────────────────────────────
  if (!bureau) {
    const actif = etat.stade && colonnes.some((c) => c.cle === etat.stade) ? etat.stade : ongletStadeParDefaut(colonnes)
    return (
      <div className="@container/parcours flex flex-col gap-3">
        {filtre}
        <PagerAimante
          etiquette="Stades" actif={actif} onChange={(cle) => setEtat({ stade: cle })}
          pages={colonnes.map((c) => ({
            cle: c.cle,
            libelle: `${c.libelle} · ${c.total}`,
            contenu: (
              <div className="flex flex-col gap-2 pb-2">
                <h3 className="sr-only">{c.libelle} · {c.total}</h3>
                {c.groupes.length === 0 && (
                  <p className="rounded-[13px] border-[1.5px] border-dashed border-border bg-surface px-3 py-2.5 text-[12.5px] text-txt2">
                    {caseVide(c.cle, k.lignes[0])}
                  </p>
                )}
                {c.groupes.map(({ ligne, etiquettes }) => {
                  const tete = enteteGroupe(ligne, etiquettes.length)
                  return (
                    <section key={ligne.cle} aria-label={tete.texte} className="flex flex-col gap-2">
                      <div className="flex items-center gap-1.5 pt-1 text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2">
                        <i aria-hidden="true" className="block h-2.5 w-2.5 rounded-[3px]" style={{ background: tete.couleur }} />
                        {tete.texte}
                      </div>
                      {etiquettes.map(carteDe)}
                    </section>
                  )
                })}
              </div>
            ),
          }))}
        />
      </div>
    )
  }

  // ── Ordinateur : la matrice emplacement × stade ───────────────────────────────────────────────
  return (
    <section className="@container/parcours flex flex-col gap-3" aria-labelledby="titre-parcours">
      <h2 id="titre-parcours" className="text-[13px] font-bold text-txt2">Le parcours du plant · emplacement × stade</h2>
      {filtre}
      <div role="table" aria-label="Les lots par emplacement et par stade" className="grid grid-cols-[150px_repeat(4,minmax(0,1fr))] overflow-hidden rounded-[18px] border border-border bg-card shadow-card">
        <div role="columnheader" className="border-b border-border px-3.5 py-3 text-[12.5px] font-bold text-txt">Emplacement</div>
        {colonnes.map((c) => (
          <div key={c.cle} role="columnheader" className="border-b border-l border-border-soft px-3.5 py-3"><TeteDeColonne colonne={c} /></div>
        ))}
        {k.lignes.map((ligne) => {
          const tete = enteteGroupe(ligne, 0)
          return (
            <div key={ligne.cle} role="row" className="contents">
              <div role="rowheader" className={`border-t border-border px-3.5 py-3 ${fondLigne(ligne)}`}>
                <b className="block text-[13px] text-txt">{ligne.sansEmplacement ? 'Sans emplacement' : ligne.nom}</b>
                <small className="block text-[11.5px] text-txt2">{tete.sousTitre}</small>
                {!ligne.sansEmplacement && superficieEnClair(ligne.superficie_m2) && (
                  <small className="block text-[11.5px] text-txt3">{superficieEnClair(ligne.superficie_m2)}</small>
                )}
              </div>
              {colonnes.map((c) => {
                const siennes = c.groupes.find((g) => g.ligne.cle === ligne.cle)?.etiquettes ?? []
                return (
                  <div key={c.cle} role="cell" className={`flex flex-col gap-2 border-l border-t border-border-soft p-2.5 ${fondLigne(ligne)}`}>
                    {siennes.length
                      ? siennes.map(carteDe)
                      : <p className="px-1 py-1 text-[12px] italic text-txt3">{caseVide(c.cle, ligne)}</p>}
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
    </section>
  )
}
