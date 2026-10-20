import { ScrollText } from 'lucide-react'
import { useDateRef } from '../context/AppContext.jsx'
import { useNavigation } from '../context/NavigationContext.jsx'
import { jourLocal } from '../lib/gestes.js'
import { destinationJournal } from '../lib/planVue.js'
import DateRefPicker from './DateRefPicker.jsx'
import { Btn } from './ui'

/**
 * Date de référence et « Journal du jour » de l'activité Plan [US-223 / CA5].
 *
 * Posés dans l'en-tête, sous les sous-onglets : aux mêmes places sur la Vue plan
 * et sur Parcelles, indépendants de toute sélection de parcelle. Ils ne
 * dépendent d'aucun écran — la date vient du contexte, le journal s'ouvre
 * filtré sur ce jour (US-201 / I6, A15).
 *
 * [CA6] Composant à container query : « Journal du jour » s'abrège en
 * « Journal » quand la barre est étroite, les cibles d'appui gardent 44 px.
 */
export default function BarreActivitePlan() {
  const { dateRef } = useDateRef()
  const { aller } = useNavigation()
  const jour = dateRef || jourLocal()
  const { vue, intention } = destinationJournal(jour)

  return (
    <div className="@container/barre mt-3">
      <div className="flex items-center justify-between gap-2">
        <DateRefPicker haute />
        <Btn
          small
          icon={ScrollText}
          className="min-h-[44px]"
          onClick={() => aller(vue, intention)}
          aria-label="Journal du jour"
        >
          <span className="@[300px]/barre:hidden">Journal</span>
          <span className="hidden @[300px]/barre:inline">Journal du jour</span>
        </Btn>
      </div>
    </div>
  )
}
