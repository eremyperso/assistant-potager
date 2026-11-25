import { useCallback, useMemo } from 'react'
import { useCoquille } from '../context/CoquilleContext.jsx'
import FicheCommune from '../components/FicheCommune.jsx'
import FicheCatalogue from '../components/FicheCatalogue.jsx'
import { nomCulture } from '../lib/planDessus.js'

/**
 * [US-355 / CA1] Ouvrir une fiche : la même depuis le Tableau de bord, le Plan, Cultures, les Stocks et le Journal.
 * La fiche est UN occupant du panneau partagé (US-353) : panneau droit sur ordinateur, feuille sur mobile, un seul à
 * la fois (ouvrir Gaston ou une autre fiche remplace la précédente).
 *
 *  - `ouvrirCulture(selection)` : la fiche commune d'une culture (`{ culture, variete?, parcelleId?, parcelle?, rang? }`) ;
 *  - `ouvrirCatalogue(ligne, { enPlace })` : la fiche catalogue d'une espèce ; `enPlace` est la sélection de la
 *    culture déjà au potager, que « Ouvrir la culture en place » ouvre.
 *  - `fermer()`.
 */
export function useFiches() {
  const { ouvrirPanneau, fermerPanneau } = useCoquille()

  const ouvrirCulture = useCallback((selection, options = {}) => {
    if (!selection?.culture) return
    const cle = `${selection.parcelleId ?? ''}|${selection.culture}|${selection.variete || ''}`
    ouvrirPanneau({
      cle: 'fiche',
      commune: true,   // se referme au changement de vue (App.jsx)
      titre: nomCulture(selection.culture, null),
      contenu: <FicheCommune key={cle} selection={selection} onglet={options.onglet} />,
    })
  }, [ouvrirPanneau])

  const ouvrirCatalogue = useCallback((ligne, { enPlace = null } = {}) => {
    if (!ligne?.culture) return
    ouvrirPanneau({
      cle: 'catalogue',
      commune: true,
      titre: `Catalogue · ${ligne.nom}`,
      contenu: (
        <FicheCatalogue
          key={ligne.culture} ligne={ligne}
          onOuvrirEnPlace={enPlace ? () => ouvrirCulture(enPlace) : null}
        />
      ),
    })
  }, [ouvrirPanneau, ouvrirCulture])

  return useMemo(() => ({ ouvrirCulture, ouvrirCatalogue, fermer: fermerPanneau }), [ouvrirCulture, ouvrirCatalogue, fermerPanneau])
}

export default useFiches
