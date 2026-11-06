// [US-271] Gaston, la carotte du potager — le personnage de la maquette « Compagnon.html ».
//
// Le dessin est celui de la maquette (symboles SVG `c-body`, `c-arm`, `glove`), repris tel quel : un
// corps de carotte, des fanes, un bras qui salue. `GastonDefs` pose les définitions UNE fois dans la
// page ; `VisageGaston` (l'avatar rond) et `GastonComplet` (replié sur le bord) les référencent.

export function GastonDefs() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" focusable="false">
      <defs>
        <symbol id="c-body" viewBox="0 0 100 120">
          <g stroke="#3F6E1E" strokeWidth="2" strokeLinejoin="round">
            <path d="M50 32C44 18 34 10 25 8C33 16 40 24 46 34Z" fill="#6BA832" />
            <path d="M49 32C49 18 52 8 56 1C59 12 57 23 55 33Z" fill="#4A7C22" />
            <path d="M53 34C59 22 68 14 77 12C71 21 63 29 57 35Z" fill="#8DBA5E" />
          </g>
          <path d="M27 34Q50 22 73 34Q76 52 61 90Q53 110 50 115Q46 109 39 90Q24 52 27 34Z" fill="#F08A24" stroke="#A9520E" strokeWidth="2.5" strokeLinejoin="round" />
          <path d="M30 64h6M64 72h6M40 86h6M56 96h5M47 106h4" stroke="#C0661A" strokeWidth="2" strokeLinecap="round" />
          <path d="M31 62Q20 66 14 76" fill="none" stroke="#7A4A1E" strokeWidth="3" strokeLinecap="round" />
          <circle cx="13" cy="78" r="5" fill="#fff" stroke="#3a2a1a" strokeWidth="2" />
          <path d="M35 37Q41 33 47 37M53 37Q59 33 65 37" fill="none" stroke="#6B3410" strokeWidth="2" strokeLinecap="round" />
          <g className="gst-yeux">
            <ellipse cx="41" cy="47" rx="7" ry="8" fill="#fff" stroke="#3a2a1a" strokeWidth="2" />
            <ellipse cx="59" cy="47" rx="7" ry="8" fill="#fff" stroke="#3a2a1a" strokeWidth="2" />
            <circle cx="42.5" cy="49" r="3.6" fill="#2a1a10" />
            <circle cx="60.5" cy="49" r="3.6" fill="#2a1a10" />
            <circle cx="44" cy="47.5" r="1.2" fill="#fff" />
            <circle cx="62" cy="47.5" r="1.2" fill="#fff" />
          </g>
          <ellipse cx="33" cy="58" rx="4.5" ry="2.6" fill="#E0503A" opacity=".45" />
          <ellipse cx="67" cy="58" rx="4.5" ry="2.6" fill="#E0503A" opacity=".45" />
          <path d="M42 57Q50 69 58 57Z" fill="#6B2414" stroke="#3a2a1a" strokeWidth="2" strokeLinejoin="round" />
          <path d="M46 62Q50 65 54 62" fill="#E86A5A" />
        </symbol>
        <symbol id="c-arm" viewBox="0 0 100 120">
          <path d="M69 60Q80 56 86 45" fill="none" stroke="#7A4A1E" strokeWidth="3" strokeLinecap="round" />
          <circle cx="87" cy="41" r="5.5" fill="#fff" stroke="#3a2a1a" strokeWidth="2" />
          <ellipse cx="82" cy="42" rx="2.2" ry="3" fill="#fff" stroke="#3a2a1a" strokeWidth="1.6" />
        </symbol>
        <symbol id="glove" viewBox="0 0 30 30">
          <path d="M9 28Q4 16 9 9Q15 3 21 9Q26 16 21 28Z" fill="#fff" stroke="#3a2a1a" strokeWidth="2" />
          <ellipse cx="6" cy="17" rx="3" ry="4.5" fill="#fff" stroke="#3a2a1a" strokeWidth="2" transform="rotate(-25 6 17)" />
          <path d="M13 10v6M17 10v6" stroke="#3a2a1a" strokeWidth="1.4" strokeLinecap="round" />
        </symbol>
      </defs>
    </svg>
  )
}

/** Le visage seul, rogné comme dans la maquette (viewBox « 22 22 56 56 ») : l'avatar rond. */
export function VisageGaston() {
  return (
    <svg viewBox="22 22 56 56" aria-hidden="true" focusable="false">
      <use href="#c-body" width="100" height="120" />
    </svg>
  )
}

/** Gaston en pied, le bras qui peut saluer : l'état replié sur le bord de l'écran. */
export function GastonComplet({ salue = false, className = '' }) {
  return (
    <svg viewBox="0 0 100 120" overflow="visible" className={className} aria-hidden="true" focusable="false">
      <use href="#c-body" width="100" height="120" />
      <use
        href="#c-arm" width="100" height="120"
        className={salue ? 'gst-wave' : ''}
        style={{ transformOrigin: '69px 60px' }}
      />
    </svg>
  )
}

/** La main qui salue au coin de l'avatar « présent ». */
export function MainGaston() {
  return (
    <svg className="gst-hand" viewBox="0 0 30 30" aria-hidden="true" focusable="false">
      <use href="#glove" width="30" height="30" />
    </svg>
  )
}
