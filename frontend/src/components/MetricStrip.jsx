// ── Strip d'indicateurs (3 zones fixes) ────────────────────────────────────────
// Template repris de l'onglet Pépinière : une carte unique bordée, séparateurs
// verticaux fins entre indicateurs, gros chiffre + libellé.
//
// Le découpage occupe toujours `slots` zones égales (3 par défaut), même si
// `metrics` en fournit moins : les zones restantes sont laissées vides, prêtes
// à accueillir un futur indicateur sans changer la mise en page.

export default function MetricStrip({ metrics, slots = 3 }) {
  const items = [...metrics]
  while (items.length < slots) items.push(null)

  return (
    <div
      className="rounded-2xl border border-g-brd flex mb-3"
      style={{ background: 'var(--g-card)' }}
    >
      {items.map((m, i) => (
        <div key={m?.label ?? `empty-${i}`} className="flex-1 relative">
          {i > 0 && (
            <div className="absolute left-0 top-2.5 bottom-2.5 w-px" style={{ background: 'var(--g-brd)' }} />
          )}
          {m && (
            <div className="py-3 text-center">
              <div className="text-4xl font-bold tracking-tight leading-none" style={{ color: m.color || 'var(--g-pri)' }}>
                {m.value}
              </div>
              <div className="text-[11px] mt-1.5" style={{ color: 'var(--g-sec)' }}>{m.label}</div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
