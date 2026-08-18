// [US-058] Assistant de création du premier potager — écran bloquant affiché
// juste après l'inscription tant que le compte connecté n'appartient à aucun
// potager (CA1), remplace l'ancien écran `AucunPotager.jsx`. Réutilise le
// panneau de marque de l'écran de connexion (cf. `views/Auth.jsx`, US-056) et,
// pour la commune, le composant `VilleSearch` livré par le Lot C (US-074) —
// voir docs/ANALYSE_REFONTE_UI_WEB_2026.md §5.8, fichier focal maquette
// `Potager - Premier potager.html` / `onboarding-screens.jsx`.
import { useState } from 'react'
import {
  Sun, Moon, Leaf, Sprout, LayoutGrid, MapPin, KeyRound,
  Check, Plus, ArrowRight, Layers, Send, BookOpen,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useTheme } from '../hooks/useTheme.js'
import { Field, VilleSearch, Badge, Tip, InfoBanner, Btn } from '../components/ui'

const STEPS = [
  { id: 'potager', label: 'Votre potager', sub: 'Nom et emplacement' },
  { id: 'parcelle', label: 'Première parcelle', sub: 'Surface et exposition' },
  { id: 'cultures', label: 'Cultures', sub: 'Ce que vous faites pousser' },
  { id: 'pret', label: "C'est prêt", sub: 'Récapitulatif' },
]

const STEP_DESCRIPTIONS = [
  'Donnez un nom à votre potager pour le retrouver et le partager.',
  'Décrivez le premier espace que vous cultivez.',
  'Choisissez ce que vous cultivez déjà, vous compléterez plus tard.',
  'Vérifiez, puis entrez dans votre potager.',
]

// [CA3] Valeurs libres — la colonne texte `Parcelle.exposition` accepte
// n'importe quelle chaîne, ce catalogue est purement une aide à la saisie.
const EXPOS = ['Plein sud', 'Est', 'Ouest', 'Nord', 'Mi-ombre']
// [CA3] `Parcelle.type_sol` (migration_v28) : même principe, texte informatif.
const SOLS = ['Limoneux', 'Argileux', 'Sableux', 'Terreau', 'Je ne sais pas']
const TYPES = [
  { id: 'pleine-terre', label: 'Pleine terre', sub: 'Planche, butte ou carré au sol', icon: LayoutGrid },
  { id: 'pepiniere', label: 'Pépinière', sub: 'Semis en godet, avant mise en terre', icon: Sprout },
]
// [CA4] Catalogue fixe de 12 cultures courantes — Tomate et Courgette
// pré-sélectionnées par défaut, comme dans la maquette.
const COURANTES = [
  'Tomate', 'Courgette', 'Salade', 'Carotte', 'Haricot vert', 'Radis',
  'Pomme de terre', 'Oignon', 'Fraise', 'Poireau', 'Concombre', 'Betterave',
]

function toFloat(v) {
  if (!v || !v.trim()) return undefined
  const n = parseFloat(v.replace(',', '.'))
  return Number.isFinite(n) ? n : undefined
}

// Dupliqué à l'identique depuis `views/Auth.jsx` (US-056) plutôt que partagé :
// seul le deuxième usage, pas encore de justification à en faire un composant
// commun tant qu'un troisième écran n'en a pas besoin.
function LogoMark({ light }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className={`w-[34px] h-[34px] rounded-[11px] flex items-center justify-center shrink-0 ${light ? 'bg-white/[.18]' : 'bg-brand-soft'}`}>
        <Leaf size={20} className={light ? 'text-white' : 'text-brand'} />
      </span>
      <span className={`font-serif text-[18px] font-bold tracking-tight whitespace-nowrap ${light ? 'text-white' : 'text-txt'}`}>
        Mon Potager
      </span>
    </span>
  )
}

function Lab({ children, tip }) {
  return (
    <label className="flex items-center gap-1.5 text-[12.5px] font-semibold text-txt2 mb-1.5">
      {children}
      {tip && <Tip text={tip} />}
    </label>
  )
}

function ChoiceRow({ options, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const on = o === value
        return (
          <button
            key={o}
            type="button"
            onClick={() => onChange(o)}
            aria-pressed={on}
            className={`px-3.5 py-2 rounded-[10px] text-[13px] font-semibold border-[1.5px] transition-colors ${
              on ? 'bg-brand border-brand text-white dark:text-bg' : 'bg-card border-border text-txt2'
            }`}
          >
            {o}
          </button>
        )
      })}
    </div>
  )
}

function TypeCard({ t, on, onClick }) {
  const Icon = t.icon
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={`flex flex-col items-start gap-1.5 p-3 rounded-xl text-left border-[1.5px] transition-colors ${
        on ? 'bg-brand-soft border-brand' : 'bg-card border-border'
      }`}
    >
      <Icon size={19} className={on ? 'text-brand' : 'text-txt3'} />
      <span>
        <span className={`block text-[13.5px] ${on ? 'font-bold text-brand-text' : 'font-semibold text-txt'}`}>{t.label}</span>
        <span className="block text-[11.5px] text-txt2 mt-0.5">{t.sub}</span>
      </span>
    </button>
  )
}

// [CA2] Encart de bascule vers un code d'invitation — même parcours que
// l'ancien `AucunPotager.jsx`/`PotagerSelector.jsx` (US-048), sans changement
// de logique : un code valide rejoint directement ce potager (rechargement
// complet) et ignore le reste de l'assistant.
function InviteJoin() {
  const { accepterInvitation } = usePotager()
  const [ouvert, setOuvert] = useState(false)
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (loading || !code.trim()) return
    setLoading(true)
    setError(null)
    try {
      await accepterInvitation(code.trim())
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  if (!ouvert) {
    return (
      <button
        type="button"
        onClick={() => setOuvert(true)}
        className="mt-2 px-3.5 py-1.5 rounded-[9px] border border-blue text-blue text-[12.5px] font-bold bg-transparent"
      >
        Saisir un code d'invitation
      </button>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 mt-2 w-full">
      <div className="flex gap-2">
        <input
          autoFocus
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="Code"
          className="flex-1 min-w-0 bg-card border border-border rounded-[9px] px-3 py-2 text-[13px] font-mono tracking-wider text-txt placeholder:text-txt3"
        />
        <Btn type="submit" kind="primary" small disabled={loading || !code.trim()}>
          {loading ? '…' : 'Rejoindre'}
        </Btn>
      </div>
      {error && <p className="text-red text-[12.5px]">{error}</p>}
    </form>
  )
}

function StepPotager({ st, set }) {
  return (
    <div className="flex flex-col gap-4">
      <Field
        id="onb-nom"
        label={<span className="inline-flex items-center gap-1.5">Nom du potager<Tip text="Ce nom apparaît en haut de l'application et permet de basculer entre plusieurs potagers." /></span>}
        required
        icon={Sprout}
        placeholder="Potager de Pierre"
        value={st.nom}
        onChange={(e) => set({ nom: e.target.value })}
      />
      <div>
        <Lab tip="Sert à afficher la météo locale et à ajuster les périodes de semis proposées. Aucune adresse précise n'est demandée.">Commune</Lab>
        <VilleSearch
          id="onb-ville"
          label={null}
          value={st.localisation}
          onSelect={(v) => set({ localisation: v })}
          placeholder="Argenteuil (95)"
        />
      </div>
      <InfoBanner
        tint="blue"
        icon={KeyRound}
        dismissible={false}
        title="Vous rejoignez un potager existant ?"
        body="Si un proche vous a transmis un code d'invitation, saisissez-le plutôt que de créer un potager."
        action={<InviteJoin />}
      />
    </div>
  )
}

function StepParcelle({ st, set }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Lab tip="Une parcelle en pleine terre reçoit vos cultures ; une pépinière accueille les semis en godet avant leur mise en terre.">Nature de l'espace</Lab>
        <div className="grid grid-cols-2 gap-2">
          {TYPES.map((t) => (
            <TypeCard key={t.id} t={t} on={st.type === t.id} onClick={() => set({ type: t.id })} />
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field
          id="onb-pnom"
          label="Nom de la parcelle"
          placeholder="Planche du fond"
          value={st.pnom}
          onChange={(e) => set({ pnom: e.target.value })}
        />
        <Field
          id="onb-surface"
          label={<span className="inline-flex items-center gap-1.5">Surface<Tip text="Surface cultivable de cette parcelle. Elle sert à calculer le taux d'occupation." /></span>}
          placeholder="20"
          suffix="m²"
          inputMode="decimal"
          value={st.surface}
          onChange={(e) => set({ surface: e.target.value })}
        />
      </div>
      <div>
        <Lab tip="L'ensoleillement conditionne les cultures qui réussiront le mieux sur cette parcelle.">Exposition</Lab>
        <ChoiceRow options={EXPOS} value={st.expo} onChange={(v) => set({ expo: v })} />
      </div>
      <div>
        <Lab tip="Approximatif suffit. Vous pourrez le préciser plus tard depuis la fiche parcelle.">Type de sol</Lab>
        <ChoiceRow options={SOLS} value={st.sol} onChange={(v) => set({ sol: v })} />
      </div>
    </div>
  )
}

function StepCultures({ st, set }) {
  const toggle = (n) => set({ cultures: st.cultures.includes(n) ? st.cultures.filter((x) => x !== n) : [...st.cultures, n] })
  return (
    <div>
      <div className="flex items-center gap-2 mb-3.5 flex-wrap">
        <span className="text-[13.5px] text-txt2">Les cultures les plus courantes, pour démarrer.</span>
        <span className="ml-auto">
          <Badge tint={st.cultures.length ? 'brand' : 'amber'}>
            {st.cultures.length} sélectionnée{st.cultures.length > 1 ? 's' : ''}
          </Badge>
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {COURANTES.map((n) => {
          const on = st.cultures.includes(n)
          return (
            <button
              key={n}
              type="button"
              onClick={() => toggle(n)}
              aria-pressed={on}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-[13px] border-[1.5px] transition-colors ${
                on ? 'bg-brand-soft border-brand font-bold text-brand-text' : 'bg-card border-border font-medium text-txt2'
              }`}
            >
              {on ? <Check size={14} strokeWidth={2.2} className="text-brand" /> : <Plus size={14} strokeWidth={2.2} className="text-txt3" />}
              {n}
            </button>
          )
        })}
      </div>
      <div className="flex items-start gap-2.5 mt-4 bg-card-alt rounded-xl px-3.5 py-3">
        <BookOpen size={17} className="text-txt2 shrink-0 mt-0.5" />
        <div className="min-w-0 flex-1">
          <div className="text-[13.5px] font-bold text-txt">Le reste viendra du catalogue</div>
          <div className="text-[12.5px] text-txt2 mt-0.5 leading-relaxed">
            Variétés, familles et calendriers détaillés vous attendent dans l'écran Cultures. Ici, l'essentiel suffit à remplir votre première parcelle.
          </div>
        </div>
      </div>
    </div>
  )
}

function StepRecap({ st }) {
  const type = TYPES.find((t) => t.id === st.type)
  const hasParcelle = st.pnom.trim().length > 0
  const lignes = [
    { Icon: Sprout, l: 'Potager', v: st.nom || '—' },
    { Icon: MapPin, l: 'Commune', v: st.localisation?.ville || 'Non renseignée' },
    {
      Icon: type?.icon || LayoutGrid,
      l: 'Première parcelle',
      v: hasParcelle
        ? `${st.pnom} · ${type.label} · ${st.surface ? `${st.surface} m²` : 'Surface non renseignée'} · ${st.expo}`
        : "Aucune pour l'instant",
    },
    { Icon: Layers, l: 'Sol', v: hasParcelle ? st.sol : '—' },
    { Icon: Leaf, l: 'Cultures', v: st.cultures.length ? st.cultures.join(', ') : "Aucune pour l'instant" },
  ]
  return (
    <div>
      <div className="flex items-center gap-3 bg-brand-soft rounded-2xl px-4 py-3.5 mb-4">
        <span className="w-[42px] h-[42px] rounded-full bg-card flex items-center justify-center shrink-0">
          <Check size={22} strokeWidth={2.4} className="text-brand" />
        </span>
        <div>
          <div className="font-serif text-[17px] font-bold text-txt">Votre potager est prêt</div>
          <div className="text-[13px] text-brand-text mt-0.5">Vous pourrez tout modifier ensuite depuis les écrans Plan et Cultures.</div>
        </div>
      </div>
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        {lignes.map((r, i) => (
          <div key={r.l} className={`flex items-start gap-3 px-3.5 py-3 ${i < lignes.length - 1 ? 'border-b border-border-soft' : ''}`}>
            <r.Icon size={17} className="text-txt3 shrink-0 mt-0.5" />
            <span className="text-[12.5px] text-txt3 w-[118px] shrink-0 pt-px">{r.l}</span>
            <span className="flex-1 min-w-0 text-[13.5px] text-txt font-medium leading-relaxed">{r.v}</span>
          </div>
        ))}
      </div>
      <InfoBanner
        className="mt-3.5"
        tint="blue"
        icon={Send}
        dismissible={false}
        title="Prochaine étape suggérée"
        body="Reliez Telegram pour saisir vos récoltes et arrosages directement depuis le jardin, sans ouvrir l'application."
      />
    </div>
  )
}

function StepRail({ step }) {
  return (
    <div className="flex flex-col gap-1">
      {STEPS.map((s, i) => {
        const done = i < step
        const cur = i === step
        return (
          <div key={s.id} className="flex gap-3 items-start">
            <div className="flex flex-col items-center shrink-0">
              <span
                className={`w-[30px] h-[30px] rounded-full flex items-center justify-center shrink-0 text-[12.5px] font-bold ${done || cur ? 'bg-white' : 'bg-white/[.16]'}`}
                style={{ color: 'var(--header-from)' }}
              >
                {done ? <Check size={15} strokeWidth={2.6} /> : i + 1}
              </span>
              {i < STEPS.length - 1 && (
                <span className={`w-0.5 h-[26px] my-[3px] rounded-full ${done ? 'bg-white' : 'bg-white/[.18]'}`} />
              )}
            </div>
            <div className="pt-1">
              <div className={`text-[14.5px] ${cur ? 'font-bold text-white' : done ? 'font-medium text-white' : 'font-medium text-white/60'}`}>
                {s.label}
              </div>
              <div className="text-[12.5px] text-white/[.62] mt-0.5">{s.sub}</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function StepBar({ step }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="w-[26px] h-[26px] rounded-full bg-brand text-white dark:text-bg flex items-center justify-center text-[12px] font-bold shrink-0">
          {step + 1}
        </span>
        <span className="text-[13.5px] font-bold text-txt">{STEPS[step].label}</span>
        <span className="ml-auto text-[12px] text-txt2">Étape {step + 1} sur {STEPS.length}</span>
      </div>
      <div className="flex gap-1">
        {STEPS.map((s, i) => (
          <span key={s.id} className={`flex-1 h-1 rounded-full ${i <= step ? 'bg-brand' : 'bg-border'}`} />
        ))}
      </div>
    </div>
  )
}

export default function Onboarding() {
  const { logout } = useAuth()
  const { finaliserOnboarding } = usePotager()
  const { theme, toggle } = useTheme()

  const [step, setStep] = useState(0)
  // [CA2, CA3, CA4] État local le temps de l'assistant — aucun appel API avant
  // la validation finale du récapitulatif (CA5, CA6).
  const [st, setSt] = useState({
    nom: '',
    localisation: null, // { ville, latitude, longitude } | null
    type: 'pleine-terre',
    pnom: '',
    surface: '',
    expo: 'Plein sud',
    sol: 'Limoneux',
    cultures: ['Tomate', 'Courgette'],
  })
  const set = (patch) => setSt((s) => ({ ...s, ...patch }))

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const last = step === STEPS.length - 1
  // [CA2] Seul le nom du potager est obligatoire pour avancer / terminer.
  const peutContinuer = step !== 0 || st.nom.trim().length > 0

  function handleNext() {
    if (!peutContinuer) return
    setStep((s) => Math.min(STEPS.length - 1, s + 1))
  }

  // [CA5] Persistance en une seule fois, à la validation finale : POST /potagers
  // puis, seulement si une parcelle a été renseignée, POST /parcelles.
  async function handleFinish() {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      await finaliserOnboarding({
        nom: st.nom.trim(),
        ville: st.localisation?.ville,
        latitude: st.localisation?.latitude,
        longitude: st.localisation?.longitude,
        parcelle: st.pnom.trim()
          ? {
              nom: st.pnom.trim(),
              exposition: st.expo,
              superficieM2: toFloat(st.surface),
              estPepiniere: st.type === 'pepiniere',
              typeSol: st.sol,
            }
          : null,
      })
      // finaliserOnboarding() recharge la page en cas de succès.
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const Body = [StepPotager, StepParcelle, StepCultures, StepRecap][step]

  return (
    <div className="@container/onb h-dvh bg-bg flex flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="flex flex-col min-h-full @[900px]/onb:flex-row">
          {/* Panneau de marque — visible à partir de 900px de conteneur, même
              principe que l'écran de connexion (US-056). */}
          <aside
            className="hidden @[900px]/onb:flex flex-col justify-between p-10 shrink-0 basis-[42%] max-w-[560px] text-white"
            style={{ background: 'linear-gradient(150deg, var(--header-from), var(--header-to))' }}
          >
            <LogoMark light />
            <div className="py-8">
              <h2 className="font-serif text-[30px] @[1200px]/onb:text-[38px] font-bold tracking-tight leading-[1.15] mb-2.5">
                Créons votre premier potager.
              </h2>
              <p className="text-[15px] text-white/80 leading-relaxed max-w-[360px] mb-7">
                Quatre étapes, moins de deux minutes. Tout reste modifiable une fois dans l'application.
              </p>
              <StepRail step={step} />
            </div>
            <div className="text-xs text-white/60">© 2026 Mon Potager</div>
          </aside>

          {/* Assistant */}
          <div className="flex-1 min-w-0 flex items-start justify-center px-5 py-[26px] @[640px]/onb:p-10">
            <div className="w-full max-w-[480px]">
              <div className="flex items-center mb-[18px]">
                <span className="inline-flex @[900px]/onb:hidden">
                  <LogoMark />
                </span>
                <button onClick={logout} className="ml-auto mr-2 text-[12.5px] font-semibold text-txt2">
                  Se déconnecter
                </button>
                <button
                  onClick={toggle}
                  aria-label="Thème clair ou sombre"
                  className="w-[34px] h-[34px] rounded-[10px] border border-border bg-card flex items-center justify-center text-txt2 shrink-0"
                >
                  {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                </button>
              </div>

              <div className="@[900px]/onb:hidden mb-[18px]">
                <StepBar step={step} />
              </div>

              <h1 className="font-serif text-[25px] font-bold text-txt tracking-tight leading-[1.15]">
                {STEPS[step].label}
              </h1>
              <p className="text-[13.5px] text-txt2 mt-[5px] mb-5">{STEP_DESCRIPTIONS[step]}</p>

              <Body st={st} set={set} />

              {last && error && <p className="text-red text-[13px] mt-3.5">{error}</p>}

              <div className="flex items-center gap-2.5 mt-[22px] pt-4 border-t border-border-soft flex-wrap">
                <Btn type="button" kind="ghost" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={!step}>
                  Précédent
                </Btn>
                {!last && step > 0 && (
                  <button type="button" onClick={handleNext} className="text-[13px] font-semibold text-txt2">
                    Passer
                  </button>
                )}
                <Btn
                  type="button"
                  kind="primary"
                  className="ml-auto"
                  disabled={last ? loading : !peutContinuer}
                  onClick={last ? handleFinish : handleNext}
                >
                  {last ? (loading ? '…' : 'Entrer dans mon potager') : 'Continuer'}
                  {!loading && <ArrowRight size={16} />}
                </Btn>
              </div>

              <div className="@[900px]/onb:hidden mt-5 pt-3.5 border-t border-border-soft flex items-center justify-center gap-3.5 flex-wrap">
                <span className="text-xs text-txt3">© 2026 Mon Potager</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
