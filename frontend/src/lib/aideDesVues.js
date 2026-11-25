// [US-359 / CA5] L'aide de la vue : menu ⋯ › « Aide de la vue » ouvre la section du guide propre à
// l'écran où l'on est. Une entrée par vue, calculée sans modèle ; `section` est le titre de la
// section du guide utilisateur (section 4.5, « Les écrans, un par un ») qu'elle résume, et `question`
// est la phrase que « Demander à Gaston » pré-écrit dans son champ (jamais envoyée d'office).
//
// Le texte dit la même chose que le guide (`docs/MANUEL/guide assistant.md` et sa copie du corpus) :
// toute modification de l'un se reporte dans l'autre.

/** Le titre de la section du guide dont toutes les aides tirent leur renvoi. */
export const SECTION_GUIDE = '4.5 Les écrans, un par un'

export const AIDE_PAR_VUE = Object.freeze({
  bord: {
    titre: 'Tableau de bord',
    section: 'Tableau de bord',
    points: [
      'La vue d’ensemble : ce qui demande votre œil aujourd’hui, la Météo · 3 jours (le jour de gel en ambre) et les dernières notes du carnet.',
      'Une section vide disparaît ; il n’y a ni barre d’outils ni personnalisation.',
      'Toucher une ligne ouvre la fiche de la culture.',
    ],
    question: 'Que montre le tableau de bord ?',
  },
  stats: {
    titre: 'Statistiques',
    section: 'Tableau de bord',
    points: [
      'Les récoltes, les stocks et les semis de votre potager, recalculés depuis vos gestes.',
      'Le bouton « Aujourd’hui » remonte dans le temps : les chiffres se recalculent à cette date.',
    ],
    question: 'Comment lire les statistiques ?',
  },
  'plan-vue': {
    titre: 'Plan',
    section: 'Plan',
    points: [
      'Le potager vu du dessus, parcelle par parcelle ; chaque rang est coloré selon l’étape de sa culture.',
      'La règle des temps (bouton « Aujourd’hui ») remonte dans le passé.',
      'Toucher une culture ouvre sa fiche commune ; toucher une parcelle, son détail.',
    ],
    question: 'Comment lire le plan ?',
  },
  cultures: {
    titre: 'Cultures',
    section: 'Cultures · Au potager et Cultures · Catalogue',
    points: [
      'Au potager : vos cultures rangées par ce qui demande une action (À confirmer, À placer, En récolte…).',
      'Catalogue : les espèces du référentiel, par prochaine fenêtre de semis ; « Ajouter à mon potager » ouvre Gaston avec la phrase prête à envoyer.',
      'Une culture absente du catalogue : « Dites-la à Gaston », en bas de l’écran.',
    ],
    question: 'Comment ajouter une culture du catalogue ?',
  },
  pepiniere: {
    titre: 'Pépinière',
    section: 'Pépinière',
    points: [
      'Parcours : vos lots, de la germination à la mise en terre.',
      'Semer : le bon moment pour semer ; le bouton Semer ouvre Gaston avec la phrase prête.',
      'Lots : le registre, par colonnes En cours, À régler et Terminés.',
    ],
    question: 'Comment suivre mes lots de pépinière ?',
  },
  stocks: {
    titre: 'Stocks',
    section: 'Stocks',
    points: [
      'Les stocks par variété, avec les Récoltes par saison.',
      'Le menu ⋯ exporte en CSV ou en JSON ce qui est à l’écran, filtres appliqués.',
    ],
    question: 'Comment lire mes stocks ?',
  },
  journal: {
    titre: 'Journal',
    section: 'Journal',
    points: [
      'Tous vos gestes et notes, filtrables par type, culture et date ; il a son propre filtre de date.',
      'Le menu ⋯ exporte exactement ce qui est affiché.',
    ],
    question: 'Comment retrouver un geste dans le journal ?',
  },
})

/** L'aide de la vue, ou `null` quand l'écran n'en a pas (aucune entrée n'est alors proposée). */
export function aideDeLaVue(vue) {
  return AIDE_PAR_VUE[vue] ?? null
}

/** La barre avec « Aide de la vue » ajoutée à son menu ⋯ ; sans barre ou sans aide, elle est rendue telle quelle. */
export function barreAvecAide(barre, vue, ouvrir) {
  if (!barre || !aideDeLaVue(vue)) return barre
  return { ...barre, menu: { ...(barre.menu ?? {}), aide: ouvrir } }
}
