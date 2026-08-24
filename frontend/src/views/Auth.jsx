// [US-056] Écran d'inscription / connexion / mot de passe oublié — affiché tant
// qu'aucune session JWT n'est active. Layout scindé (panneau de marque + formulaire)
// à partir de 900px de conteneur, formulaire seul en dessous — cf. maquette
// `login-screens.jsx` et docs/ANALYSE_REFONTE_UI_WEB_2026.md §5.7.
import { useEffect, useState } from 'react'
import { Sun, Moon, Leaf, KeyRound, Sprout, LayoutGrid, Send } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../hooks/useTheme.js'
import { authApi } from '../lib/api.js'
import { Field } from '../components/ui'

function GoogleMark({ s = 18 }) {
  return (
    <svg width={s} height={s} viewBox="0 0 48 48" className="shrink-0 block">
      <path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-3.2-.4-4.7H24v9h11.8c-.5 2.7-2 5-4.4 6.6v5.5h7.1c4.2-3.8 6.6-9.5 6.6-16.4z" />
      <path fill="#34A853" d="M24 46c6 0 11-2 14.6-5.4l-7.1-5.5c-2 1.3-4.5 2.1-7.5 2.1-5.8 0-10.6-3.9-12.4-9.1H4.3v5.7C7.9 41 15.4 46 24 46z" />
      <path fill="#FBBC05" d="M11.6 28.1c-.4-1.3-.7-2.7-.7-4.1s.2-2.8.7-4.1v-5.7H4.3C2.8 17.1 2 20.4 2 24s.8 6.9 2.3 9.8l7.3-5.7z" />
      <path fill="#EA4335" d="M24 10.8c3.3 0 6.2 1.1 8.5 3.3l6.3-6.3C35 4.3 30 2 24 2 15.4 2 7.9 7 4.3 14.2l7.3 5.7c1.8-5.2 6.6-9.1 12.4-9.1z" />
    </svg>
  )
}

// [US-090 / CA2] Facebook n'a jamais été retenu — l'API Graph ne garantit
// jamais l'attestation de vérification de l'e-mail, ce qui interdit le
// rattachement automatique d'un compte existant (CA12). [US-091 / CA19]
// Telegram non plus : un Login Widget ouvrirait un second chemin d'identité
// concurrent (compte sans e-mail, sans canal de récupération) pour un gain
// nul face à la liaison existante (menu Compte) — l'utilisateur déjà lié se
// reconnecte par e-mail ou par Google (US-090). Google reste donc le seul
// connecteur de cet écran. Écart assumé avec la maquette 2026
// (docs/ANALYSE_REFONTE_UI_WEB_2026.md §5.7, qui en dessine trois).

// [CA3] Chaque échec possible du parcours Google a son message — l'utilisateur
// revient toujours sur cet écran avec une explication, jamais une trace technique.
const MESSAGES_ERREUR_OAUTH = {
  acces_refuse:
    "Connexion Google interrompue. Vous pouvez réessayer, ou vous connecter avec votre e-mail et votre mot de passe.",
  etat_invalide:
    "La demande de connexion Google a expiré. Cliquez à nouveau sur « Continuer avec Google ».",
  email_non_verifie:
    "Google n'atteste pas la vérification de cette adresse e-mail : elle ne peut pas être rattachée automatiquement à un compte existant. Connectez-vous avec votre e-mail et votre mot de passe.",
  echec_google:
    "La connexion avec Google n'a pas abouti. Réessayez dans un instant, ou connectez-vous avec votre e-mail et votre mot de passe.",
}

const MESSAGE_VERIFICATION_REQUISE =
  "Votre compte a bien été créé, mais Google n'atteste pas la vérification de votre adresse : un e-mail de vérification vient de vous être envoyé. Cliquez sur le lien reçu, puis revenez vous connecter."

function alerteDepuisRetourOAuth(retour) {
  if (!retour) return null
  if (retour.erreur) {
    return { ton: 'erreur', texte: MESSAGES_ERREUR_OAUTH[retour.erreur] || MESSAGES_ERREUR_OAUTH.echec_google }
  }
  if (retour.info === 'verification_requise') {
    return { ton: 'info', texte: MESSAGE_VERIFICATION_REQUISE }
  }
  return null
}

// [CA1] Repères génériques, non liés à un compte réel : cet écran s'affiche
// avant authentification, aucune donnée personnelle n'est disponible ici
// (contrairement aux chiffres d'exemple de la maquette de démonstration).
const HERO = [
  { Icon: Sprout, t: 'Du semis à la récolte', s: 'Toutes vos parcelles suivies au même endroit' },
  { Icon: LayoutGrid, t: 'Parcelles, pépinière et stocks réunis', s: 'Un seul suivi pour tout votre potager' },
  { Icon: Send, t: 'Accessible aussi depuis Telegram', s: 'Dictez vos actions directement depuis le jardin' },
]

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

// [US-090 / CA1, CA4] Actif dès que l'API déclare le connecteur configuré, et
// purement absent sinon — masqué, jamais en erreur : sans identifiants Google
// dans l'environnement, le bouton n'existe pas (dev local et tests compris).
function OAuthRow({ googleActif }) {
  if (!googleActif) return null

  return (
    <button
      type="button"
      onClick={() => { window.location.href = authApi.googleStartUrl() }}
      className="w-full h-[46px] rounded-[11px] bg-card border border-border text-txt text-[13.5px] font-semibold flex items-center justify-center gap-2"
    >
      <GoogleMark s={19} />
      Continuer avec Google
    </button>
  )
}

function Sep({ children }) {
  return (
    <div className="flex items-center gap-3 my-[18px]">
      <span className="flex-1 h-px bg-border" />
      <span className="text-[11.5px] text-txt3 uppercase tracking-wider font-semibold">{children}</span>
      <span className="flex-1 h-px bg-border" />
    </div>
  )
}

export default function Auth({ retourOAuth = null }) {
  const { theme, toggle } = useTheme()
  const { login, register, loading, error, errorCode, resendVerification } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'signup' | 'forgot'
  const [nom, setNom] = useState('')
  const [email, setEmail] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [cguOk, setCguOk] = useState(false)
  const [message, setMessage] = useState(null)
  const [envoiForgotEnCours, setEnvoiForgotEnCours] = useState(false)
  const [forgotEnvoye, setForgotEnvoye] = useState(false)
  // [US-090 / CA4] Faux par défaut : tant que l'API n'a pas répondu, aucun
  // bouton Google n'apparaît — mieux vaut un connecteur qui s'affiche avec un
  // instant de retard qu'un bouton qui s'avère inopérant.
  const [googleActif, setGoogleActif] = useState(false)
  const [alerteOAuth, setAlerteOAuth] = useState(() => alerteDepuisRetourOAuth(retourOAuth))

  useEffect(() => {
    let annule = false
    authApi.oauthProviders().then((connecteurs) => {
      if (!annule) setGoogleActif(Boolean(connecteurs.google))
    })
    return () => { annule = true }
  }, [])

  function changerMode(m) {
    setMode(m)
    setMessage(null)
    setAlerteOAuth(null)
    setMotDePasse('')
    setForgotEnvoye(false)
  }

  async function handleResend() {
    setMessage(null)
    await resendVerification(email)
    setMessage("Si ce compte existe, un nouvel e-mail de vérification vient d'être envoyé.")
  }

  // [US-057 / CA1] Réponse toujours générique côté API — aucune indication
  // exploitable sur l'existence du compte, quel que soit l'e-mail saisi.
  async function handleSubmit(e) {
    e.preventDefault()
    setMessage(null)

    if (mode === 'forgot') {
      setEnvoiForgotEnCours(true)
      try {
        await authApi.motDePasseOublie(email)
      } finally {
        setEnvoiForgotEnCours(false)
      }
      setForgotEnvoye(true)
      return
    }

    if (mode === 'login') {
      const ok = await login(email, motDePasse)
      if (!ok) setMotDePasse('')
    } else {
      const ok = await register(email, motDePasse, nom)
      setMotDePasse('')
      if (ok) {
        // [Fix] changerMode() remet `message` à null — l'appeler avant de fixer
        // le message de succès, jamais après, sous peine de l'effacer aussitôt
        // (les deux setState sont mis en lot dans le même gestionnaire d'événement).
        changerMode('login')
        setMessage(
          "Compte créé — un e-mail de vérification vient d'être envoyé à votre adresse. " +
            'Cliquez sur le lien reçu pour activer votre compte avant de vous connecter.'
        )
      }
    }
  }

  const titre = { login: 'Connexion', signup: 'Créer un compte', forgot: 'Mot de passe oublié' }[mode]
  const sousTitre = {
    login: 'Accédez au suivi de vos parcelles, semis et récoltes.',
    signup: 'Quelques informations et votre premier potager est prêt.',
    forgot: 'Indiquez votre e-mail, nous vous envoyons un lien de réinitialisation.',
  }[mode]

  return (
    <div className="@container/auth h-dvh bg-bg flex flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="flex flex-col min-h-full @[900px]/auth:flex-row">
          {/* Panneau de marque — visible à partir de 900px de conteneur [CA1] */}
          <aside
            className="hidden @[900px]/auth:flex flex-col justify-between p-10 shrink-0 basis-[42%] max-w-[560px] text-white"
            style={{ background: 'linear-gradient(150deg, var(--header-from), var(--header-to))' }}
          >
            <LogoMark light />
            <div className="py-8">
              <h2 className="font-serif text-[30px] @[1200px]/auth:text-[38px] font-bold tracking-tight leading-[1.15] mb-3">
                Votre potager, saison après saison.
              </h2>
              <p className="text-[15px] text-white/80 leading-relaxed max-w-[380px] mb-7">
                Parcelles, semis, stocks et récoltes réunis dans un seul suivi, consultable
                depuis le jardin comme depuis le bureau.
              </p>
              <div className="flex flex-col gap-4">
                {HERO.map(({ Icon, t, s }) => (
                  <div key={t} className="flex items-start gap-3">
                    <span className="w-[38px] h-[38px] rounded-xl bg-white/[.14] flex items-center justify-center shrink-0">
                      <Icon size={19} />
                    </span>
                    <span>
                      <span className="block text-[14.5px] font-bold">{t}</span>
                      <span className="block text-[13px] text-white/[.72] mt-0.5">{s}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex gap-4 text-xs text-white/60 flex-wrap">
              <span>© 2026 Mon Potager</span>
              <a href="#">Mentions légales</a>
              <a href="#">Confidentialité</a>
            </div>
          </aside>

          {/* Formulaire */}
          <div className="flex-1 min-w-0 flex items-center justify-center px-5 py-[26px] @[640px]/auth:p-10">
            <div className="w-full max-w-[404px]">
              <div className="flex items-center mb-[22px]">
                <span className="inline-flex @[900px]/auth:hidden">
                  <LogoMark />
                </span>
                <button
                  onClick={toggle}
                  aria-label="Thème clair ou sombre"
                  className="ml-auto w-[34px] h-[34px] rounded-[10px] border border-border bg-card flex items-center justify-center text-txt2"
                >
                  {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                </button>
              </div>

              <div className="mb-5">
                <h1 className="font-serif text-[27px] font-bold text-txt tracking-tight leading-[1.15]">{titre}</h1>
                <p className="text-[13.5px] text-txt2 mt-1.5">{sousTitre}</p>
              </div>

              {alerteOAuth && (
                <div
                  role={alerteOAuth.ton === 'erreur' ? 'alert' : 'status'}
                  className={`rounded-xl text-[13px] leading-relaxed p-3.5 mb-4 ${
                    alerteOAuth.ton === 'erreur' ? 'bg-red-soft text-red' : 'bg-brand-soft text-brand-text'
                  }`}
                >
                  {alerteOAuth.texte}
                </div>
              )}

              {mode !== 'forgot' && (
                <>
                  <OAuthRow googleActif={googleActif} />
                  {/* [CA16] La fusion de deux comptes ouverts sur deux adresses
                      différentes n'existe pas en v1 : le dire avant, plutôt que
                      de laisser découvrir un potager vide après coup. */}
                  {googleActif && mode === 'login' && (
                    <p className="text-[11px] text-txt3 mt-1.5 text-center leading-relaxed">
                      Une adresse e-mail = un compte : deux comptes ouverts sur deux adresses
                      différentes ne peuvent pas encore être fusionnés.
                    </p>
                  )}
                  <Sep>ou par e-mail</Sep>
                </>
              )}

              {mode === 'forgot' && forgotEnvoye ? (
                <div className="rounded-xl bg-brand-soft text-brand-text text-[13.5px] leading-relaxed p-4">
                  Si un compte existe pour cette adresse, un e-mail contenant un lien de
                  réinitialisation vient d'être envoyé (valable 1 heure).
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
                  {mode === 'signup' && (
                    <Field
                      id="nom"
                      label="Nom"
                      required
                      placeholder="Pierre Dupont"
                      autoComplete="name"
                      value={nom}
                      onChange={(e) => setNom(e.target.value)}
                    />
                  )}
                  <Field
                    id="email"
                    label="Adresse e-mail"
                    type="email"
                    required
                    placeholder="vous@exemple.fr"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  {mode !== 'forgot' && (
                    <Field
                      id="mdp"
                      label="Mot de passe"
                      type="password"
                      required
                      minLength={8}
                      placeholder={mode === 'login' ? 'Votre mot de passe' : 'Au moins 8 caractères'}
                      autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                      hint={mode === 'signup' ? 'Au moins 8 caractères, dont un chiffre.' : null}
                      right={
                        mode === 'login' ? (
                          <button
                            type="button"
                            onClick={() => changerMode('forgot')}
                            className="text-[12.5px] font-medium text-brand-text"
                          >
                            Mot de passe oublié ?
                          </button>
                        ) : null
                      }
                      value={motDePasse}
                      onChange={(e) => setMotDePasse(e.target.value)}
                    />
                  )}
                  {mode === 'signup' && (
                    <label className="flex items-start gap-2 text-[12.5px] text-txt2 leading-relaxed cursor-pointer">
                      <input
                        type="checkbox"
                        required
                        checked={cguOk}
                        onChange={(e) => setCguOk(e.target.checked)}
                        className="w-4 h-4 mt-0.5 accent-brand shrink-0"
                      />
                      {/* [US-090 / CA20] Le consentement nomme explicitement
                          Google comme fournisseur d'identité et les données
                          récupérées. Les liens restent inertes tant que les
                          documents n'existent pas — leur rédaction relève
                          d'US-132 (RGPD & conformité), cf.
                          docs/RGPD_FEDERATION_GOOGLE.md. */}
                      <span>
                        J'accepte les <a href="#" className="text-brand-text font-semibold">conditions d'utilisation</a>{' '}
                        et la <a href="#" className="text-brand-text font-semibold">politique de confidentialité</a>.
                        {googleActif && (
                          <>
                            {' '}En choisissant « Continuer avec Google », j'accepte que Google agisse comme
                            fournisseur d'identité et transmette à Assistant Potager mon identifiant technique
                            de compte, mon adresse e-mail et mon nom.
                          </>
                        )}
                      </span>
                    </label>
                  )}

                  {error && <p className="text-red text-[13px]">{error}</p>}
                  {errorCode === 'EMAIL_NOT_VERIFIED' && (
                    <button
                      type="button"
                      onClick={handleResend}
                      disabled={loading}
                      className="text-brand text-[13px] text-left"
                    >
                      Renvoyer l'e-mail de vérification
                    </button>
                  )}
                  {message && <p className="text-brand text-[13px]">{message}</p>}

                  <button
                    type="submit"
                    disabled={loading || envoiForgotEnCours}
                    className="w-full h-12 rounded-xl bg-brand text-white dark:text-bg font-bold text-[15px] disabled:opacity-60"
                  >
                    {mode === 'forgot'
                      ? envoiForgotEnCours
                        ? '…'
                        : 'Envoyer le lien'
                      : loading
                        ? '…'
                        : mode === 'login'
                          ? 'Se connecter'
                          : 'Créer mon compte'}
                  </button>
                </form>
              )}

              {mode === 'forgot' ? (
                <button
                  onClick={() => changerMode('login')}
                  className="mt-4 w-full text-center text-[13px] text-txt2"
                >
                  Retour à la connexion
                </button>
              ) : (
                <div className="mt-4 text-center text-[13px] text-txt2">
                  {mode === 'login' ? 'Pas encore de compte ? ' : 'Vous avez déjà un compte ? '}
                  <button
                    onClick={() => changerMode(mode === 'login' ? 'signup' : 'login')}
                    className="font-bold text-brand-text"
                  >
                    {mode === 'login' ? 'Créer un compte' : 'Se connecter'}
                  </button>
                </div>
              )}

              {mode !== 'forgot' && (
                <div className="mt-3.5 flex items-center justify-center gap-1.5 text-[11.5px] text-txt3">
                  <KeyRound size={13} /> Connexion chiffrée · vos données restent privées
                </div>
              )}

              <div className="@[900px]/auth:hidden mt-5 pt-3.5 border-t border-border-soft flex items-center justify-center gap-3.5 flex-wrap">
                <span className="text-xs text-txt3">© 2026 Mon Potager</span>
                <a href="#" className="text-xs text-txt2">Mentions légales</a>
                <a href="#" className="text-xs text-txt2">Confidentialité</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
