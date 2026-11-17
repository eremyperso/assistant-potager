// Les filtres de la coquille, partagés par toutes les vues et gardés dans l'adresse
// [US-311 / CA4] : `?periode=30j&provenance=mesure&canal=pwa&modele=…`. Une valeur par défaut
// n'apparaît pas dans l'adresse. Ouvrir une adresse copiée retrouve exactement les mêmes chiffres.
import { PERIODE_DEFAUT, bornes, dateValide, periodeConnue } from './periode.js'

export const PROVENANCES = [
  { id: 'usage', libelle: 'Usage' },
  { id: 'fond', libelle: 'Tâches de fond' },
  { id: 'mesure', libelle: 'Mesures' },
  { id: 'test', libelle: 'Tests' },
  { id: 'historique', libelle: 'Historique' },
]
export const PROVENANCES_PAR_DEFAUT = ['usage', 'fond']
export const TOUTES_LES_PROVENANCES = PROVENANCES.map((p) => p.id)

/** Le sélecteur de provenance de la maquette (US-318) : un seul choix, qui correspond au filtre de
 *  l'API. `defaut` = usage + fond (rien dans l'adresse) ; `toutes` = les cinq provenances. */
export const CHOIX_PROVENANCE = [
  { id: 'defaut', libelle: 'usage, fond' },
  { id: 'mesure', libelle: 'mesure' },
  { id: 'test', libelle: 'test' },
  { id: 'historique', libelle: 'historique' },
  { id: 'toutes', libelle: 'toutes' },
]

export function choixDeProvenance(provenance) {
  if (!provenance.length) return 'defaut'
  if (provenance.length === 1) return provenance[0]
  return TOUTES_LES_PROVENANCES.every((p) => provenance.includes(p)) ? 'toutes' : 'autre'
}

export function provenanceDuChoix(choix) {
  if (choix === 'defaut') return []
  if (choix === 'toutes') return [...TOUTES_LES_PROVENANCES]
  return IDS_PROVENANCE.has(choix) ? [choix] : []
}
export const CANAUX = ['telegram', 'pwa', 'mcp', 'fond', 'outil', 'inconnu']

const IDS_PROVENANCE = new Set(PROVENANCES.map((p) => p.id))

export const FILTRES_DEFAUT = Object.freeze({
  periode: PERIODE_DEFAUT, depuis: '', jusqu_a: '', provenance: [], canal: '', modele: '',
})

/** Lit une chaîne de requête (`location.search`). Toute valeur inconnue retombe sur le défaut. */
export function depuisRecherche(recherche) {
  const p = new URLSearchParams(recherche || '')
  const periode = periodeConnue(p.get('periode')) ? p.get('periode') : PERIODE_DEFAUT
  const depuis = p.get('depuis'), jusqu_a = p.get('jusqu_a')
  const perso = periode === 'perso' && dateValide(depuis) && dateValide(jusqu_a) && depuis <= jusqu_a
  const provenance = (p.get('provenance') || '').split(',').filter((v) => IDS_PROVENANCE.has(v))
  const canal = CANAUX.includes(p.get('canal')) ? p.get('canal') : ''
  return {
    periode: periode === 'perso' && !perso ? PERIODE_DEFAUT : periode,
    depuis: perso ? depuis : '',
    jusqu_a: perso ? jusqu_a : '',
    provenance: [...new Set(provenance)],
    canal,
    modele: p.get('modele') || '',
  }
}

/** L'inverse : la chaîne de requête, vide quand tout est par défaut. */
export function versRecherche(filtres) {
  const p = new URLSearchParams()
  if (filtres.periode !== PERIODE_DEFAUT) p.set('periode', filtres.periode)
  if (filtres.periode === 'perso') {
    p.set('depuis', filtres.depuis)
    p.set('jusqu_a', filtres.jusqu_a)
  }
  if (filtres.provenance.length) p.set('provenance', filtres.provenance.join(','))
  if (filtres.canal) p.set('canal', filtres.canal)
  if (filtres.modele) p.set('modele', filtres.modele)
  const texte = p.toString()
  return texte ? `?${texte}` : ''
}

/** Nombre de filtres actifs (hors période) — affiché sur le bouton replié du téléphone. */
export function nombreFiltresActifs(filtres) {
  return (filtres.provenance.length ? 1 : 0) + (filtres.canal ? 1 : 0) + (filtres.modele ? 1 : 0)
}

/** Vrai quand la provenance est celle par défaut (usage + fond) : le rappel de périmètre s'affiche. */
export const perimetreParDefaut = (filtres) => filtres.provenance.length === 0

/** Les paramètres de `GET /admin/pilotage/...` ; ce qui est par défaut n'est pas envoyé. */
export function versParametresApi(filtres, maintenant = new Date()) {
  const { depuis, jusqu_a } = bornes(filtres, maintenant)
  const params = { depuis, jusqu_a }
  if (filtres.provenance.length) params.provenance = filtres.provenance.join(',')
  if (filtres.canal) params.canal = filtres.canal
  if (filtres.modele) params.modele = filtres.modele
  return params
}

/** Même filtres, sans le filtre de modèle : pour lister les modèles disponibles dans la période. */
export function pourListeDeModeles(filtres, maintenant = new Date()) {
  const { modele, ...reste } = versParametresApi({ ...filtres, modele: '' }, maintenant)
  return { ...reste, provenance: PROVENANCES.map((p) => p.id).join(',') }
}
