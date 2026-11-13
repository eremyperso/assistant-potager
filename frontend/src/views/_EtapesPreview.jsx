import { useState } from 'react'
import { EtiquetteEtape, SegmentEtape, LegendeEtapes } from '../components/ui'
import {
  ETAPES, VARIANTE_PLEIN, VARIANTE_PREVU, VARIANTE_A_CONFIRMER, VARIANTE_A_LIBERER, VARIANTE_LIBRE,
  ETAPE_LEVEE, ETAPE_EN_RECOLTE,
} from '../lib/etapes.js'

/**
 * Page de contrôle visuel du langage des étapes [US-321 / CA7] — `/etapes`.
 * Rejoue les sept étapes pleines et prévues, la pastille « à confirmer », le gris
 * « à libérer » et le rang libre, en trois largeurs de segment (le libellé s'écrit
 * dès qu'il y a la place), avec bascule thème sombre et niveaux de gris (V8).
 * Non référencée par la navigation applicative.
 */
export default function EtapesPreview() {
  const [sombre, setSombre] = useState(false)
  const [gris, setGris] = useState(false)
  const basculer = () => {
    document.documentElement.classList.toggle('dark', !sombre)
    setSombre(!sombre)
  }
  return (
    <div className="min-h-dvh bg-bg p-4 flex flex-col gap-6 max-w-3xl mx-auto"
      style={gris ? { filter: 'grayscale(1)' } : undefined}>
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-2xl font-bold text-txt mr-auto">Étapes — US-321</h1>
        <button type="button" onClick={basculer}
          className="text-[12px] font-semibold px-3 py-1 rounded-full border border-border bg-card text-txt">
          {sombre ? 'Thème clair' : 'Thème sombre'}
        </button>
        <button type="button" onClick={() => setGris(!gris)}
          className="text-[12px] font-semibold px-3 py-1 rounded-full border border-border bg-card text-txt">
          {gris ? 'Couleurs' : 'Niveaux de gris'}
        </button>
      </header>

      <Section titre="Étiquettes — validées">
        <div className="flex flex-wrap gap-2">
          {ETAPES.map((e) => <EtiquetteEtape key={e.cle} etape={e.cle} />)}
        </div>
      </Section>

      <Section titre="Étiquettes — prévues (hachurées)">
        <div className="flex flex-wrap gap-2">
          {ETAPES.map((e) => <EtiquetteEtape key={e.cle} etape={e.cle} prevue />)}
        </div>
      </Section>

      <Section titre="Segments — pleins, puis prévus (160 px)">
        <div className="grid grid-cols-2 gap-2 w-[336px] max-w-full">
          {ETAPES.map((e) => <SegmentEtape key={e.cle} etape={e.cle} variante={VARIANTE_PLEIN} />)}
          {ETAPES.map((e) => <SegmentEtape key={e.cle} etape={e.cle} variante={VARIANTE_PREVU} />)}
        </div>
      </Section>

      <Section titre="Cas du plan : à confirmer, à libérer, libre">
        <div className="grid grid-cols-3 gap-2">
          <SegmentEtape etape={ETAPE_LEVEE} variante={VARIANTE_A_CONFIRMER} />
          <SegmentEtape etape={ETAPE_EN_RECOLTE} variante={VARIANTE_A_CONFIRMER} />
          <SegmentEtape variante={VARIANTE_A_LIBERER} />
          <SegmentEtape variante={VARIANTE_LIBRE} />
        </div>
      </Section>

      <Section titre="Largeurs : pictogramme seul (36 px), puis avec libellé (96 px, 200 px)">
        <div className="flex flex-col gap-2">
          {[36, 96, 200].map((l) => (
            <div key={l} style={{ width: l }}>
              <SegmentEtape etape={ETAPE_EN_RECOLTE} variante={VARIANTE_PLEIN} />
            </div>
          ))}
        </div>
      </Section>

      <Section titre="Légende">
        <LegendeEtapes />
        <h3 className="text-[11.5px] font-semibold text-txt3 mt-3">Compacte (mobile, six étapes)</h3>
        <LegendeEtapes compact />
      </Section>
    </div>
  )
}

function Section({ titre, children }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">{titre}</h2>
      {children}
    </section>
  )
}
