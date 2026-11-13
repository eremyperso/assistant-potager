// [US-321] Langage visuel des étapes — `npm test`.
//
// Ce qui se vérifie ici : la table étape → couleur, pictogramme, libellé (CA6), les cinq
// états d'un segment (V3-V6), la légende (CA4), les contrastes AA encre / fond dans les
// deux thèmes, trame comprise (CA5), les tokens clair + sombre (CA2) et l'absence de
// couleur en dur dans le composant (CA2, CA3).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  ETAPES, FAMILLES, etape, libelleEtape, classeEtape, jetonFond, jetonEncre,
  variante, segmentDeLigne, classesSegment, libelleAccessible, entreesLegende,
  VARIANTES, VARIANTE_PLEIN, VARIANTE_PREVU, VARIANTE_A_CONFIRMER, VARIANTE_A_LIBERER, VARIANTE_LIBRE,
  PICTO_GRAINE, PICTO_LEVEE, PICTO_PLANT, PICTO_TIGE, PICTO_FLEUR, PICTO_PANIER, PICTO_COCHE,
} from './etapes.js'

const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8')
const composant = readFileSync(new URL('../components/ui/EtapeCulture.jsx', import.meta.url), 'utf8')

// ── CA6 : la table ──────────────────────────────────────────────────────────────

test('[CA6, V1, V2] sept étapes dans l’ordre du cycle, un pictogramme chacune', () => {
  assert.deepEqual(ETAPES.map((e) => e.cle),
    ['semee', 'levee', 'plantee', 'croissance', 'fleur', 'en_recolte', 'terminee'])
  assert.deepEqual(ETAPES.map((e) => e.picto),
    [PICTO_GRAINE, PICTO_LEVEE, PICTO_PLANT, PICTO_TIGE, PICTO_FLEUR, PICTO_PANIER, PICTO_COCHE])
  assert.equal(new Set(ETAPES.map((e) => e.picto)).size, 7)
})

test('[V1] six familles de couleur : Levé et Planté partagent le vert tendre', () => {
  assert.equal(FAMILLES.length, 6)
  assert.equal(new Set(ETAPES.map((e) => e.famille)).size, 6)
  assert.equal(etape('levee').famille, etape('plantee').famille)
  assert.notEqual(etape('levee').picto, etape('plantee').picto)
})

test('[CA6] les libellés sont ceux du serveur pour les cinq étapes de US-320', () => {
  assert.equal(libelleEtape('semee'), 'Semé')
  assert.equal(libelleEtape('levee'), 'Levé')
  assert.equal(libelleEtape('plantee'), 'Planté')
  assert.equal(libelleEtape('en_recolte'), 'En récolte')
  assert.equal(libelleEtape('terminee'), 'Terminé')
})

test('une étape inconnue ne reçoit ni libellé ni classe de repli', () => {
  assert.equal(etape('inconnue'), null)
  assert.equal(libelleEtape('inconnue'), '')
  assert.equal(classeEtape('inconnue'), '')
  assert.equal(segmentDeLigne({ etapes: { etape: 'inconnue' } }), null)
  assert.equal(segmentDeLigne({}), null)
  assert.equal(segmentDeLigne(null), null)
})

// ── V3 à V6 : les cinq états ────────────────────────────────────────────────────

test('[V3] validée = plein ; prévue = hachuré ; non notée = hachuré', () => {
  assert.equal(variante({ statut: 'validee' }), VARIANTE_PLEIN)
  assert.equal(variante({ statut: 'prevue' }), VARIANTE_PREVU)
  assert.equal(variante({ statut: 'non_notee' }), VARIANTE_PREVU)
})

test('[V4] date atteinte : pastille « à confirmer », seulement sur du prévu', () => {
  assert.equal(variante({ statut: 'prevue', aConfirmer: true }), VARIANTE_A_CONFIRMER)
  assert.equal(variante({ statut: 'validee', aConfirmer: true }), VARIANTE_PLEIN)
})

test('[V5, V6] à libérer et libre l’emportent sur le statut', () => {
  assert.equal(variante({ statut: 'validee', aLiberer: true }), VARIANTE_A_LIBERER)
  assert.equal(variante({ aLiberer: true, libre: true }), VARIANTE_LIBRE)
  assert.deepEqual([...VARIANTES].sort(), ['a_confirmer', 'a_liberer', 'libre', 'plein', 'prevu'])
})

test('[Gherkin 1] la fève au stade Levé, prévue, date atteinte', () => {
  const s = segmentDeLigne({ etapes: { etape: 'levee', etape_statut: 'prevue', a_confirmer: true } })
  assert.deepEqual(s, { etape: 'levee', variante: VARIANTE_A_CONFIRMER })
  assert.equal(classesSegment(s.etape, s.variante), 'etape-levee etape-prevue')
  assert.equal(etape('levee').picto, PICTO_LEVEE)
  assert.equal(libelleAccessible(s.etape, s.variante), 'Levé, prévu, à confirmer')
})

test('[Gherkin 2, V8] quatre états distinguables sans couleur : trame, contour, mot', () => {
  assert.equal(classesSegment('en_recolte', VARIANTE_PLEIN), 'etape-recolte')
  assert.match(classesSegment('en_recolte', VARIANTE_PREVU), /etape-prevue/)
  assert.match(classesSegment(null, VARIANTE_A_LIBERER), /etape-prevue/)
  assert.equal(classesSegment(null, VARIANTE_LIBRE), 'etape-libre')
  const noms = [
    libelleAccessible('en_recolte', VARIANTE_PLEIN), libelleAccessible('en_recolte', VARIANTE_PREVU),
    libelleAccessible(null, VARIANTE_A_LIBERER), libelleAccessible(null, VARIANTE_LIBRE),
  ]
  assert.equal(new Set(noms).size, 4)
  assert.match(css, /\.etape-prevue\s*\{[^}]*repeating-linear-gradient\(45deg/)
  assert.match(css, /\.etape-libre\s*\{[^}]*dotted/)
})

// ── CA4 : la légende ────────────────────────────────────────────────────────────

test('[CA4] légende : sept étapes puis prévu, à confirmer aujourd’hui, rang libre', () => {
  assert.deepEqual(entreesLegende().map((e) => e.libelle), [
    'Semé', 'Levé', 'Planté', 'En croissance', 'En fleur', 'En récolte', 'Terminé',
    'hachuré : prévu, à confirmer', 'à confirmer aujourd’hui', 'rang libre',
  ])
})

test('[CA4] légende compacte : six étapes, Levé et Planté fusionnés', () => {
  const l = entreesLegende({ compact: true })
  assert.equal(l.filter((e) => e.type === 'etape').length, 6)
  assert.ok(l.some((e) => e.libelle === 'Levé / Planté'))
  assert.ok(!l.some((e) => e.libelle === 'Planté'))
  assert.equal(l.length, 9)
})

// ── CA2, CA5 : tokens et contrastes ─────────────────────────────────────────────

/** Le bloc de déclarations (clair ou sombre) qui porte les jetons d'étape. */
function jetons(theme) {
  const re = new RegExp(`${theme === 'sombre' ? '\\.dark' : ':root'}\\s*\\{([\\s\\S]*?)\\n  \\}`, 'g')
  for (const m of css.matchAll(re)) if (m[1].includes('--etape-semee:')) return m[1]
  throw new Error(`jetons ${theme} introuvables`)
}
const valeur = (bloc, nom) => {
  const m = bloc.match(new RegExp(`${nom}:\\s*([^;]+);`))
  assert.ok(m, `${nom} absent`)
  return m[1].trim()
}
const canaux = (v) => {
  const rgba = v.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/)
  if (rgba) return { rgb: rgba.slice(1, 4).map(Number), a: Number(rgba[4]) }
  return { rgb: [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16)), a: 1 }
}
const luminance = (rgb) => {
  const [r, g, b] = rgb.map((c) => c / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contraste = (a, b) => {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}
const melange = (fond, dessus) => fond.map((c, i) => Math.round(c * (1 - dessus.a) + dessus.rgb[i] * dessus.a))

for (const theme of ['clair', 'sombre']) {
  test(`[CA2] ${theme} : les six familles ont un fond et une encre`, () => {
    const bloc = jetons(theme)
    for (const f of FAMILLES) {
      valeur(bloc, jetonFond(f))
      valeur(bloc, jetonEncre(f))
    }
    valeur(bloc, '--etape-trame')
    valeur(bloc, '--etape-pastille')
  })

  test(`[CA5] ${theme} : contraste AA du pictogramme et du libellé, plein et hachuré`, () => {
    const bloc = jetons(theme)
    const trame = canaux(valeur(bloc, '--etape-trame'))
    for (const f of FAMILLES) {
      const fond = canaux(valeur(bloc, jetonFond(f))).rgb
      const encre = canaux(valeur(bloc, jetonEncre(f))).rgb
      assert.ok(contraste(fond, encre) >= 4.5, `${f} plein ${contraste(fond, encre).toFixed(2)}`)
      const raye = melange(fond, trame)
      assert.ok(contraste(raye, encre) >= 4.5, `${f} hachuré ${contraste(raye, encre).toFixed(2)}`)
    }
  })

  test(`[CA2] ${theme} : les six familles sont distinctes entre elles`, () => {
    const bloc = jetons(theme)
    assert.equal(new Set(FAMILLES.map((f) => valeur(bloc, jetonFond(f)))).size, 6)
  })

  test(`[V7] ${theme} : la récolte est plus saturée que le sable, le vert tendre et le gris`, () => {
    const bloc = jetons(theme)
    const sat = (f) => {
      const [r, g, b] = canaux(valeur(bloc, jetonFond(f))).rgb
      const mx = Math.max(r, g, b)
      return mx === 0 ? 0 : (mx - Math.min(r, g, b)) / mx
    }
    for (const f of ['semee', 'levee', 'terminee']) assert.ok(sat('recolte') > sat(f), f)
  })
}

test('[CA2] une classe CSS par famille, et aucune couleur en dur dans le composant', () => {
  for (const f of FAMILLES) assert.match(css, new RegExp(`\\.etape-${f}\\s*\\{`))
  assert.doesNotMatch(composant, /#[0-9a-fA-F]{3,8}\b/)
  assert.doesNotMatch(composant, /rgba?\(/)
})

// ── CA3 : des SVG, pas des emoji ────────────────────────────────────────────────

test('[CA3] pictogrammes : SVG teinté par currentColor, aucun emoji, sept dessinés', () => {
  assert.match(composant, /stroke="currentColor"/)
  assert.doesNotMatch(composant, /\p{Extended_Pictographic}/u)
  for (const nom of ['GRAINE', 'LEVEE', 'PLANT', 'TIGE', 'FLEUR', 'PANIER', 'COCHE']) {
    assert.ok(composant.includes(`picto === PICTO_${nom}`), nom)
  }
})

test('[CA1] composant réutilisable : conteneur @container, libellé dès qu’il y a la place', () => {
  assert.ok(composant.includes('@' + 'container'))
  assert.match(composant, /@\[5\.5rem\]:inline/)
  assert.doesNotMatch(composant, /\b(sm|md|lg|nav):/)
})
