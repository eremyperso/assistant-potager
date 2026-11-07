// [US-271] Le chat de Gaston, ouvert depuis n'importe quel écran — d'après la maquette « Compagnon.html ».
//
// Le portail parle au MÊME compagnon que Telegram : la phrase part à `POST /compagnon/messages`
// (US-270), qui la lit par le même orchestrateur que le bot. Ce panneau ne décide de RIEN — il
// envoie, il montre, il clique. Un geste compris revient en carte et se confirme ici ; une commande
// se confirme dans Telegram (la carte le dit) ; en mode Support (le casque de l'en-tête), l'aide de
// l'application répond et rien n'est écrit.
//
// Placement : c'est la PAGE qui décide (voir `App.jsx`) — plein écran au téléphone, carte flottante
// de 380 × 600 en bas à droite au-delà. Ce composant remplit la boîte qu'on lui donne ; `plein` ne
// change que les tailles tactiles (boutons de 44 px, marge haute, pied) de la maquette mobile. Son
// contenu vit dans un conteneur (`@container/compagnon`), comme la règle de frontend/CLAUDE.md l'exige.
import { useState, useEffect, useRef, useCallback } from 'react'
import { Headset, RotateCcw, X, Send, Lock, Loader2, Microscope } from 'lucide-react'
import { api } from '../lib/api.js'
import { VisageGaston } from './Gaston.jsx'
import CarteProposition from './CarteProposition.jsx'
import {
  GASTON, MODE_DEFAUT, ACCUEIL, SUGGESTIONS, PLACEHOLDER, questionDeSuggestion, messageErreur,
  carteDefinitivementFermee, carteFermee, carteApresIssue, filDepuisHistorique, filApresRecommencer,
  ajouterEchange, ajouterErreur, ajouterPhrase, cleDePhrase, remplacerCarte, remplacerLesAnciennes, peutEnvoyer, texteACorriger,
  aEnregistre, LONGUEUR_MAX, fusionnerEtat, INTERVALLE_OUVERT_MS,
  MODE_ANALYSE, TEXTE_ANALYSE_EN_COURS, peutApprofondir, peutApprofondirEntree, analyseBornee,
} from '../lib/compagnon.js'
import { ThumbsUp, ThumbsDown } from 'lucide-react'

const ETAGES_AVEC_AVIS = ['savoir', 'raisonnement']

function Avatar() {
  return (
    <span className="h-[34px] w-[34px] shrink-0 overflow-hidden rounded-full border-2 border-[var(--card)] bg-[var(--gst-visage)] shadow-[0_1px_3px_rgba(0,0,0,.12)]">
      <VisageGaston />
    </span>
  )
}

/** Une bulle du compagnon, avec son avatar ; ce qui est dessous (cartes, avis) s'aligne sur son texte. */
function Bulle({ children, etiquette = null, teinte = '' }) {
  return (
    <div className="flex items-end gap-2">
      <Avatar />
      <div className="min-w-0 max-w-[270px]">
        {etiquette && <div className="mb-1 text-[11.5px] font-semibold text-brand-text">{etiquette}</div>}
        <p className={`whitespace-pre-wrap break-words rounded-[16px] rounded-bl-[4px] bg-[var(--gst-bulle)] px-[13px] py-2.5 text-[13.5px] leading-[1.45] text-txt shadow-[0_1px_2px_rgba(22,33,12,.06)] ${teinte}`}>
          {children}
        </p>
      </div>
    </div>
  )
}

function Entree({ entree, occupe, onAction, onAvis, avisDonnes, onApprofondir }) {
  const { role, texte } = entree

  if (role === 'jardinier') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[270px] whitespace-pre-wrap break-words rounded-[16px] rounded-br-[4px] bg-brand px-[13px] py-2.5 text-[13.5px] leading-[1.45] text-white dark:text-bg">
          {texte}
        </p>
      </div>
    )
  }

  if (role === 'erreur') {
    return (
      <div role="alert" className="ml-[42px] rounded-[12px] border-[1.5px] border-red bg-red-soft px-3 py-2 text-[12.5px] text-red break-words">
        {texte}
      </div>
    )
  }

  const spontane = role === 'spontane'
  const peutNoter = entree.routageLogId && ETAGES_AVEC_AVIS.includes(entree.etage)
  return (
    <div className="space-y-2">
      {texte && (
        <Bulle
          etiquette={spontane ? `Message de ${GASTON.nom}` : entree.vers === 'analyse' ? (analyseBornee(entree) ? 'Analyse partielle' : 'Analyse approfondie') : null}
          teinte={entree.resume ? 'italic text-txt2' : ''}
        >
          {texte}
        </Bulle>
      )}
      {entree.vers === 'analyse' && entree.sources?.length > 0 && (
        <p className="ml-[42px] text-[12px] text-txt3">Sources : {entree.sources.join(' · ')}</p>
      )}
      {peutApprofondirEntree(entree) && (
        <div className="ml-[42px]">
          <button
            type="button"
            disabled={occupe}
            onClick={() => onApprofondir(entree.phrase)}
            className="inline-flex items-center gap-1.5 rounded-full border-[1.5px] border-brand bg-[var(--gst-bulle)] px-3 py-1.5 text-[12.5px] font-semibold text-brand-text hover:bg-brand-soft disabled:opacity-40"
          >
            <Microscope size={14} aria-hidden="true" />
            Approfondir
          </button>
        </div>
      )}
      {(entree.cartes ?? []).map((carte) => (
        <div key={carte.id} className="ml-[42px]">
          <CarteProposition carte={carte} occupe={occupe} onAction={onAction} />
        </div>
      ))}
      {peutNoter && (
        <div className="ml-[42px] flex items-center gap-1.5 text-[12px] text-txt3">
          <span>Cette réponse vous a aidé ?</span>
          {avisDonnes[entree.routageLogId] ? (
            <span aria-live="polite">Merci.</span>
          ) : (
            <>
              <button type="button" aria-label="Utile" onClick={() => onAvis(entree.routageLogId, 'positif')} className="rounded p-1 hover:bg-brand-soft">
                <ThumbsUp size={14} />
              </button>
              <button type="button" aria-label="Pas utile" onClick={() => onAvis(entree.routageLogId, 'negatif')} className="rounded p-1 hover:bg-brand-soft">
                <ThumbsDown size={14} />
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function PanneauCompagnon({ onFermer, onEnregistre, onVu, plein = false }) {
  const [mode, setMode] = useState(MODE_DEFAUT)
  const [fil, setFil] = useState([])
  const [texte, setTexte] = useState('')
  const [occupe, setOccupe] = useState(false)
  const [charge, setCharge] = useState(false)
  const [analyse, setAnalyse] = useState(false)
  const [avisDonnes, setAvisDonnes] = useState({})
  const bas = useRef(null)
  const saisie = useRef(null)

  const support = mode === 'support'
  const accueil = charge && fil.length === 0

  // CA3 : à l'ouverture, ce que le compagnon a dit de lui-même, la conversation récente et les cartes en cours.
  useEffect(() => {
    let vivant = true
    api.historiqueCompagnon()
      .then((h) => { if (vivant) { setFil(filDepuisHistorique(h)); onVu?.(h) } })
      .catch((e) => { if (vivant) setFil((f) => ajouterErreur(f, e)) })
      .finally(() => { if (vivant) setCharge(true) })
    return () => { vivant = false }
  }, [onVu])

  // [US-272 / CA5] Le panneau ouvert se relit à intervalle court, sans WebSocket : une carte confirmée
  // dans Telegram y passe « Confirmé depuis Telegram », une proposition ou un message nouveaux s'ajoutent.
  useEffect(() => {
    if (!charge) return undefined
    let vivant = true
    const relire = () => {
      if (typeof document !== 'undefined' && document.hidden) return
      api.etatCompagnon()
        .then((etat) => { if (vivant) { setFil((f) => fusionnerEtat(f, etat)); onVu?.(etat) } })
        .catch(() => { /* hors ligne un instant : la prochaine relecture rattrapera */ })
    }
    const minuterie = setInterval(relire, INTERVALLE_OUVERT_MS)
    return () => { vivant = false; clearInterval(minuterie) }
  }, [charge, onVu])

  useEffect(() => { bas.current?.scrollIntoView?.({ block: 'end' }) }, [fil, occupe])

  // Échap referme le chat, comme la croix.
  useEffect(() => {
    const surTouche = (e) => { if (e.key === 'Escape') onFermer?.() }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [onFermer])

  const envoyer = useCallback(async (brut, modeForce) => {
    const phrase = (brut ?? texte).trim()
    if (!peutEnvoyer(phrase, occupe)) return
    // La phrase s'affiche tout de suite : la saisie se vide, elle ne doit pas disparaître pendant
    // que Gaston réfléchit. Sa clé la désigne au retour de la réponse, pour ne pas la remettre.
    const cleJ = cleDePhrase()
    setOccupe(true)
    setAnalyse(modeForce === MODE_ANALYSE)
    setTexte('')
    setFil((f) => ajouterPhrase(f, phrase, cleJ))
    try {
      const reponse = await api.messageCompagnon(phrase, modeForce ?? mode)
      setFil((f) => ajouterEchange(remplacerLesAnciennes(f, reponse.propositions), phrase, reponse, cleJ))
    } catch (e) {
      // CA4 : réseau coupé, modèle indisponible, lecteur… dit en clair ; la phrase reste à reprendre.
      setFil((f) => ajouterErreur(f, e, phrase, cleJ))
      setTexte(phrase)
    } finally {
      setOccupe(false)
      setAnalyse(false)
      saisie.current?.focus()
    }
  }, [texte, occupe, mode])

  // [US-273 / CA1] « Approfondir » : la même phrase, lue en profondeur et sans rien écrire.
  const approfondir = useCallback((phrase) => envoyer(phrase, MODE_ANALYSE), [envoyer])

  const agirSurCarte = useCallback(async (action, carte) => {
    if (action === 'corriger') {
      setMode('normal')
      setTexte(texteACorriger(carte))
      saisie.current?.focus()
      return
    }
    setOccupe(true)
    try {
      const issue = action === 'confirmer'
        ? await api.confirmerProposition(carte.id)
        : await api.abandonnerProposition(carte.id)
      setFil((f) => remplacerCarte(f, carteApresIssue(carte, issue)))
      if (aEnregistre(issue)) onEnregistre?.()
    } catch (e) {
      // Déjà traitée ou disparue : la carte se ferme avec la raison. Sinon, on peut réessayer.
      setFil((f) => remplacerCarte(
        f, carteDefinitivementFermee(e) ? carteFermee(carte, e) : { ...carte, erreur: messageErreur(e) },
      ))
    } finally {
      setOccupe(false)
    }
  }, [onEnregistre])

  const donnerAvis = useCallback(async (id, avis) => {
    setAvisDonnes((a) => ({ ...a, [id]: true }))
    try { await api.retourReponse(id, avis) } catch { /* un avis déjà donné (409) ou perdu ne gêne personne */ }
  }, [])

  // « Recommencer » : l'écran repart d'un accueil (la mémoire du compagnon, elle, reste la même).
  const recommencer = useCallback(async () => {
    setMode(MODE_DEFAUT)
    setTexte('')
    try {
      setFil(filApresRecommencer(await api.historiqueCompagnon()))
    } catch {
      setFil([])
    }
  }, [])

  const bouton = plein ? 'h-11 w-11' : 'h-9 w-9'

  return (
    <div
      className="@container/compagnon flex h-full w-full flex-col overflow-hidden bg-[var(--gst-fond)] text-txt"
      role="dialog"
      aria-label={`Discuter avec ${GASTON.nom}`}
    >
      {/* En-tête : Gaston, son état, et les trois boutons ronds de la maquette */}
      <div className={`flex items-center gap-3 bg-[var(--gst-entete)] pb-3.5 pl-3.5 pr-3 text-white ${plein ? 'pt-[max(52px,env(safe-area-inset-top))]' : 'pt-3.5'}`}>
        <span className="h-[54px] w-[54px] shrink-0 overflow-hidden rounded-full border-[3px] border-white bg-[#FBF3D1]">
          <VisageGaston />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-hand text-[24px] font-bold leading-none">{GASTON.nom}</div>
          <div className="mt-[3px] flex items-center gap-1.5 whitespace-nowrap text-[12.5px] font-semibold">
            <i className="h-2 w-2 rounded-full bg-[#7BD87F]" aria-hidden="true" />
            {support ? 'En ligne · mode Support' : 'En ligne'}
          </div>
          {!plein && (
            <div className="mt-0.5 text-[11px] italic text-[#C9DBB8]">Version bêta : les conseils peuvent être approximatifs.</div>
          )}
        </div>
        <div className={`flex gap-2 self-start ${plein ? 'gap-1 self-center' : ''}`}>
          <button
            type="button"
            onClick={() => setMode(support ? 'normal' : 'support')}
            aria-pressed={support}
            aria-label={support ? 'Revenir au mode Normal' : 'Passer en mode Support'}
            title={support ? 'Revenir au mode Normal' : 'Mode Support : l’aide de l’application'}
            className={`${bouton} inline-flex items-center justify-center rounded-full ${support ? 'bg-white/35' : 'bg-white/[.16] hover:bg-white/[.26]'}`}
          >
            <Headset size={17} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={recommencer}
            aria-label="Recommencer"
            title="Recommencer"
            className={`${bouton} inline-flex items-center justify-center rounded-full bg-white/[.16] hover:bg-white/[.26]`}
          >
            <RotateCcw size={17} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onFermer}
            aria-label="Fermer"
            title="Fermer"
            className={`${bouton} inline-flex items-center justify-center rounded-full bg-white/[.16] hover:bg-white/[.26]`}
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Fil de la conversation */}
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-3.5 py-4" aria-live="polite">
        <div className="mt-auto" />
        {support && (
          <div className="ml-[42px] rounded-[12px] border-[1.5px] border-dashed border-brand bg-[var(--gst-bulle)] px-3 py-2.5 text-[12.5px] text-txt2">
            <b className="font-hand text-[17px] text-txt">Mode Support</b><br />
            L’aide de l’application répond ; rien n’est écrit.{' '}
            <button type="button" onClick={() => setMode('normal')} className="font-semibold text-brand-text underline">
              Revenir au mode Normal
            </button>
          </div>
        )}
        {!charge && <p className="ml-[42px] text-[12.5px] text-txt3">Je relis notre conversation…</p>}
        {accueil && (
          <>
            <Bulle>{ACCUEIL[mode]}</Bulle>
            <div className="flex flex-wrap gap-1.5 pl-[42px]">
              {SUGGESTIONS[mode].map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={occupe}
                  onClick={() => envoyer(questionDeSuggestion(s))}
                  className={`rounded-full border-[1.5px] border-brand bg-[var(--gst-bulle)] px-3 text-[12.5px] font-semibold text-brand-text hover:bg-brand-soft disabled:opacity-40 ${plein ? 'py-2.5' : 'py-1.5'}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </>
        )}
        {fil.map((entree) => (
          <Entree key={entree.cle} entree={entree} occupe={occupe} onAction={agirSurCarte} onAvis={donnerAvis} avisDonnes={avisDonnes} onApprofondir={approfondir} />
        ))}
        {occupe && (
          <div className="flex items-end gap-2" role="status" aria-label={analyse ? TEXTE_ANALYSE_EN_COURS : 'Gaston réfléchit'}>
            <Avatar />
            <div className="gst-tape flex gap-1 rounded-[16px] rounded-bl-[4px] bg-[var(--gst-bulle)] p-3.5 shadow-[0_1px_2px_rgba(22,33,12,.06)]"><i /><i /><i /></div>
            {analyse && <span className="text-[12.5px] text-txt3">{TEXTE_ANALYSE_EN_COURS}</span>}
          </div>
        )}
        <div ref={bas} />
      </div>

      {/* Saisie en pilule, et la mention de la maquette */}
      <div className={`border-t border-[var(--gst-bord-doux)] bg-[var(--gst-fond)] px-3 pt-2.5 ${plein ? 'pb-[max(26px,env(safe-area-inset-bottom))]' : 'pb-3.5'}`}>
        <form
          className="@container/saisie flex items-center gap-2 rounded-full border-[1.5px] border-[var(--gst-bord)] bg-[var(--gst-bulle)] py-1 pl-4 pr-1 focus-within:border-brand"
          onSubmit={(e) => { e.preventDefault(); envoyer() }}
        >
          <label htmlFor="compagnon-saisie" className="sr-only">Votre message à {GASTON.nom}</label>
          <input
            id="compagnon-saisie"
            ref={saisie}
            value={texte}
            onChange={(e) => setTexte(e.target.value)}
            maxLength={LONGUEUR_MAX}
            placeholder={PLACEHOLDER[mode]}
            autoComplete="off"
            className="min-w-0 flex-1 border-0 bg-transparent text-[13.5px] text-txt outline-none placeholder:text-txt3"
          />
          <button
            type="button"
            disabled={!peutApprofondir(texte, occupe)}
            onClick={() => envoyer(undefined, MODE_ANALYSE)}
            aria-label="Approfondir"
            title="Approfondir : une analyse qui croise vos données, sans rien modifier"
            className={`${plein ? 'h-11 w-11' : 'h-[38px] w-[38px]'} inline-flex shrink-0 items-center justify-center rounded-full border-[1.5px] border-brand text-brand-text hover:bg-brand-soft disabled:opacity-40`}
          >
            <Microscope size={17} aria-hidden="true" />
          </button>
          <button
            type="submit"
            disabled={!peutEnvoyer(texte, occupe)}
            aria-label="Envoyer"
            className={`${plein ? 'h-11 w-11' : 'h-[38px] w-[38px]'} inline-flex shrink-0 items-center justify-center rounded-full bg-brand text-white disabled:opacity-40 dark:text-bg`}
          >
            {occupe ? <Loader2 size={17} className="animate-spin" aria-hidden="true" /> : <Send size={17} fill="currentColor" aria-hidden="true" />}
          </button>
        </form>
        <div className="mt-2 flex items-center justify-center gap-[5px] text-[11px] text-txt3">
          <Lock size={12} className="text-brand" aria-hidden="true" />
          <span>Agent dédié <b className="font-semibold text-brand-text">Assistant Potager</b> · échanges protégés</span>
        </div>
      </div>
    </div>
  )
}
