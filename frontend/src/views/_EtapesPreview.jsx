import { useState } from 'react'
import {
  EtiquetteEtape, SegmentEtape, LegendeEtapes, PastilleEtape, PuceEtape, CalendrierAnnee, NoteCarnet,
  LegendeCommune, InfobulleEtapes,
} from '../components/ui'
import { moisDeChaine } from '../lib/calendrierAnnee.js'
import {
  ETAPES, VARIANTE_PLEIN, VARIANTE_PREVU, VARIANTE_A_CONFIRMER, VARIANTE_A_LIBERER, VARIANTE_LIBRE,
  ETAPE_LEVEE, ETAPE_EN_RECOLTE,
} from '../lib/etapes.js'

/**
 * Page de contrôle visuel du langage des étapes [US-321 / CA7] — `/etapes`.
 * Rejoue les sept étapes pleines et prévues, la pastille « à confirmer », le gris
 * « à libérer » et le rang libre, en trois largeurs de segment (le libellé s'écrit
 * dès qu'il y a la place), avec bascule thème sombre et niveaux de gris (V8).
 * [US-352 / CA9] Montre aussi les pièces du socle — pastille, puce, calendrier de l'année, note du
 * carnet, légende commune, infobulle — en clair et en sombre, avec la valeur attendue de la
 * maquette `docs/EPIC 21 - SOCLE COMMUN DES VUES/maquette/Socle commun - 7 vues.html` (section
 * « Les pièces du socle ») à côté de chaque rendu.
 * Non référencée par la navigation applicative.
 */

/** Les couleurs d'étape de la maquette : la colonne « attendu » de la page. */
const ATTENDU = [
  ['semee', 'Semé', '#E6CFA2'], ['levee', 'Levé', '#CDE9A6'], ['en_godet', 'En godet', '#CDE9A6'],
  ['plantee', 'Planté', '#CDE9A6'], ['croissance', 'En croissance', '#86C163'], ['fleur', 'En fleur', '#F4D35E'],
  ['en_recolte', 'En récolte', '#F2A54A'], ['terminee', 'Terminé', '#DADAD2'],
]
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
      <InfobulleEtapes />
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-2xl font-bold text-txt mr-auto">Étapes — US-321, pièces du socle — US-352</h1>
        <button type="button" onClick={basculer}
          className="text-[12px] font-semibold px-3 py-1 rounded-full border border-border bg-card text-txt">
          {sombre ? 'Thème clair' : 'Thème sombre'}
        </button>
        <button type="button" onClick={() => setGris(!gris)}
          className="text-[12px] font-semibold px-3 py-1 rounded-full border border-border bg-card text-txt">
          {gris ? 'Couleurs' : 'Niveaux de gris'}
        </button>
      </header>

      <Section titre="Pastilles d'étape — rendu, puis couleur attendue de la maquette">
        <div className="flex flex-wrap gap-3">
          {ATTENDU.map(([cle, libelle, hex]) => (
            <div key={cle} className="flex flex-col items-center gap-1 w-[72px]">
              <PastilleEtape etape={cle} />
              <span className="w-10 h-3 rounded-sm border border-border" style={{ background: hex }} title={hex} />
              <span className="text-[10px] text-txt3 text-center leading-tight">{libelle}<br />{hex}</span>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <PastilleEtape etape="croissance" /><span className="text-[12.5px] text-txt2">réalisé</span>
          <PastilleEtape etape="levee" prevue /><span className="text-[12.5px] text-txt2">prévu</span>
          <PastilleEtape etape="levee" prevue due /><span className="text-[12.5px] text-txt2">prévu, dû</span>
          <PastilleEtape etape="en_recolte" petite /><span className="text-[12.5px] text-txt2">petite (30 px)</span>
          <PastilleEtape etape="levee" prevue due petite />
        </div>
        <p className="text-[11.5px] text-txt3">
          Survolez une pastille, ou appuyez 380 ms au doigt : « Levé · prévu, à confirmer · dû aujourd’hui ».
        </p>
      </Section>

      <Section titre="Puces d'étape — pleines, puis « · prévu »">
        <div className="flex flex-wrap gap-2">
          {ATTENDU.map(([cle]) => <PuceEtape key={cle} etape={cle} />)}
        </div>
        <div className="flex flex-wrap gap-2">
          {ATTENDU.map(([cle]) => <PuceEtape key={cle} etape={cle} prevue petite />)}
        </div>
      </Section>

      <Section titre="Calendrier de l'année — douze cases, le mois courant cerclé">
        <div className="max-w-sm">
          <CalendrierAnnee mois={moisDeChaine('..slcfp.....')} moisCourant={new Date().getMonth()} initiales />
        </div>
        <div className="max-w-[160px]">
          <CalendrierAnnee mois={moisDeChaine('.sslccffppp..')} moisCourant={new Date().getMonth()} />
        </div>
        <LegendeCommune sujet="un mois" calendrier />
      </Section>

      <Section titre="Note du carnet — Kalam, encre bleue, papier crème">
        <div className="max-w-sm">
          <NoteCarnet dicte date="aujourd’hui" lieu="Fève · Planche centrale"
            texte="Les fèves pointent sur tout le rang, terre encore humide." />
          <NoteCarnet date="5 nov." lieu="Poireau" texte="Buttés" />
        </div>
      </Section>

      <Section titre="Légende commune">
        <LegendeCommune />
      </Section>

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
