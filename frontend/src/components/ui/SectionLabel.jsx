/** Intitulé de section en majuscules, utilisé dans les cartes et modales [US-055]. */
export function SectionLabel({ children, right }) {
  return (
    <div className="flex items-center justify-between gap-2.5 mb-2.5">
      <span className="text-[11.5px] font-bold text-txt3 uppercase tracking-wider">{children}</span>
      {right}
    </div>
  )
}

export default SectionLabel
