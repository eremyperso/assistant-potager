// [US-215] L'onglet « Aujourd'hui » de la Pépinière — « l'écran qu'on ouvre en
// passant » (wireframe v2 § 3) : le bandeau des quatre réponses, puis les lots en
// cours du plus urgent au plus calme, chacun avec le bouton de son action suggérée.
//
// Rien n'est calculé ici : échéances, action suggérée, rang d'urgence et résumé
// viennent de `GET /pepiniere/lots` (US-214) ; leur mise en forme vit dans
// `lib/pepiniere.js` (CA15). Les boutons DÉPOSENT un geste dans la file
// (`BoutonGeste`, US-224) : aucune redirection vers Telegram, une notification
// confirme le dépôt, le compagnon le propose de son côté.
//
// Rendu : maquette figée US-216 du 14/10/2026 (ligne de lot en trois colonnes en
// desktop, carte à 375 px). Container queries, jamais de breakpoint (CA12).
import { ArrowRightLeft, CalendarClock, Flower2, Sprout, Shovel, X, Archive } from 'lucide-react'
import BoutonGeste from './BoutonGeste.jsx'
import { Btn } from './ui'
import { gestePrepare } from '../lib/ficheLot.js'
import {
  boutonDeLigne, cartesReponses, echeanceCourte, filtrerLots, libelleNumeroLot, lotsDuJour,
  quantiteLigne, sousTitreLigne, basculerFiltre,
} from '../lib/pepiniere.js'

const ICONES = { a_repiquer: Sprout, a_endurcir: CalendarClock, prets_pour_le_plan: Shovel, a_semer: Flower2 }
const ICONE_GESTE = { repiquer: Sprout, mettre_en_terre: Shovel, cloturer: Archive, deplacer: ArrowRightLeft }

/** [CA3, CA4] Une des quatre réponses. Filtrante : un bouton à bascule (`aria-pressed`). */
export function CarteReponsePepiniere({ carte, actif, onBasculer, onOuvrirCulture }) {
  const Icone = ICONES[carte.cle] ?? Sprout
  const vide = carte.valeur === 'rien'
  const teinte = carte.alerte
    ? 'border-amber bg-amber-soft'
    : actif ? 'border-brand bg-brand-soft' : 'border-border bg-card'
  const contenu = (
    <>
      <span className={`flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[.05em] ${carte.alerte ? 'text-amber' : 'text-txt3'}`}>
        <Icone size={14} aria-hidden="true" />
        {carte.titre}
      </span>
      <span className={`font-serif text-[19px] font-semibold leading-tight ${vide ? 'text-txt3' : 'text-txt'}`}>
        {carte.valeur}
      </span>
      {carte.detail && <span className="text-[12px] text-txt2 leading-snug">{carte.detail}</span>}
    </>
  )
  if (!carte.filtrable) {
    // « À semer » ne filtre pas : chaque culture ouvre sa fiche (CA4).
    return (
      <div className={`flex flex-col gap-1 rounded-[14px] border p-3 min-h-[44px] ${teinte}`}>
        {contenu}
        {carte.cultures?.length > 0 && (
          <ul className="flex flex-wrap gap-x-2 gap-y-1 mt-0.5">
            {carte.cultures.map((c) => (
              <li key={c.culture}>
                <button
                  type="button"
                  onClick={() => onOuvrirCulture?.(c.culture)}
                  className="min-h-[32px] text-[12.5px] font-semibold text-brand-text underline underline-offset-2 capitalize"
                  title={c.fenetre ? `Fenêtre de semis : ${c.fenetre}` : undefined}
                >
                  {c.culture}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    )
  }
  return (
    <button
      type="button"
      aria-pressed={actif}
      onClick={() => onBasculer(carte.cle)}
      className={`text-left flex flex-col gap-1 rounded-[14px] border p-3 min-h-[44px] transition-colors ${teinte} ${actif ? 'ring-2 ring-brand' : ''}`}
    >
      {contenu}
    </button>
  )
}

/**
 * [CA5, CA6, CA12, CA14] Une ligne de lot. Trois colonnes et le bouton en
 * desktop ; une carte de deux ou trois lignes sous 40rem de conteneur.
 */
export function LigneLot({ lot, selectionne, nbPepinieres, dateRef, onOuvrir }) {
  const ech = echeanceCourte(lot)
  const bouton = boutonDeLigne(lot, { nbPepinieres })
  const retard = ech.ton === 'retard'
  const dormant = Boolean(lot.echeances?.dormance?.est_dormant)
  const numero = libelleNumeroLot(lot)
  const fond = selectionne ? 'bg-brand-soft' : retard ? 'bg-amber-soft/50' : ''
  return (
    <li
      className={`relative grid gap-x-3.5 gap-y-1 items-center px-3.5 py-3 border-b border-border-soft last:border-b-0
        grid-cols-[minmax(0,1fr)_auto]
        @[40rem]/liste:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1.3fr)_10.5rem]
        ${fond} ${dormant ? 'opacity-60' : ''}`}
    >
      {/* Le liseré d'alerte double la teinte : la couleur ne porte jamais seule l'information. */}
      {retard && <span aria-hidden="true" className="absolute left-0 inset-y-0 w-[3px] bg-amber" />}
      <button
        type="button"
        onClick={() => onOuvrir(lot)}
        className="text-left min-w-0 min-h-[44px] flex flex-col justify-center"
        aria-label={`Ouvrir la fiche du lot ${lot.numero_lot ?? lot.culture}`}
      >
        <span className="font-serif text-[15px] font-semibold text-txt truncate capitalize">
          {numero && <span className="mr-1">{numero} ·</span>}{lot.culture}
          {lot.variete && <span className="font-sans font-normal italic text-[12.5px] text-txt2 normal-case"> {lot.variete}</span>}
        </span>
        <span className="text-[11.5px] text-txt3 mt-0.5 truncate">{sousTitreLigne(lot)}</span>
      </button>
      <span className="text-[12.5px] text-txt2 col-start-1 @[40rem]/liste:col-start-auto">{quantiteLigne(lot)}</span>
      <span
        className={`text-[12.5px] row-start-1 col-start-2 text-right @[40rem]/liste:row-start-auto @[40rem]/liste:col-start-auto @[40rem]/liste:text-left ${retard ? 'font-bold text-amber' : 'font-medium text-txt2'}`}
        title={ech.raison}
      >
        {ech.texte}
      </span>
      <div className="col-span-2 @[40rem]/liste:col-span-1 flex justify-end">
        {bouton && (bouton.ouvreFiche ? (
          <Btn kind="ghost" small className="min-h-[44px]" aria-label={bouton.ariaLabel} onClick={() => onOuvrir(lot)}>
            {bouton.libelle}
          </Btn>
        ) : (
          <BoutonGeste
            geste={gestePrepare(bouton.geste)} dateRef={dateRef} ecran="pepiniere"
            libelle={bouton.libelle} ariaLabel={bouton.ariaLabel}
            kind={bouton.principal ? 'primary' : 'ghost'} small
            icone={ICONE_GESTE[bouton.geste.code] ?? Sprout}
            afficherPhrase={false} btnClassName="min-h-[44px]"
          />
        ))}
      </div>
    </li>
  )
}

/**
 * @param data        réponse de `GET /pepiniere/lots` (`lots`, `resume`, `pepinieres`)
 * @param etat        `{ q, bandeau }` — l'état d'écran rendu tel quel au retour (US-195)
 * @param emplacement filtre d'emplacement posé par une intention du Plan (CA9)
 */
export default function OngletAujourdhui({
  data, etat, setEtat, emplacement, onRetirerEmplacement, lotSelectionne, nbPepinieres,
  dateRef, onOuvrirLot, onOuvrirCulture,
}) {
  const enCours = lotsDuJour(data?.lots)
  const cartes = cartesReponses(data?.resume, enCours)
  const visibles = filtrerLots(enCours, { q: etat.q, emplacement, bandeau: etat.bandeau })
  const carteActive = cartes.find((c) => c.cle === etat.bandeau)

  return (
    <div className="flex flex-col gap-3.5">
      {/* [CA3] Le bandeau des quatre réponses : deux colonnes en dessous de 36rem, quatre au-dessus. */}
      <section aria-label="Ce qu'il y a à faire aujourd'hui" className="@container/bandeau">
        <div className="grid gap-2.5 grid-cols-2 @[36rem]/bandeau:grid-cols-4">
          {cartes.map((c) => (
            <CarteReponsePepiniere
              key={c.cle} carte={c} actif={etat.bandeau === c.cle}
              onBasculer={(cle) => setEtat({ bandeau: basculerFiltre(etat.bandeau, cle) })}
              onOuvrirCulture={onOuvrirCulture}
            />
          ))}
        </div>
      </section>

      {/* [CA4, CA9] Les filtres posés, en pastilles retirables. */}
      {(carteActive || emplacement) && (
        <div className="flex flex-wrap gap-2">
          {carteActive && (
            <button
              type="button" onClick={() => setEtat({ bandeau: null })}
              className="inline-flex items-center gap-1.5 min-h-[36px] px-3 rounded-full bg-brand-soft text-brand-text text-[12.5px] font-semibold"
            >
              {carteActive.titre} <X size={13} aria-hidden="true" /><span className="sr-only">— retirer le filtre</span>
            </button>
          )}
          {emplacement && (
            <button
              type="button" onClick={onRetirerEmplacement}
              className="inline-flex items-center gap-1.5 min-h-[36px] px-3 rounded-full bg-brand-soft text-brand-text text-[12.5px] font-semibold"
            >
              {emplacement} <X size={13} aria-hidden="true" /><span className="sr-only">— retirer le filtre d'emplacement</span>
            </button>
          )}
        </div>
      )}

      {/* [CA10] Aucun lot en cours : le bandeau reste, « À semer » compris. */}
      {enCours.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10 text-txt3">
          <Sprout size={32} aria-hidden="true" />
          <p className="text-[15px]">Aucun lot en cours</p>
        </div>
      ) : visibles.length === 0 ? (
        <p className="text-[13px] text-txt3 py-6 text-center">Aucun lot ne correspond à ces filtres.</p>
      ) : (
        <div className="@container/liste bg-card border border-border rounded-[14px] shadow-card overflow-hidden">
          <ul aria-label="Lots en cours, du plus urgent au plus calme">
            {visibles.map((lot) => (
              <LigneLot
                key={lot.lot_id} lot={lot} selectionne={lotSelectionne === lot.lot_id}
                nbPepinieres={nbPepinieres} dateRef={dateRef} onOuvrir={onOuvrirLot}
              />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
