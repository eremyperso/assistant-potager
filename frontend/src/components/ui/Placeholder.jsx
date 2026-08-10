import { Construction } from 'lucide-react'
import { Card } from './Card.jsx'

/**
 * Écran « à venir » [US-053 / CA6].
 *
 * Rend explicite qu'une entrée de navigation est bien en place mais que son
 * contenu arrive dans un lot ultérieur — jamais de page blanche ni de lien mort.
 */
export function Placeholder({ title, body, icon: Icon = Construction }) {
  return (
    <Card className="text-center" pad="px-6 py-14">
      <div className="w-16 h-16 rounded-[20px] bg-brand-soft flex items-center justify-center mx-auto mb-4">
        <Icon size={30} className="text-brand" />
      </div>
      <div className="font-serif text-[19px] font-semibold text-txt">{title}</div>
      <p className="text-[13.5px] text-txt2 mt-2 max-w-[400px] mx-auto leading-relaxed">{body}</p>
      <p className="text-[12px] text-txt3 mt-4">Cet écran sera disponible dans une prochaine version.</p>
    </Card>
  )
}

export default Placeholder
