// Remplace le `LogoMark` local de `views/Auth.jsx` et `views/Onboarding.jsx` : mêmes props
// (`light` = posé sur le fond vert), même gabarit (34 px + nom en Lora gras 18 px), le médaillon
// de la marque à la place de la feuille Lucide.
//
// Le nom reste du texte HTML (police `font-serif` de l'appli) : rien à charger de plus. Il est
// paramétrable pour le jour où le nom de la marque change.
import MedaillonBulle from './MedaillonBulle.jsx'

export default function LogoMark({ light = false, nom = 'Les bons gestes' }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <MedaillonBulle taille={34} variante={light ? 'inverse' : 'auto'} />
      <span className={`font-serif text-[18px] font-bold tracking-tight whitespace-nowrap ${light ? 'text-white' : 'text-txt'}`}>
        {nom}
      </span>
    </span>
  )
}
