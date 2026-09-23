import { PisteDesPlaces, IconeCote, PictoCulture } from './PisteDesPlaces.jsx'
import { PastillePhase } from './PastillePhase.jsx'
import { palettePhases, gabarit, capitaliser } from '../../lib/planVue.js'

/**
 * Une ligne de rang dans une carte du Plan [US-200 / V2, V6, V12, V16 ;
 * US-228 / P5, P10].
 *
 * C'est une **grille**, pas une suite de blocs : toutes les lignes d'une carte
 * partagent le même gabarit de colonnes, donc les noms s'alignent, les pistes
 * commencent toutes au même endroit et les restes se lisent en colonne.
 *
 *   R1 · Tomate cœur de bœuf · ●●●○○○○ · reste 15 · En place
 *            9 plants · ↔ 50 cm
 *
 * [US-228 / P10] La quantité a quitté sa colonne pour la **seconde ligne du
 * libellé**, avec l'espacement sur le rang quand il est connu : la place ainsi
 * rendue va à la piste, qui a besoin de largeur pour rester lisible.
 *
 * [V16] La phase reste écrite à chaque rang, même sur une carte étroite.
 *
 * [CA10] La ligne est focalisable et son nom accessible dit tout, places
 * comprises : « Rang 1, tomate, 9 plants sur 24 places, 15 restantes, en place ».
 * Le contenu visible est masqué aux technologies d'assistance, qui liraient
 * sinon deux fois la même chose.
 *
 * [US-201] `onSelect` est la seule prise laissée aux interactions à venir.
 */
export function RangPlan({
  rang,
  palette = palettePhases(),
  taille = 'normale',
  onSelect = undefined,
}) {
  const g = gabarit(taille)
  const nom = capitaliser(rang.culture)
  const reste = rang.reste

  return (
    <button
      type="button"
      aria-label={rang.nomAccessible}
      onClick={onSelect}
      // [CA6] Deux gabarits, par largeur de CARTE (container query) :
      //  - sous 560 px, trois zones empilées — libellé, piste, reste — le
      //    numéro restant en marge ;
      //  - au-delà, tout sur une ligne, la piste au centre.
      // 44 px de cible d'appui sur mobile, piste comprise.
      className={`w-full text-left grid items-center gap-x-2 gap-y-1.5 py-2 min-h-[44px] rounded-lg
          grid-cols-[24px_minmax(0,1fr)_auto]
          @[560px]/carte:grid-cols-[28px_22px_minmax(0,1.25fr)_minmax(0,1fr)_80px_104px]
          @[560px]/carte:gap-x-3 @[560px]/carte:gap-y-0
                  hover:bg-card-alt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand`}
    >
      <span aria-hidden="true" className="contents">
        {/* [V12, A5] Numéro dans l'ordre d'installation, abrégé à toutes les
            largeurs. La légende de l'écran dit une fois ce qu'il signifie. */}
        <span
          className={`${g.numero} font-bold tabular-nums self-start @[560px]/carte:self-center
                      row-span-3 @[560px]/carte:row-span-1
                      ${rang.suite ? 'text-txt3 font-medium' : 'text-txt2'}`}
        >
          {rang.numeroCourt}
        </span>

        {/* [V6, P10] Culture et variété, puis la quantité et l'espacement. */}
        <span className="hidden @[560px]/carte:flex col-start-2 row-start-1 items-center justify-center">
          {!rang.libre && <PictoCulture culture={rang.culture} variete={rang.variete} />}
        </span>
        <span className="min-w-0 col-start-2 row-start-1 @[560px]/carte:col-start-3">
          <span className="block break-words [overflow-wrap:anywhere]">
            {rang.libre ? (
              <span className={`${g.libelle} italic text-txt3`}>libre</span>
            ) : (
              <>
                <span className={`${g.libelle} font-semibold text-txt`}>{nom}</span>
                {rang.variete && <span className={`${g.libelle} text-txt2`}> {rang.variete}</span>}
              </>
            )}
          </span>
          <span className="block text-[11.5px] text-txt3 text-pretty">
            {/* [P9] Un rang libre dit sa longueur et, s'il y en a une, la
                capacité d'exemple nommée — « 12 m · ex. 24 tomates ». */}
            {rang.libre ? rang.sousLibelleLibre : <span className="whitespace-nowrap">{rang.sousLibelle?.quantite}</span>}
            {!rang.libre && rang.sousLibelle?.espacement && (
              <span className="whitespace-nowrap">
                {' · '}
                <IconeCote taille={10} className="inline-block align-[-1px] mr-[2px]" />
                {rang.sousLibelle.espacement}
              </span>
            )}
          </span>
        </span>

        {/* [P1] La piste : deuxième ligne à l'étroit, colonne centrale au large. */}
        <span className="min-w-0 col-start-2 col-span-2 row-start-2 @[560px]/carte:col-start-4 @[560px]/carte:col-span-1 @[560px]/carte:row-start-1">
          <PisteDesPlaces
            piste={rang.piste}
            culture={rang.culture}
            variete={rang.variete}
            phase={rang.phase}
            mode={rang.mode}
            longueur={rang.longueur}
            segments={rang.segments}
            palette={palette}
            taille={taille}
          />
        </span>

        {/* [P5] La colonne de reste : « libre 15 », « 4 en trop » en
            teinte d'alerte, « 8 places ? » en mode dégradé — ou rien. */}
        <span
          className="col-start-2 col-span-2 row-start-3 @[560px]/carte:col-start-5 @[560px]/carte:col-span-1
                     @[560px]/carte:row-start-1 text-left @[560px]/carte:text-right
                     min-w-0 tabular-nums break-words"
        >
          {!rang.libre && reste ? (
            <span className={`text-[12px] ${reste.alerte ? 'text-red font-semibold' : 'text-txt2'}`}>
              {reste.prefixe && `${reste.prefixe === 'reste' ? 'libre' : reste.prefixe} `}
              <span className={`${g.libelle} font-semibold ${reste.alerte ? 'text-red' : 'text-txt'}`}>
                {reste.valeur}
              </span>{' '}
              {reste.prefixe !== 'reste' && <span className="text-txt3">{reste.unite}</span>}
            </span>
          ) : null}
        </span>
        <span className="col-start-3 row-start-1 justify-self-end @[560px]/carte:col-start-6">
          {rang.libre ? (
            <span className="inline-block rounded-full border border-dashed border-txt3/60 px-2.5 py-0.5 text-[11.5px] text-txt2">Libre</span>
          ) : <PastillePhase ligne={rang} />}
        </span>
      </span>
    </button>
  )
}

export default RangPlan
