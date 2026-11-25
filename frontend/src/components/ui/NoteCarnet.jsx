import { Mic, Pencil, NotebookPen } from 'lucide-react'

/**
 * Note du carnet [US-352 / CA5] : papier crème, bordure `--paper-bd`, méta « Dicté · date · lieu »
 * ou « Écrit · date · lieu » en 11,5 px, texte en Kalam 16,5 px à l'encre `--ink`.
 *
 * Kalam n'écrit QUE ce que le jardinier a dicté ou écrit (CA6) : ce composant en est la porte.
 *
 * `dicte={null}` : on ne sait pas comment la note est arrivée (le serveur ne le garde pas, US-354) ;
 * la méta ne dit alors NI « Dicté » NI « Écrit », rien n'est inventé.
 */
export function NoteCarnet({ texte, dicte = false, date, lieu, className = '' }) {
  const inconnue = dicte === null
  const meta = [inconnue ? '' : (dicte ? 'Dicté' : 'Écrit'), date, lieu].filter(Boolean).join(' · ')
  const Icone = inconnue ? NotebookPen : (dicte ? Mic : Pencil)
  return (
    <div className={`note-carnet ${className}`} data-source={inconnue ? 'inconnue' : (dicte ? 'dicte' : 'ecrit')}>
      <div className="note-carnet-meta">
        <Icone size={13} aria-hidden="true" />
        <span>{meta}</span>
      </div>
      <div className="note-carnet-texte">{texte}</div>
    </div>
  )
}

export default NoteCarnet
