// [US-359 / CA5] « Aide de la vue » : la section du guide propre à l'écran, dans une fenêtre.
import { Modal, Btn } from './ui'
import { SECTION_GUIDE } from '../lib/aideDesVues.js'

/**
 * `aide` : une entrée de `AIDE_PAR_VUE`. « Demander à Gaston » ferme la fenêtre et ouvre Gaston avec la
 * question pré-écrite dans son champ (elle n'est pas envoyée d'office).
 */
export default function AideVue({ aide, onFermer, onDemander }) {
  return (
    <Modal title={`Aide · ${aide.titre}`} sub={`Guide · ${SECTION_GUIDE}`} onClose={onFermer} width={480}
      foot={(
        <>
          <Btn onClick={onFermer}>Fermer</Btn>
          <Btn kind="primary" onClick={() => onDemander(aide.question)}>Demander à Gaston</Btn>
        </>
      )}
    >
      <p className="mb-2 text-[12.5px] font-bold text-txt2">{aide.section}</p>
      <ul className="flex list-disc flex-col gap-2 pl-5 text-[13.5px] leading-snug text-txt">
        {aide.points.map((p) => <li key={p}>{p}</li>)}
      </ul>
    </Modal>
  )
}
