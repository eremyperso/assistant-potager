import { useState, useEffect, useRef } from 'react'
import { MapPin, Loader2 } from 'lucide-react'

// [US-074 / CA1] Géocodage Open-Meteo — même fournisseur que utils/meteo.py,
// gratuit et sans clé, CORS ouvert : appelé directement depuis le navigateur,
// sans passer par le backend (pas de donnée sensible, rien à proxifier).
const GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'

/**
 * Champ de recherche de ville réutilisable du design system [US-074].
 *
 * Composant contrôlé : `value` est soit `null` (rien de retenu), soit
 * `{ ville, latitude, longitude }` — la valeur que le parent transmettra telle
 * quelle à `POST /potagers` ou `PATCH /potagers/{id}`. Toute frappe qui
 * s'écarte de la ville déjà retenue invalide la sélection (`onSelect(null)`)
 * pour ne jamais soumettre un libellé qui ne correspond plus aux coordonnées
 * mémorisées.
 *
 * [CA7] Recherche vide, sans résultat ou en échec réseau : un message clair
 * s'affiche, jamais bloquant — le champ reste simplement vide, l'appelant
 * décide de soumettre son formulaire sans localisation.
 */
export function VilleSearch({ id, label = 'Ville', value, onSelect, placeholder = 'Rechercher une ville…', hint }) {
  const [query, setQuery] = useState(value?.ville || '')
  const [resultats, setResultats] = useState([])
  const [ouvert, setOuvert] = useState(false)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState(null)
  const debounceRef = useRef(null)
  const conteneurRef = useRef(null)

  useEffect(() => {
    setQuery(value?.ville || '')
  }, [value?.ville])

  useEffect(() => {
    function auClicExterieur(e) {
      if (conteneurRef.current && !conteneurRef.current.contains(e.target)) setOuvert(false)
    }
    document.addEventListener('mousedown', auClicExterieur)
    return () => document.removeEventListener('mousedown', auClicExterieur)
  }, [])

  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current) }, [])

  async function rechercher(q) {
    setChargement(true)
    try {
      const params = new URLSearchParams({ name: q, count: '6', language: 'fr', format: 'json' })
      const res = await fetch(`${GEOCODING_URL}?${params}`)
      if (!res.ok) throw new Error('Erreur réseau')
      const body = await res.json()
      setResultats(body.results || [])
      setErreur(null)
    } catch {
      setResultats([])
      setErreur("Recherche impossible pour l'instant — réessayez plus tard.")
    } finally {
      setChargement(false)
      setOuvert(true)
    }
  }

  function handleChange(texte) {
    setQuery(texte)
    if (value) onSelect(null)
    if (debounceRef.current) clearTimeout(debounceRef.current)

    const q = texte.trim()
    if (q.length < 2) {
      setResultats([])
      setErreur(null)
      setOuvert(false)
      return
    }
    debounceRef.current = setTimeout(() => rechercher(q), 350)
  }

  function choisir(r) {
    const libelle = [r.name, r.admin1, r.country].filter(Boolean).join(', ')
    setQuery(libelle)
    setResultats([])
    setOuvert(false)
    onSelect({ ville: libelle, latitude: r.latitude, longitude: r.longitude })
  }

  return (
    <div ref={conteneurRef} className="relative">
      {label && (
        <label htmlFor={id} className="flex items-center gap-1.5 text-[12.5px] font-semibold text-txt2 mb-1.5">
          {label}
        </label>
      )}
      <div className="flex items-center gap-2 bg-card border border-border rounded-[11px] h-[46px] px-3 has-[input:focus]:border-brand has-[input:focus]:ring-[3px] has-[input:focus]:ring-brand-soft transition-shadow">
        <MapPin size={16} className="text-txt3 shrink-0" />
        <input
          id={id}
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => resultats.length > 0 && setOuvert(true)}
          placeholder={placeholder}
          autoComplete="off"
          className="flex-1 min-w-0 h-full border-none outline-none bg-transparent text-[14.5px] text-txt placeholder:text-txt3"
        />
        {chargement && <Loader2 size={15} className="animate-spin text-txt3 shrink-0" />}
      </div>
      {hint && !ouvert && <div className="text-[11.5px] text-txt3 mt-1">{hint}</div>}

      {ouvert && (
        <div className="absolute z-50 mt-1.5 w-full bg-card border border-border rounded-2xl shadow-[0_18px_46px_rgba(12,18,8,.26)] overflow-hidden max-h-64 overflow-y-auto">
          {erreur ? (
            <div className="px-3.5 py-3 text-[12.5px] text-txt3">{erreur}</div>
          ) : resultats.length === 0 ? (
            <div className="px-3.5 py-3 text-[12.5px] text-txt3">Aucune ville trouvée pour « {query.trim()} ».</div>
          ) : (
            resultats.map((r) => (
              <button
                key={`${r.id ?? r.name}-${r.latitude}-${r.longitude}`}
                type="button"
                onClick={() => choisir(r)}
                className="w-full flex flex-col items-start px-3.5 py-2.5 text-left hover:bg-card-alt transition-colors"
              >
                <span className="text-[13.5px] font-medium text-txt">{r.name}</span>
                <span className="text-[11.5px] text-txt3">
                  {[r.admin1, r.country].filter(Boolean).join(', ')}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default VilleSearch
