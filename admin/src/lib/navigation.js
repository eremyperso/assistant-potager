// Les six vues de l'application [US-311 / CA4]. Une seule est livrée avec la coquille (Consommation,
// US-312) ; les autres s'ouvrent sur un écran d'attente qui nomme l'US qui les remplira.
// La vue courante vit dans le fragment (#/cout), les filtres dans la requête : les deux se
// copient avec l'adresse.
//
// libelleLong : le nom complet, dans le bandeau (≥ 900 px) ; court : celui de la barre basse.

export const VUES = [
  { id: 'consommation', libelle: 'Consommation', libelleLong: 'Consommation', court: 'Conso', us: 'US-312' },
  { id: 'cout', libelle: 'Coût', libelleLong: 'Coût', court: 'Coût', us: 'US-313' },
  { id: 'fiabilite', libelle: 'Fiabilité', libelleLong: 'Fiabilité', court: 'Fiabilité', us: 'US-314' },
  { id: 'derives', libelle: 'Dérives', libelleLong: 'Dérives', court: 'Dérives', us: 'US-315' },
  { id: 'potagers', libelle: 'Potagers', libelleLong: 'Potagers et jardiniers', court: 'Potagers', us: 'US-319' },
  { id: 'seuils', libelle: 'Seuils', libelleLong: 'Seuils', court: 'Seuils', us: 'US-316' },
]
export const VUE_DEFAUT = 'consommation'

export function vueDepuisFragment(fragment) {
  const id = String(fragment || '').replace(/^#\/?/, '').split('?')[0]
  return VUES.some((v) => v.id === id) ? id : VUE_DEFAUT
}

export const versFragment = (vue) => `#/${vue}`

export const vue = (id) => VUES.find((v) => v.id === id) || VUES[0]
