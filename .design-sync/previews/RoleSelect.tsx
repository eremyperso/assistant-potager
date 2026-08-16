import { useState } from 'react'
import { Pencil, Eye } from 'lucide-react'
import { RoleSelect } from 'assistant-potager-dashboard'

// Options réelles portées de `GestionMembres.jsx` (ROLES_INVITABLES) — le
// composant n'a pas de valeur par défaut pour `options`/`value`, donc une
// preview sans données réalistes plante au montage.
const ROLES_INVITABLES = [
  { value: 'editor', icon: Pencil, sub: 'Saisit récoltes, semis et cultures' },
  { value: 'lecteur', icon: Eye, sub: 'Consulte sans rien modifier' },
]

export function Editeur() {
  const [role, setRole] = useState('editor')
  return <RoleSelect value={role} options={ROLES_INVITABLES} onChange={setRole} />
}

export function LectureSeule() {
  const [role, setRole] = useState('lecteur')
  return <RoleSelect value={role} options={ROLES_INVITABLES} onChange={setRole} />
}
