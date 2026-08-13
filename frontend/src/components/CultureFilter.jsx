// [US-031 CA17-CA19] Champ de recherche culture — local par écran, non persisté.
// [US-059 CA2] Habillage délégué au composant de recherche du design system :
// ce fichier ne conserve que le libellé métier (« filtrer par culture ») et la
// signature attendue par les quatre écrans de consultation.
import { SearchField } from './ui'

export default function CultureFilter({ value, onChange, placeholder = 'Filtrer par culture…', className = 'relative' }) {
  return (
    <SearchField
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className={className}
      aria-label="Filtrer par culture"
    />
  )
}
