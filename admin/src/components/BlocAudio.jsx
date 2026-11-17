import { Mic, Volume2 } from 'lucide-react'
import { entier } from '../lib/format.js'

/** Bloc audio, à part des jetons [US-312 / CA6] : des secondes de dictée et des caractères de
 *  voix ne sont pas des jetons et ne s'additionnent à rien. */
export default function BlocAudio({ audio, vide = false }) {
  const n = (v) => (vide ? '0' : entier(v))
  return (
    <section aria-labelledby="titre-audio" className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
      <div className="mb-2.5">
        <h3 id="titre-audio" className="font-serif text-base font-semibold leading-tight text-txt">Audio</h3>
        <p className="mt-0.5 text-xs text-txt2">Ce ne sont pas des jetons : ne s'additionnent pas au reste</p>
      </div>
      <div className="grid grid-cols-2 gap-2.5 tabular-nums">
        <div className="rounded-xl bg-card-alt px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs text-txt2"><Mic size={15} aria-hidden="true" />Dictée</div>
          <div className="mt-0.5 text-xl font-bold text-txt">{n(audio.dictee.secondes)} s</div>
          <div className="text-xs text-txt2">{n(audio.dictee.appels)} dictée{audio.dictee.appels > 1 ? 's' : ''}</div>
        </div>
        <div className="rounded-xl bg-card-alt px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs text-txt2"><Volume2 size={15} aria-hidden="true" />Synthèse vocale</div>
          <div className="mt-0.5 text-xl font-bold text-txt">{n(audio.voix.caracteres)}</div>
          <div className="text-xs text-txt2">caractères · {n(audio.voix.appels)} lecture{audio.voix.appels > 1 ? 's' : ''}</div>
        </div>
      </div>
    </section>
  )
}
