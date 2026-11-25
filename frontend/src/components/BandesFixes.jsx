import { useCoquille } from '../context/CoquilleContext.jsx'
import { useDateRef } from '../context/AppContext.jsx'
import { useNavigation } from '../context/NavigationContext.jsx'
import { useState } from 'react'
import { barreEffective } from '../lib/coquille.js'
import { aideDeLaVue, barreAvecAide } from '../lib/aideDesVues.js'  // [US-359 / CA5]
import { executerAction, normaliserMot } from '../lib/motDeGaston.js'
import { ouvrirGastonSur } from '../lib/contexteCompagnon.js'
import MotDeGaston from './MotDeGaston.jsx'
import BarreOutils from './BarreOutils.jsx'
import RegleTemps from './RegleTemps.jsx'
import AideVue from './AideVue.jsx'

/**
 * Les bandes FIXES sous l'en-tête de page [US-353 / CA11] : le Mot de Gaston, la barre d'outils et,
 * juste sous elle, la règle des temps. Elles ne défilent pas ; seule la bande de contenu défile.
 *
 * Ce que la vue y met, elle le DÉCLARE (`useDeclarerEcran`) : son mot (calculé sans modèle,
 * `lib/motDeGaston.js`) et ses contrôles de barre. **Une bande sans contenu disparaît** : sans mot,
 * ou masqué par le ×, rien n'est rendu ; sans barre (le tableau de bord), non plus.
 */
export default function BandesFixes({ view, compact, onRemonter }) {
  const { declaration, masquerMot, motMasque } = useCoquille()
  const { regleOuverte } = useDateRef()
  const { aller } = useNavigation()

  // [US-359 / CA5] « Aide de la vue » est dans le menu ⋯ de toute vue qui a une barre d'outils.
  const [aideOuverte, setAideOuverte] = useState(false)
  const barre = barreAvecAide(barreEffective(view, declaration?.barre), view, () => setAideOuverte(true))
  const aide = aideDeLaVue(view)
  const mot = motMasque(view) ? null : normaliserMot(declaration?.mot)
  if (!mot && !barre) return null

  const marge = compact ? 'mt-2.5' : 'mt-3.5'
  return (
    <div className="mx-auto w-full max-w-[1320px] px-4 pb-3 nav:px-6">
      {mot && (
        <div className={marge}>
          <MotDeGaston
            mot={mot} compact={compact} onRemonter={onRemonter}
            onMasquer={() => masquerMot(view)}
            onAction={(a) => executerAction(a, { ouvrirGaston: (contexte, champ, sujet) => ouvrirGastonSur({ contexte, champ, sujet }), aller })}
          />
        </div>
      )}
      {barre && (
        <div className={marge}>
          <BarreOutils barre={barre} />
          {barre.date && regleOuverte && <RegleTemps />}
        </div>
      )}
      {aideOuverte && aide && (
        <AideVue
          aide={aide} onFermer={() => setAideOuverte(false)}
          onDemander={(question) => { setAideOuverte(false); ouvrirGastonSur({ champ: question }) }}
        />
      )}
    </div>
  )
}
