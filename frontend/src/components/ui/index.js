// Design system de l'interface web [US-052].
// Point d'entrée unique : `import { Card, Btn, Badge } from '../components/ui'`
export { Card, CardHead } from './Card.jsx'
export { Btn } from './Btn.jsx'
export { Badge } from './Badge.jsx'
export { Stat } from './Stat.jsx'
export { ProgressBar } from './ProgressBar.jsx'
export { MonthStrip, MonthStripLegend } from './MonthStrip.jsx'
export { SearchField } from './SearchField.jsx'
export { Select } from './Select.jsx'
export { IconSelect } from './IconSelect.jsx'
export { RoleSelect } from './RoleSelect.jsx'
export { LegendeRepliable } from './LegendeRepliable.jsx'
export { TileNav } from './TileNav.jsx'
export { InfoBanner } from './InfoBanner.jsx'
export { Tip } from './Tip.jsx'
export { Placeholder } from './Placeholder.jsx'
export { Pop, PopItem, PopHead, PopSep } from './Pop.jsx'
export { Modal } from './Modal.jsx'
export { Toast } from './Toast.jsx'
export { SectionLabel } from './SectionLabel.jsx'
export { GroupHead, useGroups } from './GroupHead.jsx'
export { Field } from './Field.jsx'
export { VilleSearch } from './VilleSearch.jsx'

// [US-180] Bloc « règle de confiance », partagé avec la fiche calendrier (US-183).
export {
  Etoiles, LigneRegle, BlocConfiance, SelecteurAction, PastilleConfiance, PuceConfiance,
} from './RegleConfiance.jsx'

// [US-194] Phase du moment d'une culture en place — Vue plan, Cultures, fiche culture.
export { PastillePhase, LegendePhases } from './PastillePhase.jsx'

// [US-200] Le trait d'un rang. [US-327 / CA6] La carte par parcelle et son rang
// (`CartePlanParcelle`, `RangPlan`) ont quitté l'écran Plan avec l'ancienne Vue plan ;
// le trait reste, mode dégradé de la piste des places du suivi de culture (US-322).
export { TraitRang } from './TraitRang.jsx'

// [US-228] La piste des places — un rang dessiné en places prises et restantes.
// `TraitRang` en reste le MODE DÉGRADÉ, pour les rangs sans places calculables.
export { PisteDesPlaces, IconeCote } from './PisteDesPlaces.jsx'

// [US-321] Langage visuel des étapes : étiquette, segment, légende, pictogrammes.
// La correspondance étape → couleur / pictogramme / libellé est dans `lib/etapes.js`.
export { EtiquetteEtape, SegmentEtape, LegendeEtapes, PictoEtape, IconeEtape } from './EtapeCulture.jsx'
