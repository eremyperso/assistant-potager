// [US-242, US-356] L'onglet « Lots » — le registre de la saison, lot par lot.
//
// Version 3 de la maquette « Socle commun » : MÊME FORME QUE LE PARCOURS. Sous le bilan de la saison en
// une phrase (« 18 lots cette saison · 14 en cours dont 2 à régler · 4 terminés, 34 plants sortis vers
// le potager »), un tableau dont les colonnes sont l'état du lot — En cours, À régler, Terminés ; plus de
// colonne « Tous », elle doublait les trois autres — et les lignes le mois de semis, chacune avec sa
// teinte (un filet à gauche et un fond léger), « vide » dans les cases sans lot. Les cartes sont CELLES
// DU PARCOURS (`CarteLot`) : emoji, nom, icône du lot et n°, variété · quantité · date, frise des gestes
// datés, alerte. Sur mobile, un état à la fois (défilement aimanté, points qui suivent), les lots
// groupés par mois de semis dans la colonne.
//
// C'est un registre SANS geste : on agit depuis le Parcours ou par Noter. Toucher une carte ouvre la
// fiche du lot (panneau droit sur ordinateur, feuille sur mobile). Les règles — état, alertes, rangées,
// cartes — vivent dans `lib/pepiniereSocle.js` ; ce composant ne fait que les dessiner.
import { useEffect } from 'react'
import CarteLot from './CarteLot.jsx'
import PagerAimante from './PagerAimante.jsx'
import IconeLot from './ui/IconeLot.jsx'
import {
  bilanRegistre, matriceRegistre, carteLotDuRegistre, colonneRegistreInitiale,
} from '../lib/pepiniereSocle.js'

/** Le fond léger d'une rangée : sa teinte, qui s'estompe vers la droite. */
const teinte = (c) => ({ background: `linear-gradient(90deg, ${c}1F, ${c}08 60%, transparent)` })

const Pastille = ({ couleur }) => <i aria-hidden="true" className="block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: couleur }} />

export default function OngletLots({ data, etat, setEtat, bureau, alertes, lotOuvert, onOuvrirLot, aujourdhui }) {
  // [US-358] Arrivé par « Voir dans Lots » depuis la fiche d'un lot : le registre reste entier et le lot ouvert est
  // amené en vue (plutôt que filtré, ce qui ne laissait plus rien à faire défiler).
  useEffect(() => {
    if (lotOuvert == null) return
    document.querySelector('[data-lot-choisi]')?.scrollIntoView?.({ block: 'center' })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const tous = data?.lots ?? []
  const parcours = data?.parcours ?? {}
  const bilan = bilanRegistre(tous, alertes)
  const q = etat.q ?? ''
  const matrice = matriceRegistre(tous, alertes, aujourdhui, { q })

  if (!tous.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-txt3">
        <IconeLot size={32} className="!text-txt3" />
        <p className="text-[15px]">Aucun lot de semis pour l’instant.</p>
      </div>
    )
  }

  const bilanTexte = (
    <p className="text-[13px] text-txt2" data-bilan-registre="">
      <b className="text-txt">{bilan.tous} lot{bilan.tous > 1 ? 's' : ''}</b> cette saison · <b className="text-txt">{bilan.enCours}</b> en cours
      {bilan.a_regler > 0 && <> dont {bilan.a_regler} à régler</>} · <b className="text-txt">{bilan.termine}</b> terminé{bilan.termine > 1 ? 's' : ''}
      {bilan.plantsSortis > 0 && <>, {bilan.plantsSortis} plants sortis vers le potager</>}
    </p>
  )
  const pied = (
    <p className="mt-1 text-[12.5px] text-txt2">Registre sans geste : on agit depuis le Parcours ou par Noter.</p>
  )

  const carte = (lot) => (
    <CarteLot
      key={lot.lot_id}
      carte={carteLotDuRegistre(lot, parcours, alertes)}
      choisie={lotOuvert === lot.lot_id}
      onOuvrir={() => onOuvrirLot(lot)}
    />
  )

  if (matrice.total === 0) {
    return (
      <div className="@container/lots flex flex-col gap-3">
        {bilanTexte}
        <p className="px-1 py-6 text-center text-[13px] text-txt3">Aucun lot ne correspond à cette recherche.</p>
        {pied}
      </div>
    )
  }

  // ── Mobile : un état à la fois, les lots groupés par mois de semis ───────────────────────────
  if (!bureau) {
    const actif = colonneRegistreInitiale(etat.filtreLots)
    return (
      <div className="@container/lots flex flex-col gap-3">
        {bilanTexte}
        <PagerAimante
          etiquette="États" actif={actif} onChange={(cle) => setEtat({ filtreLots: cle })}
          pages={matrice.colonnes.map((c) => ({
            cle: c.cle,
            libelle: `${c.libelle} · ${c.total}`,
            contenu: (
              <div className="flex flex-col gap-2 pb-2">
                <h3 className="sr-only">{c.libelle} · {c.total}</h3>
                {c.total === 0 && <p className="px-1 py-1 text-[12px] italic text-txt3">vide</p>}
                {matrice.rangees.filter((r) => r.cases[c.cle].length > 0).map((r) => (
                  <section key={r.cle} aria-label={`${r.titre} · ${r.cases[c.cle].length}`} className="flex flex-col gap-2">
                    <div className="flex items-center gap-1.5 pt-1 text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2">
                      <i aria-hidden="true" className="block h-2.5 w-2.5 rounded-[3px]" style={{ background: r.couleur }} />
                      {r.titre} · {r.cases[c.cle].length}
                    </div>
                    {r.cases[c.cle].map(carte)}
                  </section>
                ))}
              </div>
            ),
          }))}
        />
        {pied}
      </div>
    )
  }

  // ── Ordinateur : la matrice mois de semis × état ──────────────────────────────────────────────
  return (
    <section className="@container/lots flex flex-col gap-3" aria-labelledby="titre-registre">
      {bilanTexte}
      <h2 id="titre-registre" className="text-[13px] font-bold text-txt2">Le registre · mois de semis × état</h2>
      <div
        role="table" aria-label="Les lots par mois de semis et par état"
        className="grid grid-cols-[190px_repeat(3,minmax(0,1fr))] overflow-hidden rounded-[18px] border border-border bg-card shadow-card"
      >
        <div role="columnheader" className="border-b border-border px-3.5 py-3 text-[12.5px] font-bold text-txt">Mois de semis</div>
        {matrice.colonnes.map((c) => (
          <div key={c.cle} role="columnheader" className="border-b border-l border-border-soft px-3.5 py-3">
            <span className="flex items-center gap-2 text-[12.5px] font-bold text-txt"><Pastille couleur={c.couleur} />{c.libelle} · {c.total}</span>
          </div>
        ))}
        {matrice.rangees.map((r) => (
          <div key={r.cle} role="row" className="contents">
            <div
              role="rowheader" className="border-t border-border px-3.5 py-3"
              style={{ ...teinte(r.couleur), boxShadow: `inset 4px 0 0 ${r.couleur}` }}
            >
              <b className="block text-[13px] text-txt">{r.titre}</b>
              <small className="block text-[11.5px] text-txt2">{r.total} lot{r.total > 1 ? 's' : ''}{r.sousTitre ? ` · ${r.sousTitre}` : ''}</small>
            </div>
            {matrice.colonnes.map((c) => (
              <div key={c.cle} role="cell" className="flex flex-col gap-2 border-l border-t border-border-soft p-2.5" style={teinte(r.couleur)}>
                {r.cases[c.cle].length ? r.cases[c.cle].map(carte) : <span className="px-1 py-1 text-[12px] italic text-txt3">vide</span>}
              </div>
            ))}
          </div>
        ))}
      </div>
      {pied}
    </section>
  )
}
