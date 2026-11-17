import { useEffect, useRef, useState } from 'react'
import { echelle, CLE_AUTRES } from '../lib/consommation.js'
import { abrege, entier, pourcent } from '../lib/format.js'

// Géométrie de la maquette d'US-318 : marges, hauteur (190 px étroit, 220 px large), barres à 62 %.
const MARGE = { haut: 14, droite: 8, bas: 26, gauche: 46 }
const JOURS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.']

const COULEURS = ['var(--serie-1)', 'var(--serie-2)', 'var(--serie-3)', 'var(--serie-4)', 'var(--serie-5)']
function couleurDe(serie, rang) {
  if (serie.cle === 'hors_cache') return 'var(--brand)'
  if (serie.cle === 'cache') return 'var(--serie-cache)'
  if (serie.cle === CLE_AUTRES) return 'var(--serie-autres)'
  return COULEURS[rang % COULEURS.length]
}

/** Largeur réelle du conteneur : le SVG est dessiné à sa taille, le texte garde donc sa taille. */
function useLargeur(defaut = 640) {
  const ref = useRef(null)
  const [largeur, setLargeur] = useState(defaut)
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === 'undefined') return undefined
    const o = new ResizeObserver(([e]) => setLargeur(Math.max(200, Math.round(e.contentRect.width))))
    o.observe(ref.current)
    return () => o.disconnect()
  }, [])
  return [ref, largeur]
}

/** « lun. » pour une semaine, « 9 nov. » au-delà ; une heure s'écrit « 6 h » (une sur six). */
function etiquettes(modele) {
  const n = modele.points.length
  if (modele.pas === 'heure') return modele.points.map((_, h) => (h % 6 === 0 ? `${h} h` : ''))
  if (n <= 7) return modele.points.map((p) => { const [a, m, j] = p.cle.split('-').map(Number); return JOURS[new Date(a, m - 1, j).getDay()] })
  const cadence = Math.ceil(n / 8)
  return modele.points.map((p, i) => (i % cadence === 0 ? p.libelle : ''))
}

/**
 * Graphique à piles par jour (ou par heure) [US-312 / CA2, CA3, CA8, CA9], d'après la maquette d'US-318.
 * - Une pile par pas ; un pas sans appel est un « 0 » posé sur l'axe (pas de trou).
 * - La légende, au-dessus, isole une série : un second clic la rend aux autres.
 * - `modele.mode === 'ventile'` : la part servie par le cache est une ligne en pointillé.
 * - `modele.mode === 'empile'` : une pile par série, sans ligne de cache (issues, versions…) ; la légende
 *   garde la part de chaque série comme en mode ventilé.
 * - `formatValeur` / `formatAxe` : l'unité de la mesure (euros, millisecondes…), jetons par défaut ;
 *   `reperes` : [{ index, libelle }], un trait vertical au début du pas (première apparition d'une version).
 * Écrit à la main (pas de bibliothèque) : maquette respectée au pixel, application légère.
 */
export default function Graphique({ modele, titre, formatValeur = entier, formatAxe = abrege, reperes = [] }) {
  const [ref, w] = useLargeur()
  const [isolee, setIsolee] = useState(null)
  const visibles = modele.series.filter((s) => !isolee || s.cle === isolee)
  const horaire = modele.pas === 'heure'

  const H = w < 420 ? 190 : 220
  const n = modele.points.length
  const pile = modele.points.map((_, i) => visibles.reduce((a, s) => a + (s.valeurs[i] || 0), 0))
  const maximum = Math.max(0, ...pile, ...(modele.mode === 'ventile' && !isolee ? modele.cache : []))
  const ech = echelle(maximum)
  const marge = { ...MARGE, gauche: formatAxe === abrege ? MARGE.gauche : 62 }
  const cw = (w - marge.gauche - MARGE.droite) / n
  const bw = Math.min(cw * 0.62, 48)
  const y = (v) => marge.haut + (H - marge.haut - marge.bas) * (1 - v / ech.max)
  const libelles = etiquettes(modele)
  const avecValeurs = w >= 420 && !horaire && n <= 14

  return (
    <div>
      <ul className="mb-2 mt-0.5 flex flex-wrap gap-x-3.5 gap-y-1.5 text-xs text-txt2" aria-label="Légende — activer une série pour l'isoler">
        {modele.series.map((s, i) => {
          const actif = !isolee || isolee === s.cle
          return (
            <li key={s.cle}>
              <button type="button" aria-pressed={isolee === s.cle} onClick={() => setIsolee(isolee === s.cle ? null : s.cle)}
                className={`inline-flex items-center gap-1.5 rounded px-0.5 ${actif ? '' : 'opacity-45 line-through'}`}>
                <i className="inline-block h-3 w-3 rounded-[3px]" style={{ background: couleurDe(s, i) }} aria-hidden="true" />
                {modele.mode === 'ventile' || modele.mode === 'empile'
                  ? <><b className="font-semibold text-txt">{s.libelle}</b> {s.part === null || s.part === undefined ? '' : pourcent(s.part, s.part < 0.01 ? 1 : 0)}</>
                  : s.libelle}
              </button>
            </li>
          )
        })}
        {modele.mode === 'ventile' ? (
          <li className="inline-flex items-center gap-1.5">
            <svg width="16" height="8" aria-hidden="true"><line x1="0" x2="16" y1="4" y2="4" stroke="var(--serie-cache)" strokeWidth="2" strokeDasharray="4 3" /></svg>
            dont cache
          </li>
        ) : null}
      </ul>

      <div ref={ref} className="block">
        <svg viewBox={`0 0 ${w} ${H}`} role="img" aria-label={titre} className="block h-auto w-full">
          {ech.graduations.map((g) => (
            <g key={g}>
              <line x1={marge.gauche} x2={w - MARGE.droite} y1={y(g)} y2={y(g)} stroke="var(--border)" strokeDasharray={g ? '2 3' : undefined} />
              <text x={marge.gauche - 6} y={y(g) + 4} textAnchor="end" fontSize="10.5" fill="var(--txt2)">{g ? formatAxe(g) : '0'}</text>
            </g>
          ))}
          {modele.points.map((p, i) => {
            const x = marge.gauche + cw * i + (cw - bw) / 2
            let cumul = 0
            return (
              <g key={p.cle}>
                {libelles[i] ? <text x={x + bw / 2} y={H - 8} textAnchor="middle" fontSize="10.5" fill="var(--txt2)">{libelles[i]}</text> : null}
                {pile[i] === 0 ? (
                  horaire ? null : <text x={x + bw / 2} y={y(0) - 6} textAnchor="middle" fontSize="10.5" fill="var(--txt3)">0<title>{`${p.libelle} — aucun appel`}</title></text>
                ) : (
                  <>
                    {visibles.map((s) => {
                      const rang = modele.series.indexOf(s)
                      const v = s.valeurs[i] || 0
                      const y0 = y(cumul + v)
                      const rect = (
                        <rect key={s.cle} x={x} y={y0} width={bw} height={Math.max(y(cumul) - y0, 0)}
                          fill={couleurDe(s, rang)} stroke="var(--card)" strokeWidth="1">
                          <title>{`${p.libelle} — ${s.libelle} : ${formatValeur(v)}`}</title>
                        </rect>
                      )
                      cumul += v
                      return rect
                    })}
                    {avecValeurs ? <text x={x + bw / 2} y={y(pile[i]) - 5} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="var(--txt)">{formatAxe(pile[i])}</text> : null}
                  </>
                )}
              </g>
            )
          })}
          {modele.mode === 'ventile' && !isolee ? (
            <g>
              <polyline fill="none" stroke="var(--serie-cache)" strokeWidth="2" strokeDasharray="5 4"
                points={modele.cache.map((v, i) => `${marge.gauche + cw * i + cw / 2},${y(v)}`).join(' ')} />
              {modele.cache.map((v, i) => <circle key={i} cx={marge.gauche + cw * i + cw / 2} cy={y(v)} r="3" fill="var(--card)" stroke="var(--serie-cache)" strokeWidth="2" />)}
            </g>
          ) : null}
          {reperes.map((r, k) => {
            const x = marge.gauche + cw * r.index
            return (
              <g key={r.libelle}>
                <line x1={x} x2={x} y1={marge.haut} y2={H - marge.bas} stroke="var(--txt2)" strokeWidth="1.25" strokeDasharray="3 3" />
                <text x={x + 3} y={marge.haut + 9 + (k % 2) * 11} fontSize="10" fontWeight="600" fill="var(--txt2)">{r.libelle}</text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
