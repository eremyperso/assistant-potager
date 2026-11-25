// [US-354 / CA1-CA3] Le Tableau de bord sur le socle : ce qu'il montre et ce que Gaston en dit.
// Rien n'est lu ici : la vue passe les lectures qu'elle a déjà (`GET /plan`, `GET /meteo`,
// `GET /historique`) ; ce fichier choisit et met en forme, sans React et sans modèle.
//
// Les quatre sections de la maquette sont les SEULES (D11) : « À faire aujourd'hui », « Récoltes
// possibles », « Météo · 3 jours », « Dernières notes du carnet ». Une section vide disparaît.
import { nomCulture, jourEnLettres } from './planDessus.js'
import { symboleDeCulture } from './pictosCultures.js'
import { jourCourt, jourDeSemaine, ligneAConfirmer, ligneALiberer } from './aujourdhui.js'
import { normaliserMot } from './motDeGaston.js'
import { ETAPE_EN_RECOLTE } from './etapes.js'

/** Nombre de jours que dit la météo, et fenêtre où un gel fait parler Gaston (CA1, CA3). */
export const JOURS_METEO = 3
export const JOURS_GEL = 3

/** Les deux notes montrées dans « Dernières notes du carnet » (CA1). */
export const NB_NOTES_ACCUEIL = 2

/** Récoltes possibles montrées avant « Tout voir » (la maquette en montre quatre). */
export const NB_RECOLTES_ACCUEIL = 4

const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un)
const JOURS_NOMS = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
const NOMBRES = ['aucune', 'une', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf']
const enLettres = (n) => NOMBRES[n] ?? String(n)

/** « 3 », ou « 4 · 2 kg » : jamais « undefined ». */
const lieuDeCulture = (parcelle, rang) => [parcelle, rang ? `rang ${rang}` : ''].filter(Boolean).join(' · ')

// ── À faire aujourd'hui (CA1) ───────────────────────────────────────────────────────────────

/**
 * Les lignes de « À faire aujourd'hui · n » : les étapes dues (levées, plantations… à confirmer) puis
 * les rangs à libérer, dans cet ordre. Chaque ligne porte sa pastille d'étape (`etape`, la clé brute
 * du serveur) et la culture qu'ouvre un appui.
 */
export function aFaireAujourdhui(plan) {
  const t = plan?.taches_du_jour || {}
  const dues = (t.a_confirmer || []).map((l) => {
    const mise = ligneAConfirmer(l)
    return {
      cle: mise.cle, type: 'due', etape: l.etape || null, emoji: mise.emoji, titre: mise.nom,
      detail: [mise.detail, mise.lieu].filter(Boolean).join(' · '), du: true,
      culture: l.culture, nomAccessible: mise.nomAccessible, selection: mise.selection,
    }
  })
  const aLiberer = (t.a_liberer || []).map((l) => {
    const mise = ligneALiberer(l)
    const rang = (l.etapes?.numeros_rangs || []).find((r) => Number.isInteger(r)) ?? null
    return {
      cle: mise.cle, type: 'liberer', etape: 'terminee', emoji: mise.emoji,
      titre: `Libérer ${rang ? `le rang ${rang}` : 'le rang'}${l.parcelle ? ` · ${l.parcelle}` : ''}`,
      detail: `${mise.nom} · ${mise.detail.charAt(0).toLowerCase()}${mise.detail.slice(1)}`, du: false,
      culture: l.culture, nomAccessible: mise.nomAccessible, selection: mise.selection,
    }
  })
  return [...dues, ...aLiberer]
}

// ── Récoltes possibles (CA1) ────────────────────────────────────────────────────────────────

/**
 * Les cultures en place à l'étape « En récolte », hors pépinière : une ligne par culture, avec son
 * emplacement en sous-titre. « Tout voir » ouvre Cultures.
 */
export function recoltesPossibles(plan) {
  const lignes = []
  for (const p of plan?.parcelles || []) {
    if (p.est_pepiniere) continue
    for (const c of p.cultures || []) {
      if (c.etapes?.etape !== ETAPE_EN_RECOLTE) continue
      const rangs = (c.numeros_rangs || []).filter((r) => Number.isInteger(r))
      const rang = rangs.length ? Math.min(...rangs) : null
      lignes.push({
        cle: `r-${p.id}-${c.culture}-${c.variete || ''}`,
        etape: ETAPE_EN_RECOLTE,
        emoji: symboleDeCulture(c.culture, c.variete || ''),
        titre: nomCulture(c.culture, c.variete),
        detail: lieuDeCulture(p.nom, rang),
        culture: c.culture,
        // [US-355 / CA1] La fiche commune s'ouvre sur CETTE culture, à CETTE place.
        selection: { parcelleId: p.id, parcelle: p.nom, culture: c.culture, variete: c.variete || null, rang },
        nomAccessible: `${nomCulture(c.culture, c.variete)}, en récolte, ${lieuDeCulture(p.nom, rang)}`,
      })
    }
  }
  return lignes
}

// ── Météo · 3 jours (CA1) ───────────────────────────────────────────────────────────────────

const unJourAvant = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) - 1)).toISOString().slice(0, 10) : ''
}

/**
 * Les jours que sert `GET /meteo` : AUJOURD'HUI (les `temp_min` / `temp_max` du niveau supérieur, ceux de la journée
 * entière) puis `previsions`, qui COMMENCE À DEMAIN. La date d'aujourd'hui s'en déduit : la veille du premier jour prévu.
 */
function joursDeMeteo(meteo) {
  const prevus = meteo?.previsions || []
  const aujourdhui = {
    date: unJourAvant(String(prevus[0]?.date || '').slice(0, 10)),
    temp_min: meteo?.temp_min, temp_max: meteo?.temp_max, emoji: meteo?.emoji, label: meteo?.label,
  }
  return [aujourdhui, ...prevus]
}

/**
 * Les trois jours : aujourd'hui, demain, après-demain — chacun avec le maximum et le minimum de SA journée pour la ville
 * du potager (Open-Meteo, fuseau du potager). Le gel est repéré.
 */
export function meteoTroisJours(meteo, aujourdhui = null) {
  if (!meteo || meteo.localisation_manquante) return []
  const jours = joursDeMeteo(meteo).slice(0, JOURS_METEO)
  return jours.map((p, i) => {
    const iso = String(p.date || '').slice(0, 10)
    const nom = i === 0 ? 'Aujourd’hui' : JOURS_NOMS[new Date(`${iso}T12:00:00Z`).getUTCDay()]
    const mini = typeof p.temp_min === 'number' ? Math.round(p.temp_min) : null
    const maxi = typeof p.temp_max === 'number' ? Math.round(p.temp_max) : null
    return {
      cle: iso || String(i),
      nom,
      emoji: p.emoji || '',
      maxi, mini,
      libelle: `${maxi ?? '—'}° / ${mini ?? '—'}°`,
      texte: mini != null && mini <= 0 ? 'Gel' : (p.label || p.libelle || ''),
      gel: mini != null && mini <= 0,
    }
  })
}

/** Le premier gel annoncé dans les trois jours : `{ jour: 'samedi', mini: -2 }` ou null. */
export function gelAnnonce(meteo) {
  if (!meteo || meteo.localisation_manquante) return null
  const p = (meteo.previsions || []).slice(0, JOURS_GEL).find((j) => typeof j.temp_min === 'number' && j.temp_min <= 0)
  if (!p) return null
  const iso = String(p.date || '').slice(0, 10)
  return { jour: jourDeSemaine(iso), iso, mini: Math.round(p.temp_min) }
}

const signe = (n) => (n < 0 ? `−${Math.abs(n)}` : String(n))

// ── Dernières notes du carnet (CA1) ─────────────────────────────────────────────────────────

/** Une date ISO au format de la maquette : « aujourd'hui », « sam. 21 nov. ». */
export function dateDeNote(iso, aujourdhui) {
  const jour = String(iso || '').slice(0, 10)
  if (!jour) return ''
  if (jour === aujourdhui) return 'aujourd’hui'
  return `${jourDeSemaine(jour).slice(0, 3)}. ${jourCourt(jour)}`
}

/** Les notes (observations avec un texte) les plus récentes, au plus `NB_NOTES_ACCUEIL`. */
export function dernieresNotes(evenements, aujourdhui, max = NB_NOTES_ACCUEIL) {
  return (evenements || [])
    .filter((e) => e.type_action === 'observation' && String(e.commentaire || '').trim())
    .slice(0, max)
    .map((e) => ({
      cle: `n-${e.id}`,
      texte: String(e.commentaire).trim(),
      date: dateDeNote(e.date, aujourdhui),
      lieu: [nomCulture(e.culture, null)].filter(Boolean).join(''),
    }))
}

// ── Le Mot de Gaston (CA3) ──────────────────────────────────────────────────────────────────

/**
 * Gel annoncé dans les 3 jours > levées dues > rien. Les « levées dues » sont les étapes à confirmer
 * du plan : on les nomme comme le serveur les compte, sans en inventer.
 *
 * « Voilez la mâche… » demande de savoir quelles cultures craignent le gel : le référentiel ne le dit
 * pas, la phrase n'est donc pas écrite (rien n'est inventé).
 */
export function motDuTableauDeBord({ meteo = null, plan = null } = {}) {
  const gel = gelAnnonce(meteo)
  const dues = (plan?.taches_du_jour?.a_confirmer || []).length
  const levees = dues > 0
    ? ` ${enLettres(dues).replace(/^./, (c) => c.toUpperCase())} ${pluriel(dues, 'culture attend', 'cultures attendent')} votre œil.`
    : ''
  if (gel) {
    return normaliserMot({
      texte: `**Gel annoncé ${gel.jour} (${signe(gel.mini)} °C).**${levees}`.replace(/\*\*\s*$/, '**'),
      actions: [
        ...(dues > 0 ? [{ libelle: pluriel(dues, 'Voir la levée', 'Voir les levées'), vue: 'cultures' }] : []),
        { libelle: 'Noter', noter: true },
      ],
    })
  }
  if (dues > 0) {
    return normaliserMot({
      texte: `**${dues} ${pluriel(dues, 'étape attend', 'étapes attendent')} votre œil.** Dites-moi ce que vous voyez au potager.`,
      actions: [
        { libelle: pluriel(dues, 'Voir la culture', 'Voir les cultures'), vue: 'cultures' },
        { libelle: 'Noter', noter: true },
      ],
    })
  }
  return null
}

/** La ligne de contexte de l'en-tête : « Lundi 23 novembre · 8 °C, ciel couvert ». */
export function contexteTableauDeBord(iso, meteo = null) {
  const date = [jourDeSemaine(iso), jourEnLettres(iso)].filter(Boolean).join(' ')
  const temp = meteo && !meteo.localisation_manquante ? (meteo.temp_actuelle ?? meteo.temp_max) : null
  const ciel = meteo?.label ? meteo.label.toLowerCase() : ''
  const air = [temp != null ? `${Math.round(temp)} °C` : '', ciel].filter(Boolean).join(', ')
  return [date, air].filter(Boolean).join(' · ')
}
