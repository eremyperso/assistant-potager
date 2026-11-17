// Périodes du sélecteur [US-311 / CA4]. Les bornes sont des dates INCLUSES, comme celles de
// `GET /admin/pilotage/...` ; « 7 jours » = aujourd'hui et les six jours précédents.
import { jourIso } from './format.js'

export const PERIODES = [
  { id: 'aujourdhui', libelle: "Aujourd'hui", jours: 1 },
  { id: '7j', libelle: '7 jours', jours: 7 },
  { id: '30j', libelle: '30 jours', jours: 30 },
  { id: '90j', libelle: '90 jours', jours: 90 },
  { id: 'perso', libelle: 'Personnalisée', jours: null },
]

export const PERIODE_DEFAUT = '7j'
const IDS = new Set(PERIODES.map((p) => p.id))
const ISO = /^\d{4}-\d{2}-\d{2}$/

export const periodeConnue = (id) => IDS.has(id)
export const dateValide = (texte) => typeof texte === 'string' && ISO.test(texte) && !Number.isNaN(Date.parse(texte))

function reculer(date, jours) {
  const copie = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  copie.setDate(copie.getDate() - jours)
  return copie
}

/** Les bornes (dates incluses, « AAAA-MM-JJ ») d'une période. `perso` lit `depuis` / `jusqu_a`. */
export function bornes({ periode, depuis, jusqu_a }, maintenant = new Date()) {
  if (periode === 'perso' && dateValide(depuis) && dateValide(jusqu_a) && depuis <= jusqu_a) {
    return { depuis, jusqu_a }
  }
  const def = PERIODES.find((p) => p.id === periode && p.jours) || PERIODES.find((p) => p.id === PERIODE_DEFAUT)
  return { depuis: jourIso(reculer(maintenant, def.jours - 1)), jusqu_a: jourIso(maintenant) }
}

/** Nombre de jours (inclus) de deux dates « AAAA-MM-JJ ». */
export function nbJours(depuis, jusqu_a) {
  const [a1, m1, j1] = depuis.split('-').map(Number)
  const [a2, m2, j2] = jusqu_a.split('-').map(Number)
  return Math.round((Date.UTC(a2, m2 - 1, j2) - Date.UTC(a1, m1 - 1, j1)) / 86_400_000) + 1
}

/** La vue du jour : celle qui se rafraîchit seule [US-311 / CA5]. */
export const estVueDuJour = (periode) => periode === 'aujourdhui'
