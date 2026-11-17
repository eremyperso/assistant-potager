import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, HelpCircle, X } from 'lucide-react'
import {
  COMPARAISONS, FENETRES, GRAVITES, brouillonDe, corpsModification, lireSaisie, previsualisation, regleEnClair, uniteDuSaisie,
} from '../lib/seuils.js'

const SEG = 'flex max-w-full gap-[3px] overflow-x-auto rounded-[10px] bg-card-alt p-[3px]'
const SEG_BTN = (actif) => `min-h-[38px] flex-1 whitespace-nowrap rounded-lg px-[11px] py-[7px] text-[12.5px] font-semibold ${actif ? 'bg-card text-txt shadow-[0_1px_3px_rgba(0,0,0,.12)]' : 'text-txt2'}`

function Segments({ libelle, choix, valeur, surChoix }) {
  return (
    <div role="group" aria-label={libelle} className={SEG}>
      {choix.map((c) => (
        <button key={c.id} type="button" aria-pressed={valeur === c.id} onClick={() => surChoix(c.id)} className={SEG_BTN(valeur === c.id)}>{c.libelle}</button>
      ))}
    </div>
  )
}

/**
 * La modification d'un seuil, d'après la maquette d'US-318 : une feuille montante au téléphone, un
 * panneau latéral dès 600 px (`tab:`). Comparaison, valeur, fenêtre, gravité ; la règle se relit en
 * clair et dit si elle serait franchie aujourd'hui, d'après la mesure déjà faite par l'API.
 */
export default function PanneauSeuil({ seuil, surFermer, surEnregistrer }) {
  const [brouillon, setBrouillon] = useState(() => brouillonDe(seuil))
  const [saisie, setSaisie] = useState(() => String(seuil.valeur).replace('.', ','))
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState('')
  const champ = useRef(null)
  const panneau = useRef(null)

  useEffect(() => {
    champ.current?.focus()
    const touche = (e) => { if (e.key === 'Escape') surFermer() }
    document.addEventListener('keydown', touche)
    return () => document.removeEventListener('keydown', touche)
  }, [surFermer])

  const valeur = lireSaisie(saisie)
  const courant = useMemo(() => ({ ...brouillon, valeur }), [brouillon, valeur])
  const corps = Number.isFinite(valeur) ? corpsModification(seuil, courant) : null
  const apercu = previsualisation(seuil, courant)
  const fenetreFixe = seuil.indicateur === 'cout_mois_projete'
  const comparaisons = seuil.relatif_possible ? COMPARAISONS : COMPARAISONS.filter((c) => c.id === 'fixe')
  const unite = uniteDuSaisie(seuil.unite, brouillon.comparaison)

  async function enregistrer() {
    if (!corps) { surFermer(); return }
    setEnvoi(true)
    setErreur('')
    try {
      await surEnregistrer(seuil.id, corps)
      surFermer()
    } catch (e) {
      setErreur(e.message || "L'enregistrement a échoué.")
      setEnvoi(false)
    }
  }

  const Icone = apercu.franchi === null ? HelpCircle : apercu.franchi ? AlertTriangle : CheckCircle2
  const classeApercu = apercu.franchi === null ? 'bg-card-alt text-txt2' : apercu.franchi ? 'bg-red text-white' : 'bg-brand-soft text-brand-text'

  return (
    <>
      <div className="fixed inset-0 z-40 bg-[rgba(15,20,9,.45)]" onClick={surFermer} aria-hidden="true" />
      <div ref={panneau} role="dialog" aria-modal="true" aria-label="Modifier le seuil"
        className="fixed inset-x-0 bottom-0 z-50 flex max-h-[92%] flex-col rounded-t-[20px] bg-surface text-txt shadow-[0_-10px_30px_rgba(0,0,0,.25)] tab:inset-y-0 tab:left-auto tab:right-0 tab:max-h-full tab:w-[400px] tab:rounded-none tab:shadow-[-10px_0_30px_rgba(0,0,0,.2)]">
        <span className="mx-auto mt-2 block h-[5px] w-[42px] rounded-[3px] bg-border tab:hidden" aria-hidden="true" />
        <div className="flex items-start gap-2.5 border-b border-border px-4 py-3">
          <div className="flex-1">
            <h3 className="font-serif text-[17px] font-semibold leading-snug">{seuil.libelle}</h3>
            <p className="mt-0.5 text-xs text-txt2">Modifier le seuil · alerte Telegram et e-mail</p>
          </div>
          <button type="button" onClick={surFermer} aria-label="Fermer" className="grid h-10 w-10 place-items-center rounded-full bg-card-alt"><X size={17} aria-hidden="true" /></button>
        </div>

        <div className="flex flex-col gap-3.5 overflow-y-auto px-4 py-3.5">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12.5px] font-bold text-txt2">Type de comparaison</span>
            <Segments libelle="Type de comparaison" choix={comparaisons} valeur={brouillon.comparaison}
              surChoix={(id) => setBrouillon({ ...brouillon, comparaison: id })} />
          </div>

          <label className="flex flex-col gap-1.5">
            <span className="text-[12.5px] font-bold text-txt2">Valeur</span>
            <span className="flex max-w-[220px] items-center overflow-hidden rounded-[10px] border-[1.5px] border-border bg-card">
              <input ref={champ} inputMode="decimal" value={saisie} onChange={(e) => setSaisie(e.target.value)} aria-label="Valeur du seuil"
                aria-invalid={!Number.isFinite(valeur)} className="w-full border-0 bg-transparent px-[11px] py-[9px] text-base font-bold text-txt outline-none" />
              {unite ? <em className="grid place-items-center self-stretch border-l border-border bg-card-alt px-3 font-bold not-italic text-txt2">{unite}</em> : null}
            </span>
            {!Number.isFinite(valeur) ? <span role="alert" className="text-xs font-semibold text-red">Entrez un nombre positif.</span> : null}
          </label>

          {!fenetreFixe ? (
            <div className="flex flex-col gap-1.5">
              <span className="text-[12.5px] font-bold text-txt2">Fenêtre de mesure</span>
              <Segments libelle="Fenêtre de mesure" choix={FENETRES} valeur={brouillon.fenetre_jours}
                surChoix={(id) => setBrouillon({ ...brouillon, fenetre_jours: id })} />
            </div>
          ) : null}

          <div className="flex flex-col gap-1.5">
            <span className="text-[12.5px] font-bold text-txt2">Gravité</span>
            <Segments libelle="Gravité" choix={GRAVITES} valeur={brouillon.gravite} surChoix={(id) => setBrouillon({ ...brouillon, gravite: id })} />
            <span className="text-xs text-txt2">Une gravité haute envoie un rappel chaque jour tant que l'alerte reste ouverte.</span>
          </div>

          <div className="rounded-xl bg-card-alt p-3 text-[13px]" aria-live="polite">
            <b className="mb-0.5 block text-xs text-txt2">Règle</b>
            Alerte si {regleEnClair(seuil, courant)}.
            <span className={`mt-2 flex items-start gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold ${classeApercu}`}>
              <Icone size={14} className="mt-px shrink-0" aria-hidden="true" />{apercu.texte}
            </span>
          </div>
          {erreur ? <p role="alert" className="text-[13px] font-semibold text-red">{erreur}</p> : null}
        </div>

        <div className="flex gap-2.5 border-t border-border px-4 py-3 pb-[max(12px,var(--safe-bottom))]">
          <button type="button" onClick={surFermer} className="min-h-[44px] flex-1 rounded-xl border border-border bg-card font-bold text-txt">Annuler</button>
          <button type="button" onClick={enregistrer} disabled={envoi || !Number.isFinite(valeur)}
            className="min-h-[44px] flex-1 rounded-xl bg-brand font-bold text-white disabled:opacity-50">{envoi ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </div>
    </>
  )
}
