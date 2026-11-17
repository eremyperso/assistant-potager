/** Une barre de part (6 px), comme dans le tableau de ventilation de la maquette d'US-318. */
function BarrePart({ part }) {
  const pc = Math.max(0, Math.min(100, (part || 0) * 100))
  return (
    <i aria-hidden="true" className="relative mt-1.5 block h-1.5 w-full overflow-hidden rounded-[3px] bg-card-alt">
      <b className="absolute inset-y-0 left-0 rounded-[3px] bg-[color:var(--serie-1)]" style={{ width: `${pc}%` }} />
    </i>
  )
}

// Le tableau n'apparaît que si la carte a la place de ses colonnes (container query) : plus il en a, plus tard.
// Chaque variante est écrite en entier pour que Tailwind la voie.
const TABLEAU = {
  court: { table: 'hidden w-full border-collapse text-[13px] tabular-nums @lg:table', cartes: 'flex flex-col tabular-nums @lg:hidden' },
  moyen: { table: 'hidden w-full border-collapse text-[13px] tabular-nums @2xl:table', cartes: 'flex flex-col tabular-nums @2xl:hidden' },
  large: { table: 'hidden w-full border-collapse text-[13px] tabular-nums @4xl:table', cartes: 'flex flex-col tabular-nums @4xl:hidden' },
}
const gabarit = (nbColonnes) => (nbColonnes <= 3 ? TABLEAU.court : nbColonnes <= 5 ? TABLEAU.moyen : TABLEAU.large)

const ELEVE = (
  <span className="ml-1.5 inline-flex rounded-full bg-amber-soft px-2 py-px align-middle text-[11px] font-bold text-txt">usage élevé</span>
)

function Ouvrir({ ligne }) {
  if (!ligne.surOuvrir) return null
  return (
    <button type="button" onClick={() => ligne.surOuvrir(ligne)} aria-label={`Ouvrir la fiche : ${ligne.titre}`}
      className="mt-0.5 block min-h-[28px] text-[12.5px] font-bold text-brand-text">
      Ouvrir la fiche →
    </button>
  )
}

const FAIBLE = (
  <span className="ml-1.5 inline-flex rounded-full bg-card-alt px-2 py-px align-middle text-[11px] font-bold text-txt2">échantillon faible</span>
)

/**
 * Tableau de données de la maquette d'US-318 (même carte, mêmes en-têtes, mêmes lignes de cartes sous
 * le seuil du conteneur que le tableau de ventilation de la vue Consommation), pour des colonnes que
 * le tableau de ventilation n'a pas [US-313, US-314, US-315]. Un tableau quand la carte a la place
 * (container query), une liste de cartes sinon : jamais de défilement horizontal à 360 px.
 *
 * - `colonnes` : `[{ id, libelle, mono? }]`, dans l'ordre ; la première colonne est `premiereColonne`.
 * - `lignes` : `[{ cle, titre, mono?, cellules: { [id]: texte }, faible?, note?, part? }]`.
 *   `faible` marque « échantillon faible » ; `part` (0-1) ajoute la barre de part ; `note` est une
 *   précision sous la ligne (issues hors des quatre connues, échanges non chiffrés…).
 */
export default function TableauDonnees({ titre, sousTitre, premiereColonne, colonnes, lignes, messageVide = 'Rien à afficher sur la période.', vide = false, pied = null }) {
  const entete = (
    <div className="mb-2.5">
      <h3 className="font-serif text-base font-semibold leading-tight text-txt">{titre}</h3>
      {sousTitre && !vide ? <p className="mt-0.5 text-xs text-txt2">{sousTitre}</p> : null}
    </div>
  )
  if (vide || !lignes.length) {
    return (
      <section className="rounded-2xl border border-border bg-card p-3.5 shadow-card">
        {entete}
        <div className="flex flex-col items-center gap-1.5 px-3 py-[22px] text-center text-[13px] text-txt2">
          <b className="text-sm text-txt">Aucune donnée</b>
          <span>{messageVide}</span>
        </div>
      </section>
    )
  }
  const th = 'border-b border-border px-2 py-1.5 text-right text-[11.5px] font-bold text-txt2 whitespace-nowrap first:text-left'
  const td = 'border-b border-border-soft p-2 whitespace-nowrap'
  const avecPart = lignes.some((l) => l.part !== undefined)
  const classes = gabarit(colonnes.length + 1)
  return (
    <section className="@container rounded-2xl border border-border bg-card p-3.5 shadow-card">
      {entete}

      <table className={classes.table}>
        <thead>
          <tr>
            <th scope="col" className={th}>{premiereColonne}</th>
            {colonnes.map((c) => <th key={c.id} scope="col" className={th}>{c.libelle}</th>)}
          </tr>
        </thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l.cle}>
              <th scope="row" className={`${td} text-left font-normal`}>
                {l.mono ? <code className="font-mono text-[12.5px] text-txt">{l.titre}</code> : <span className="font-semibold text-txt">{l.titre}</span>}
                {l.faible ? FAIBLE : null}
                {l.usageEleve ? ELEVE : null}
                {l.note && !l.usageEleve ? <span className="block whitespace-normal text-[11.5px] text-txt2">{l.note}</span> : null}
                <Ouvrir ligne={l} />
              </th>
              {colonnes.map((c, i) => (
                <td key={c.id} className={`${td} text-right`}>
                  {c.mono ? <code className="font-mono text-[12.5px]">{l.cellules[c.id]}</code> : l.cellules[c.id]}
                  {avecPart && i === colonnes.length - 1 && l.part !== undefined ? <span className="ml-1.5 inline-block w-[52px] align-middle"><BarrePart part={l.part} /></span> : null}
                </td>
              ))}
            </tr>
          ))}
          {pied}
        </tbody>
      </table>

      <ul className={classes.cartes}>
        {lignes.map((l) => (
          <li key={l.cle} className="border-t border-border-soft px-0.5 py-2.5 first:border-t-0">
            <div className="flex items-baseline justify-between gap-2.5">
              {l.mono ? <code className="break-all font-mono text-[13px] font-semibold text-txt">{l.titre}</code> : <b className="text-[13px] text-txt">{l.titre}</b>}
              {l.faible ? FAIBLE : null}{l.usageEleve ? ELEVE : null}
            </div>
            {l.part !== undefined ? <BarrePart part={l.part} /> : null}
            <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-txt2">
              {colonnes.map((c) => (
                <div key={c.id} className="flex items-baseline justify-between gap-2">
                  <dt>{c.libelle}</dt>
                  <dd className="font-semibold text-txt">{l.cellules[c.id]}</dd>
                </div>
              ))}
            </dl>
            {l.note && !l.usageEleve ? <p className="mt-1 text-[11.5px] text-txt2">{l.note}</p> : null}
            <Ouvrir ligne={l} />
          </li>
        ))}
      </ul>
    </section>
  )
}
