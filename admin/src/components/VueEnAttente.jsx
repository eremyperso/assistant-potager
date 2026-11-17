import { Hourglass } from 'lucide-react'
import { vue as trouverVue } from '../lib/navigation.js'

/** Les vues livrées par une autre US : la coquille les annonce, elle ne les simule pas. */
export default function VueEnAttente({ vue }) {
  const v = trouverVue(vue)
  return (
    <section className="rounded-2xl border border-dashed border-border bg-card p-8 text-center">
      <Hourglass className="mx-auto text-txt3" size={28} aria-hidden="true" />
      <h2 className="mt-3 font-serif text-lg font-semibold text-txt">{v.libelle}</h2>
      <p className="mt-1 text-sm text-txt2">Cette vue n'est pas encore ouverte ({v.us}). La période et les filtres choisis lui seront appliqués.</p>
    </section>
  )
}
