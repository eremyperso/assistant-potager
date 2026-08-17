// [US-074 / CA5] Modale « Modifier le potager » — seul moyen de localiser (ou
// corriger) un potager après sa création, réservée au owner (garde côté
// serveur : PATCH /potagers/{id} → 403 sinon, cf. modifier_potager).
import { useState } from 'react'
import { MapPinned } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { Modal, Field, VilleSearch, Btn } from './ui'

export default function ModalModifierPotager({ potager, onClose }) {
  const { modifierPotager } = usePotager()
  const [nom, setNom] = useState(potager.nom)
  // [CA6] Un potager sans localisation reste `null` — jamais de "0, 0" inventé.
  const [localisation, setLocalisation] = useState(
    potager.latitude != null && potager.longitude != null
      ? { ville: potager.ville || '', latitude: potager.latitude, longitude: potager.longitude }
      : null
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (loading || !nom.trim()) return
    setLoading(true)
    setError(null)
    try {
      await modifierPotager(potager.id, {
        nom: nom.trim(),
        ville: localisation?.ville,
        latitude: localisation?.latitude,
        longitude: localisation?.longitude,
      })
      onClose()
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <Modal title="Modifier le potager" icon={MapPinned} sub={potager.nom} onClose={onClose} width={420}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
        <Field
          id="modifier-potager-nom"
          label="Nom du potager"
          required
          value={nom}
          onChange={(e) => setNom(e.target.value)}
        />
        {/* [CA1, CA7] Recherche facultative — rien n'empêche d'enregistrer sans ville. */}
        <VilleSearch
          id="modifier-potager-ville"
          label="Ville"
          value={localisation}
          onSelect={setLocalisation}
          placeholder="Rechercher une ville…"
          hint="Facultatif — sert à personnaliser la météo du potager."
        />
        {error && <p className="text-[13px] text-red">{error}</p>}
        <Btn type="submit" kind="primary" disabled={loading || !nom.trim()} className="w-full justify-center">
          {loading ? 'Enregistrement…' : 'Enregistrer'}
        </Btn>
      </form>
    </Modal>
  )
}
