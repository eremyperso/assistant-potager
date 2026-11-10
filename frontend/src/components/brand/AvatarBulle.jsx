// Cadre d'avatar « à bulle » : le rond existant (le visage de Gaston) avec une petite queue en bas
// à droite, côté message — le même geste que le médaillon de la marque. Optionnel.
//
// Il reprend le style de l'`Avatar()` de `PanneauCompagnon.jsx` (bord, fond `--gst-visage`, ombre) :
//   <AvatarBulle><VisageGaston /></AvatarBulle>
// La queue est dessinée DERRIÈRE le rond, donc elle ne recouvre jamais le visage.
export default function AvatarBulle({ taille = 34, children, className = '' }) {
  const queue = Math.round(taille * 0.34)
  return (
    <span className={`relative inline-block shrink-0 ${className}`} style={{ width: taille, height: taille }}>
      <svg
        viewBox="0 0 10 10"
        aria-hidden="true"
        focusable="false"
        className="absolute"
        style={{ width: queue, height: queue, right: -Math.round(taille * 0.06), bottom: -Math.round(taille * 0.06) }}
      >
        <path d="M0 3 L10 10 L3 0 Z" style={{ fill: 'var(--gst-visage)' }} strokeLinejoin="round" />
      </svg>
      <span className="relative block h-full w-full overflow-hidden rounded-full border-2 border-[var(--card)] bg-[var(--gst-visage)] shadow-[0_1px_3px_rgba(0,0,0,.12)]">
        {children}
      </span>
    </span>
  )
}
