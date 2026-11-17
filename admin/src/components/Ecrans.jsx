import { useState } from 'react'
import { Lock, WifiOff, Loader2 } from 'lucide-react'

function Cadre({ children }) {
  return (
    <main className="min-h-screen grid place-items-center px-4 py-8 bg-bg">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card shadow-card p-6 text-center">
        {children}
      </div>
    </main>
  )
}

export function EcranChargement() {
  return (
    <Cadre>
      <Loader2 className="mx-auto animate-spin text-brand" size={28} aria-hidden="true" />
      <p className="mt-3 text-sm text-txt2" role="status">Ouverture de Pilotage…</p>
    </Cadre>
  )
}

/** Un compte qui n'est pas l'administrateur : aucune donnée n'est chargée [US-311 / CA3]. */
export function EcranAccesReserve({ compte, surDeconnexion }) {
  return (
    <Cadre>
      <Lock className="mx-auto text-amber" size={30} aria-hidden="true" />
      <h1 className="mt-3 font-serif text-xl font-semibold text-txt">Accès réservé</h1>
      <p className="mt-2 text-sm text-txt2">
        Pilotage est réservé à l'administrateur de la plateforme.
        {compte?.email ? <> Vous êtes connecté avec <strong className="text-txt">{compte.email}</strong>.</> : null}
      </p>
      <button type="button" onClick={surDeconnexion}
        className="mt-5 w-full rounded-lg border border-border bg-card-alt px-4 py-2.5 text-sm font-medium text-txt hover:border-brand">
        Changer de compte
      </button>
    </Cadre>
  )
}

/** L'API est injoignable avant même de savoir qui se connecte : hors ligne, pas de données. */
export function EcranHorsLigne({ surReessai }) {
  return (
    <Cadre>
      <WifiOff className="mx-auto text-txt3" size={30} aria-hidden="true" />
      <h1 className="mt-3 font-serif text-xl font-semibold text-txt">Pas de connexion</h1>
      <p className="mt-2 text-sm text-txt2">
        Pilotage s'ouvre hors ligne, mais n'a aucune donnée à montrer : les chiffres
        ne sont jamais gardés sur l'appareil.
      </p>
      <button type="button" onClick={surReessai}
        className="mt-5 w-full rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-deep">
        Réessayer
      </button>
    </Cadre>
  )
}

export function EcranConnexion({ surConnexion }) {
  const [email, setEmail] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)

  async function soumettre(evenement) {
    evenement.preventDefault()
    setEnvoi(true)
    setErreur('')
    try {
      await surConnexion(email.trim(), motDePasse)
    } catch (e) {
      setErreur(e.statut === 0 ? "L'API est injoignable." : e.message || 'Connexion impossible.')
      setEnvoi(false)
    }
  }

  return (
    <Cadre>
      <h1 className="font-serif text-xl font-semibold text-txt">Pilotage</h1>
      <p className="mt-1 text-sm text-txt2">Connectez-vous avec votre compte administrateur.</p>
      <form onSubmit={soumettre} className="mt-5 space-y-3 text-left">
        <label className="block text-sm text-txt2">
          Adresse e-mail
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-txt focus:border-brand focus:outline-none" />
        </label>
        <label className="block text-sm text-txt2">
          Mot de passe
          <input type="password" autoComplete="current-password" required value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-txt focus:border-brand focus:outline-none" />
        </label>
        {erreur ? <p role="alert" className="text-sm text-red">{erreur}</p> : null}
        <button type="submit" disabled={envoi}
          className="w-full rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-deep disabled:opacity-60">
          {envoi ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>
    </Cadre>
  )
}
