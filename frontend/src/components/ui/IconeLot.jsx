// L'icône d'un LOT de pépinière (maquette « Socle commun », icône `lot`) : une étiquette de piquet,
// la même partout où un lot est nommé — onglet Lots, numéro sur la carte, titre de sa fiche, variétés,
// origine, journal. Tracé à la manière de lucide (24 × 24, trait de 2, extrémités arrondies), donc elle
// prend `size`, `className`, `strokeWidth` comme les autres icônes ; sa couleur est celle de la
// pépinière (`text-pep`) tant qu'on n'en donne pas une autre.
import { createLucideIcon } from 'lucide-react'

export const Lot = createLucideIcon('Lot', [
  ['path', { d: 'M5 3h14a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-5v8l-2 3-2-3v-8H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z', key: 'etiquette' }],
  ['path', { d: 'M8 6.5h8', key: 'ligne' }],
])

/** L'icône du lot, décorative et à la couleur de la pépinière. */
export default function IconeLot({ size = 14, className = '' }) {
  return <Lot size={size} aria-hidden="true" className={`shrink-0 text-pep ${className}`.trim()} />
}
