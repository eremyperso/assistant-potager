// [US-354 / CA1-CA3] Tableau de bord — « Vue d'ensemble » sur le socle commun.
//
// La maquette « Socle commun » le fige sur QUATRE sections (D11) : « À faire aujourd'hui », « Récoltes
// possibles », « Météo · 3 jours » et « Dernières notes du carnet ». Une section vide disparaît (CA2) :
// il n'y a plus de placeholder, ni de personnalisation des widgets (US-077, US-078 retirées), ni de
// conseil du jour. Pas de barre d'outils (la coquille n'en dessine pas pour `bord`).
//
// Les lectures existent toutes : `GET /plan` (tâches du jour, US-328), `GET /meteo` (US-075) et
// `GET /historique` (notes). Le Mot de Gaston se calcule ici, sans modèle (`lib/accueilSocle.js`).
import { useEffect, useMemo, useState, useCallback } from 'react'
import { MapPinned, Send } from 'lucide-react'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { useDateRef } from '../context/AppContext.jsx'
import { useNavigation } from '../context/NavigationContext.jsx'
import { useDeclarerEcran } from '../context/CoquilleContext.jsx'
import { useFiches } from '../hooks/useFiches.jsx'
import {
  aFaireAujourdhui, recoltesPossibles, meteoTroisJours, dernieresNotes, motDuTableauDeBord,
  contexteTableauDeBord, NB_RECOLTES_ACCUEIL,
} from '../lib/accueilSocle.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import ModalModifierPotager from '../components/ModalModifierPotager.jsx'
import LierTelegram from '../components/LierTelegram.jsx'
import { EnTeteSection, ListeSocle, LigneSocle } from '../components/SectionSocle.jsx'
import { Btn, InfoBanner } from '../components/ui'
import NoteCarnet from '../components/ui/NoteCarnet.jsx'

const aujourdhuiIso = () => new Date().toISOString().slice(0, 10)

/** « Météo · 3 jours » : trois tuiles, le jour de gel en ambre. Sans localisation, l'invitation à la renseigner. */
function SectionMeteo({ jours, localisationManquante, onLocaliser }) {
  if (localisationManquante) {
    return (
      <section>
        <EnTeteSection titre="Météo · 3 jours" />
        <div className="rounded-[14px] border border-border bg-card px-4 py-4 text-center">
          <MapPinned size={22} aria-hidden="true" className="mx-auto mb-2 text-brand" />
          <p className="text-[13px] text-txt2">Renseignez la ville de ce potager pour afficher sa météo.</p>
          <Btn kind="soft" small className="mt-3" onClick={onLocaliser}>Modifier le potager</Btn>
        </div>
      </section>
    )
  }
  if (!jours.length) return null
  return (
    <section>
      <EnTeteSection titre="Météo · 3 jours" />
      <div className="grid grid-cols-3 gap-2">
        {jours.map((j) => (
          <div
            key={j.cle} data-gel={j.gel || undefined}
            className={`rounded-[12px] border px-2.5 py-2 text-[12px] ${j.gel ? 'border-amber bg-amber-soft text-amber-text' : 'border-border bg-card text-txt2'}`}
          >
            {j.nom}
            <b className={`block text-[15px] ${j.gel ? 'text-amber-text' : 'text-txt'}`}>{j.libelle}</b>
            {j.texte}
          </div>
        ))}
      </div>
    </section>
  )
}

export default function Dashboard({ refresh }) {
  const { potagerActif, potagerId } = usePotager()
  const { dateRef } = useDateRef()
  const { aller } = useNavigation()
  const { ouvrirCulture } = useFiches()   // [US-355 / CA1] la fiche commune, dans le panneau partagé

  const [plan, setPlan] = useState(null)
  const [meteo, setMeteo] = useState(null)
  const [evenements, setEvenements] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [modaleLocalisation, setModaleLocalisation] = useState(false)

  // [US-091 / CA14] Bandeau de relance tant que le compagnon Telegram n'est pas activé : ce n'est pas
  // une section du tableau de bord, il reste.
  const [telegramLie, setTelegramLie] = useState(true)   // true par défaut : pas de flash le temps du premier chargement
  const [modaleTelegram, setModaleTelegram] = useState(false)
  const chargerIdentite = useCallback(() => {
    api.moi().then((m) => setTelegramLie(m.telegram_lie === true)).catch(() => {})
  }, [])
  useEffect(() => { chargerIdentite() }, [chargerIdentite])

  async function charger() {
    setLoading(true); setError(null)
    try {
      // Le plan est la lecture qui compte ; la météo et les notes sont facultatives : leur échec retire
      // la section (une section absente ne dit rien de faux), il ne casse pas l'écran.
      const [p, m, h] = await Promise.all([
        api.plan(dateRef, potagerId),
        api.meteo().catch(() => null),
        api.historique({ action: 'observation', limit: 12, ...(potagerId ? { potager_id: potagerId } : {}) }).catch(() => null),
      ])
      setPlan(p); setMeteo(m); setEvenements(h?.evenements ?? [])
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { charger() }, [refresh, dateRef, potagerId]) // eslint-disable-line react-hooks/exhaustive-deps

  const jourRef = plan?.date_ref_effective || dateRef || aujourdhuiIso()
  const aFaire = useMemo(() => aFaireAujourdhui(plan), [plan])
  const recoltes = useMemo(() => recoltesPossibles(plan), [plan])
  const jours = useMemo(() => meteoTroisJours(meteo), [meteo])
  const notes = useMemo(() => dernieresNotes(evenements, aujourdhuiIso()), [evenements])
  const mot = useMemo(() => motDuTableauDeBord({ meteo, plan }), [meteo, plan])

  // [CA3] Le mot et la ligne de contexte vont à la coquille ; le tableau de bord n'a pas de barre.
  useDeclarerEcran({
    entete: { contexte: contexteTableauDeBord(jourRef, meteo) },
    mot,
  }, [JSON.stringify(mot), jourRef, meteo?.temp_actuelle, meteo?.label])


  if (loading) return <LoadingSkeleton lines={5} />
  if (error) return <ApiError message={error} onRetry={charger} />

  const colonneGauche = (
    <div className="flex flex-col gap-[18px]">
      {aFaire.length > 0 && (
        <section>
          <EnTeteSection titre={`À faire aujourd’hui · ${aFaire.length}`} />
          <ListeSocle>
            {aFaire.map((l) => (
              <LigneSocle
                key={l.cle} etape={l.etape} prevue={l.type === 'due'} due={l.du} emoji={l.emoji}
                titre={l.titre} detail={l.detail} nomAccessible={l.nomAccessible}
                onOuvrir={() => ouvrirCulture(l.selection)}
              />
            ))}
          </ListeSocle>
        </section>
      )}
      {recoltes.length > 0 && (
        <section>
          <EnTeteSection titre={`Récoltes possibles · ${recoltes.length}`} lien="Tout voir" onLien={() => aller('cultures')} />
          <ListeSocle>
            {recoltes.slice(0, NB_RECOLTES_ACCUEIL).map((l) => (
              <LigneSocle
                key={l.cle} etape={l.etape} emoji={l.emoji} titre={l.titre} detail={l.detail}
                nomAccessible={l.nomAccessible} onOuvrir={() => ouvrirCulture(l.selection)}
              />
            ))}
          </ListeSocle>
        </section>
      )}
    </div>
  )

  const colonneDroite = (
    <div className="flex flex-col gap-[18px]">
      <SectionMeteo
        jours={jours} localisationManquante={Boolean(meteo?.localisation_manquante)}
        onLocaliser={() => setModaleLocalisation(true)}
      />
      {notes.length > 0 && (
        <section>
          <EnTeteSection titre="Dernières notes du carnet" lien="Journal" onLien={() => aller('journal')} />
          <div className="flex flex-col gap-2">
            {notes.map((n) => (
              <NoteCarnet key={n.cle} texte={n.texte} dicte={null} date={n.date} lieu={n.lieu} />
            ))}
          </div>
        </section>
      )}
    </div>
  )

  const vide = !aFaire.length && !recoltes.length && !jours.length && !notes.length && !meteo?.localisation_manquante

  return (
    <div className="@container/dash">
      {!telegramLie && (
        <InfoBanner
          className="mb-4" tint="blue" icon={Send} dismissible={false}
          title="Activez votre compagnon de terrain"
          body="Dictez vos observations à la voix et recevez vos rappels directement sur Telegram."
          action={<Btn kind="primary" small onClick={() => setModaleTelegram(true)}>Activer</Btn>}
        />
      )}

      {/* [CA1] Deux colonnes à partir de 700 px de conteneur, sinon une. */}
      {vide ? (
        <p className="py-10 text-center text-[13px] text-txt3">Rien à signaler pour l’instant.</p>
      ) : (
        <div className="grid gap-[18px] @[700px]/dash:grid-cols-2 @[700px]/dash:items-start">
          {colonneGauche}
          {colonneDroite}
        </div>
      )}

      {modaleLocalisation && potagerActif && (
        <ModalModifierPotager potager={potagerActif} onClose={() => setModaleLocalisation(false)} />
      )}
      {modaleTelegram && (
        <LierTelegram
          telegramLie={telegramLie}
          onClose={() => { setModaleTelegram(false); chargerIdentite() }}
        />
      )}
    </div>
  )
}
