/** Médaillon-bulle de l'identité visuelle, version « inverse » du bandeau vert (maquette d'US-318).
 *  Décoratif : le nom « Pilotage » est écrit à côté. */
export default function Logo({ taille = 30 }) {
  return (
    <svg viewBox="0 0 200 200" width={taille} height={taille} aria-hidden="true" className="shrink-0">
      <path d="M160.4 172 A94 94 0 1 1 183 144.1 L186 192 Z" fill="none" stroke="#F6F1E4" strokeWidth="10" strokeLinejoin="round" />
      <path d="M44 144 Q100 126 156 144M58 164 Q100 150 142 164" fill="none" stroke="#E8A583" strokeWidth="10" strokeLinecap="round" />
      <path d="M100 130 C100 112 100 98 100 86" fill="none" stroke="#F6F1E4" strokeWidth="10" strokeLinecap="round" />
      <path d="M100 104 C80 104 64 92 62 70 C84 70 98 82 100 104 Z" fill="#F6F1E4" />
      <path d="M100 90 C100 64 118 46 144 44 C146 70 128 90 100 90 Z" fill="#A8D072" />
    </svg>
  )
}
