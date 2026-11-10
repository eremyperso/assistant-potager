// Médaillon de la marque : une pousse sur des sillons de terre cuite, dans un contour qui se
// prolonge en queue de bulle de dialogue (la voix du compagnon).
//
// Même dessin que `identite-visuelle/export/svg/medaillon*.svg` (source : source/identite.py).
//
// - Couleurs : variables `--logo-*` (brand.css), qui basculent avec la classe `.dark` ;
//   `variante="inverse"` pour un fond vert ou sombre fixe, `variante="mono"` pour une seule
//   couleur (celle du texte : `currentColor`).
// - Jusqu'à 48 px, la version simplifiée (traits épaissis, un sillon en moins) est choisie seule.
// - Décoratif par défaut (aria-hidden) ; passer `titre` pour l'exposer aux lecteurs d'écran.

const CONTOUR = 'M160.4 172 A94 94 0 1 1 183 144.1 L186 192 Z'

const COULEURS = {
  auto: {
    anneau: 'var(--logo-anneau, #1F4D3A)',
    feuilleA: 'var(--logo-feuille-a, #1F4D3A)',
    feuilleB: 'var(--logo-feuille-b, #5B8F3A)',
    sillon: 'var(--logo-sillon, #9E4524)',
  },
  inverse: { anneau: '#F6F1E4', feuilleA: '#F6F1E4', feuilleB: '#A8D072', sillon: '#E8A583' },
  mono: { anneau: 'currentColor', feuilleA: 'currentColor', feuilleB: 'currentColor', sillon: 'currentColor' },
}

export default function MedaillonBulle({
  taille = 34,
  variante = 'auto',
  simplifie,
  titre,
  className = '',
  style,
}) {
  const c = COULEURS[variante] || COULEURS.auto
  const petit = simplifie ?? taille <= 48
  const trait = (couleur, largeur) => ({
    fill: 'none', stroke: couleur, strokeWidth: largeur, strokeLinecap: 'round', strokeLinejoin: 'round',
  })

  return (
    <svg
      viewBox="0 0 200 200"
      width={taille}
      height={taille}
      className={`shrink-0 ${className}`}
      style={style}
      role={titre ? 'img' : undefined}
      aria-label={titre}
      aria-hidden={titre ? undefined : true}
      focusable="false"
    >
      <path d={CONTOUR} style={trait(c.anneau, petit ? 9 : 5)} />
      {!petit && <circle cx="100" cy="100" r="85" style={{ fill: 'none', stroke: c.anneau, strokeWidth: 1.6 }} />}
      {petit ? (
        <>
          <path d="M44 144 Q100 126 156 144" style={trait(c.sillon, 9)} />
          <path d="M58 164 Q100 150 142 164" style={trait(c.sillon, 9)} />
        </>
      ) : (
        <>
          <path d="M44 142 Q100 124 156 142" style={trait(c.sillon, 5)} />
          <path d="M54 158 Q100 142 146 158" style={trait(c.sillon, 5)} />
          <path d="M68 172 Q100 160 132 172" style={trait(c.sillon, 5)} />
        </>
      )}
      <path d="M100 130 C100 112 100 98 100 86" style={trait(c.feuilleA, petit ? 9 : 5)} />
      <path d="M100 104 C80 104 64 92 62 70 C84 70 98 82 100 104 Z" style={{ fill: c.feuilleA }} />
      <path d="M100 90 C100 64 118 46 144 44 C146 70 128 90 100 90 Z" style={{ fill: c.feuilleB }} />
    </svg>
  )
}
