// [US-046 / CA2] Modal de sélection du potager actif.
// [US-048 / CA4] Complétée avec la saisie d'un code d'invitation — seul
// endroit accessible à tout moment (pas uniquement au premier onboarding,
// cf. views/Onboarding.jsx, US-058) pour rejoindre un potager supplémentaire.
import { useState, useRef, useEffect } from 'react'
import { X, Sprout, Check, Plus, Archive } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { api } from '../lib/api.js'
import ModalCreerPotager from './ModalCreerPotager.jsx'
import ParametresPotager from '../views/ParametresPotager.jsx'

// [US-054 / CA2] `focusCode` : ouverture depuis « Rejoindre un potager » du menu
// déroulant — le champ code prend le focus pour éviter un clic supplémentaire.
export default function PotagerSelector({ onClose, focusCode = false }) {
  const { potagers, activer, accepterInvitation } = usePotager()
  const [enCours, setEnCours] = useState(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState(null)
  const [rejoindre, setRejoindre] = useState(false)
  // [US-081 / CA8] Miroir du menu potager : le même composant de modale de
  // creation est accessible depuis cette vue « Tous mes potagers ».
  const [creation, setCreation] = useState(false)
  // [US-083 / CA6] Archivés masqués par défaut, chargés à la demande ; un clic
  // ouvre Paramètres en lecture (CA7) plutôt qu'une activation refusée (CA6).
  const [voirArchives, setVoirArchives] = useState(false)
  const [archives, setArchives] = useState([])
  const [chargementArchives, setChargementArchives] = useState(false)
  const [parametresPotagerId, setParametresPotagerId] = useState(null)
  const champCode = useRef(null)

  async function basculerVoirArchives() {
    const prochain = !voirArchives
    setVoirArchives(prochain)
    if (prochain && archives.length === 0) {
      setChargementArchives(true)
      try {
        const res = await api.potagers('tous')
        setArchives(res.potagers.filter((p) => p.etat === 'archive'))
      } finally {
        setChargementArchives(false)
      }
    }
  }

  useEffect(() => {
    if (focusCode) champCode.current?.focus()
  }, [focusCode])

  async function handleSelect(potagerId) {
    if (enCours) return
    setEnCours(potagerId)
    try {
      await activer(potagerId)
      // activer() recharge la page — pas besoin de fermer la modale manuellement
    } catch {
      setEnCours(null)
    }
  }

  async function handleRejoindre(e) {
    e.preventDefault()
    if (!code.trim() || rejoindre) return
    setRejoindre(true)
    setError(null)
    try {
      await accepterInvitation(code.trim())
      // accepterInvitation() recharge la page en cas de succès
    } catch (err) {
      setError(err.message)
      setRejoindre(false)
    }
  }

  return (
    <>
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-6"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-xs"
        style={{ background: 'var(--g-card)', border: '1px solid var(--g-brd)', borderRadius: 18, padding: 20 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="flex items-center gap-2 font-semibold text-g-pri">
            <Sprout size={16} /> Vos potagers
          </span>
          <button onClick={onClose} aria-label="Fermer" className="text-g-sec hover:text-g-pri">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-2">
          {potagers.map((p) => (
            <button
              key={p.id}
              onClick={() => handleSelect(p.id)}
              disabled={Boolean(enCours)}
              className="flex items-center justify-between"
              style={{
                background: p.actif ? 'var(--g-acc-dim)' : 'var(--g-sur)',
                border: '1px solid var(--g-brd)',
                borderRadius: 12,
                padding: '10px 12px',
                color: 'var(--g-pri)',
                opacity: enCours && enCours !== p.id ? 0.5 : 1,
              }}
            >
              <span>{p.nom}</span>
              {p.actif && <Check size={16} color="var(--g-acc)" />}
              {enCours === p.id && <span style={{ fontSize: 12, color: 'var(--g-sec)' }}>…</span>}
            </button>
          ))}
        </div>

        {/* [US-083 / CA6] Bascule d'affichage des potagers archivés. */}
        <button
          onClick={basculerVoirArchives}
          className="flex items-center gap-2 w-full"
          style={{
            marginTop: 8, background: 'transparent', border: 'none',
            padding: '6px 2px', color: 'var(--g-sec)', fontSize: 12,
          }}
        >
          <Archive size={13} />
          {chargementArchives
            ? 'Chargement…'
            : voirArchives ? 'Masquer les potagers archivés' : 'Voir les potagers archivés'}
        </button>
        {voirArchives && (
          <div className="flex flex-col gap-2" style={{ marginTop: 4 }}>
            {archives.map((p) => (
              <button
                key={p.id}
                onClick={() => setParametresPotagerId(p.id)}
                className="flex items-center justify-between"
                style={{
                  background: 'var(--g-sur)', border: '1px dashed var(--g-brd)',
                  borderRadius: 12, padding: '10px 12px', color: 'var(--g-sec)',
                }}
              >
                <span className="flex items-center gap-2"><Archive size={14} />{p.nom}</span>
                <span style={{ fontSize: 11 }}>archivé</span>
              </button>
            ))}
          </div>
        )}

        {/* [US-081 / CA8] Meme point d'entree que dans PotagerMenu, place apres
            la liste et avant l'adhesion par code — deux chemins, une modale. */}
        <button
          onClick={() => setCreation(true)}
          className="flex items-center gap-2 w-full"
          style={{
            marginTop: 10, background: 'var(--g-sur)', border: '1px dashed var(--g-brd)',
            borderRadius: 12, padding: '10px 12px', color: 'var(--g-pri)', fontSize: 13,
          }}
        >
          <Plus size={16} /> Créer un nouveau potager
        </button>

        <div style={{ borderTop: '1px solid var(--g-brd)', marginTop: 14, paddingTop: 14 }}>
          <p style={{ fontSize: 12, color: 'var(--g-sec)', marginBottom: 8 }}>
            Rejoindre un autre potager avec un code d'invitation
          </p>
          {error && <p style={{ color: 'var(--g-red)', fontSize: 13, marginBottom: 6 }}>{error}</p>}
          <form onSubmit={handleRejoindre} className="flex gap-2">
            <input
              ref={champCode}
              type="text"
              placeholder="Code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              style={{
                flex: 1, background: 'var(--g-sur)', border: '1px solid var(--g-brd)',
                color: 'var(--g-pri)', borderRadius: 10, padding: '6px 10px', fontSize: 13,
                fontFamily: 'monospace', letterSpacing: 1,
              }}
            />
            <button
              type="submit"
              disabled={rejoindre || !code.trim()}
              style={{
                background: 'var(--g-acc)', color: 'var(--g-card)',
                borderRadius: 10, padding: '6px 14px', fontSize: 13, fontWeight: 600,
                opacity: rejoindre ? 0.6 : 1,
              }}
            >
              {rejoindre ? '…' : 'Rejoindre'}
            </button>
          </form>
        </div>
      </div>
    </div>
    {/* Frere de l'overlay, jamais enfant : un clic hors de la modale de creation
        ne doit fermer que celle-ci, pas la vue « Tous mes potagers » derriere. */}
    {creation && <ModalCreerPotager onClose={() => setCreation(false)} />}
    {parametresPotagerId != null && (
      <ParametresPotager potagerId={parametresPotagerId} onClose={() => setParametresPotagerId(null)} />
    )}
    </>
  )
}
