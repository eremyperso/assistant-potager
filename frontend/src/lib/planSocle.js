// [US-360] Le Plan posé sur le socle : le mot de Gaston du Plan, le bandeau « Au 23 novembre », la
// recherche « Parcelle ou culture » et l'infobulle d'un rang. Logique pure, sans réseau : tout vient
// de la lecture `GET /plan` que l'écran a déjà faite (`taches_du_jour`, `date_ref_effective`).
//
// Le dessin du plan (US-326 → US-333) n'est pas refait ici : cette US le « pose sur le socle ».
import { normaliserMot, motCommun } from './motDeGaston.js'
import { nomPastille } from './etapes.js'
import { LISTE_A_CONFIRMER, LISTE_A_LIBERER } from './aujourdhui.js'

/** Le texte indicatif de la recherche du Plan (CA1). */
export const PLACEHOLDER_RECHERCHE_PLAN = 'Parcelle ou culture'

const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un)

/** « tomate cerise » : le nom d'une ligne, en minuscules, comme dans une phrase. */
const enMinuscules = (nom) => String(nom ?? '').trim().toLowerCase()

/**
 * [CA2] Le bandeau sous la barre d'outils : « **Au 23 novembre** · fond … » à gauche, l'emprise
 * « 25 × 15 m » à droite. La date est celle de la règle des temps (`date_ref_effective`) : elle
 * devient « Au 12 novembre » quand on remonte la saison. Le fond dit ce qu'il est — la photo
 * importée viendra avec US-335 ; d'ici là, c'est la grille neutre, et le bandeau ne prétend pas
 * le contraire.
 */
export function bandeauDuPlan(entete) {
  return {
    date: entete?.titre || '',
    fond: entete?.fond || '',
    dimension: entete?.dimension || '',
    texte: [entete?.titre, entete?.fond].filter(Boolean).join(' · '),
  }
}

/**
 * [CA5] Le mot de Gaston du Plan, sans modèle : les rangs à libérer et, SI la lecture du plan en
 * porte un, l'engrais vert encore possible (`plan.engrais_vert.libelle`, ex. « seigle »).
 *
 *   « **3 rangs à libérer** : tomates cerises, pommes de terre, haricots. Un engrais vert de seigle
 *     peut encore y être semé cette semaine. » → *Voir les rangs*, *Noter*
 *
 * Aucune fenêtre ni espèce n'est inventée : sans `engrais_vert` dans la lecture, la phrase sur
 * l'engrais vert n'est pas dite. Rien à libérer → la règle commune (étapes à confirmer), sinon rien.
 */
export function motDuPlan({ taches = {}, engraisVert = null, gel = null } = {}) {
  const aLiberer = taches[LISTE_A_LIBERER] || []
  if (aLiberer.length > 0) {
    const noms = [...new Set(aLiberer.map((l) => enMinuscules(l.nom)).filter(Boolean))]
    const liste = noms.slice(0, 3).join(', ') + (noms.length > 3 ? '…' : '')
    const engrais = engraisVert?.libelle
      ? ` Un engrais vert de ${engraisVert.libelle} peut encore y être semé cette semaine.`
      : ''
    return normaliserMot({
      texte: `**${aLiberer.length} ${pluriel(aLiberer.length, 'rang à libérer', 'rangs à libérer')}** : ${liste}.${engrais}`,
      actions: [
        { libelle: 'Voir les rangs', vue: 'cultures' },
        { libelle: 'Noter', noter: true },
      ],
    })
  }
  return motCommun({ gel, etapesDues: (taches[LISTE_A_CONFIRMER] || []).length })
}

// ── La recherche « Parcelle ou culture » (CA1) ───────────────────────────────────────────────

/** Minuscules sans accent : « Fève » correspond à « feve ». */
export const normaliserRecherche = (texte) => String(texte ?? '')
  .normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim()

/**
 * Les parcelles qui répondent à la recherche : celles dont le NOM correspond, ou qui portent une
 * culture (ou une variété) qui correspond. `null` quand la recherche est vide (tout reste affiché).
 * Rien ne disparaît du plan : ce qui ne répond pas s'estompe, comme sous un filtre (P8).
 */
export function parcellesTrouvees(plan, recherche) {
  const q = normaliserRecherche(recherche)
  if (!q) return null
  const ids = new Set()
  for (const p of plan?.parcelles || []) {
    const champs = [
      p.nom,
      ...(p.cultures || []).flatMap((c) => [c.culture, c.variete]),
      ...((p.disposition?.lots_en_cours) || []).flatMap((l) => [l.culture, l.variete]),
    ]
    if (champs.some((c) => normaliserRecherche(c).includes(q))) ids.add(p.id)
  }
  return ids
}

// ── L'infobulle d'un rang (CA3, Gherkin 2) ───────────────────────────────────────────────────

/**
 * Le texte lu à l'appui long sur un rang, SANS ouvrir la fiche : « Fève · Levé, prévu ». Un rang
 * libre dit « Rang libre ». Le libellé d'abord, l'état ensuite : jamais la couleur seule.
 */
export function infobulleRang({ nom = '', etape = null, prevu = false, libre = false } = {}) {
  if (libre) return 'Rang libre'
  const etat = etape ? nomPastille(etape, { prevue: prevu }) : ''
  return [nom, etat].filter(Boolean).join(' · ')
}
