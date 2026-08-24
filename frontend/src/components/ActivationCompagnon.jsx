// [US-091 / CA1-CA7] Écran d'activation du compagnon de terrain Telegram —
// étape dédiée, plein écran, affichée à l'issue du parcours d'onboarding du
// premier potager (US-058) une fois celui-ci créé (CA1) : un compte sans
// potager ne peut rien dicter (US-046 / CA5), le proposer avant mènerait à un
// bot qui refuse tout.
//
// Reframing éditorial (CA2) : Telegram n'est pas « un compte à connecter »,
// c'est « un compagnon de terrain à activer » — on vend la voix et les
// rappels, le mot Telegram n'apparaît qu'en réassurance basse.
//
// Jamais bloquante (CA6) : « Plus tard » mène directement au tableau de bord ;
// la relance persistante prend le relais (bandeau du tableau de bord, CA14).
import { Leaf, Send } from 'lucide-react'
import { useCodeLiaison, PanneauActivation } from './LierTelegram.jsx'

function LogoMark() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="w-[34px] h-[34px] rounded-[11px] bg-brand-soft flex items-center justify-center shrink-0">
        <Leaf size={20} className="text-brand" />
      </span>
      <span className="font-serif text-[18px] font-bold tracking-tight whitespace-nowrap text-txt">
        Mon Potager
      </span>
    </span>
  )
}

export default function ActivationCompagnon({ onSkip }) {
  // [Fix] Cet écran n'apparaît qu'une fois, juste après la création du premier
  // potager (cf. views/Onboarding.jsx) — aucun chemin n'y mène avec un compte
  // déjà lié, `telegramLie` vaut donc toujours `false` ici.
  const etat = useCodeLiaison(false)

  return (
    <div className="@container/act h-dvh bg-bg flex flex-col overflow-y-auto">
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-10">
        <div className="w-full max-w-[420px]">
          <div className="flex justify-center mb-6">
            <LogoMark />
          </div>

          <div className="text-center mb-6">
            <div className="w-14 h-14 rounded-2xl bg-brand-soft flex items-center justify-center mx-auto mb-4">
              <Send size={26} className="text-brand" />
            </div>
            {/* [CA2] Titre imposé — jamais « Connecter Telegram ». */}
            <h1 className="font-serif text-[24px] @[380px]/act:text-[26px] font-bold text-txt tracking-tight leading-[1.15]">
              Activez votre compagnon de terrain
            </h1>
            <p className="text-[13.5px] text-txt2 mt-2.5 leading-relaxed">
              Dictez vos observations à la voix depuis le potager, et recevez vos
              rappels d'arrosage et alertes gel directement sur votre téléphone.
            </p>
          </div>

          <PanneauActivation etat={etat} tailleQr={150} />

          {/* [CA6] Discret, jamais bloquant. */}
          <button
            type="button"
            onClick={onSkip}
            className="block mx-auto mt-5 text-[12.5px] font-semibold text-txt3"
          >
            Plus tard
          </button>

          {/* [CA2] Réassurance basse — seul endroit où « Telegram » apparaît. */}
          <p className="text-[11px] text-txt3 text-center mt-4 leading-relaxed">
            Gratuit, via Telegram. Aucun mot de passe à créer.
          </p>
        </div>
      </div>
    </div>
  )
}
