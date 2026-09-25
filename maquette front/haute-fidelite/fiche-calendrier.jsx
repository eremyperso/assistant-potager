// US-183 — Fiche calendrier d'une culture + bloc « règle de confiance » (partagé US-180).
// Tokens et composants de la maquette figée : aucune couleur nouvelle.
const { useState } = React;

const CONF_LBL = { 3: 'Confiance élevée', 2: 'Confiance moyenne', 1: 'Confiance faible' };
const ETAT_REGLE = {
  ok: { ico: 'check', tint: 'brand', l: 'gagné' },
  ko: { ico: 'alert', tint: 'amber', l: 'perdu' },
  nd: { ico: 'help', tint: 'txt3', l: 'indéterminé' } };

function etoilesDe(score) { return score >= 75 ? 3 : score >= 45 ? 2 : 1; }

// Étoiles : texte ★/☆, encre du design system, jamais seules — le libellé est toujours à côté.
function Etoiles({ n, size = 17 }) {
  const W = useW();
  return (
    <span role="img" aria-label={`${n} étoile${n > 1 ? 's' : ''} sur 3 — ${CONF_LBL[n]}`} style={{ fontSize: size, letterSpacing: '.06em', lineHeight: 1, whiteSpace: 'nowrap' }}>
      <span style={{ color: W.txt }}>{'★'.repeat(n)}</span><span style={{ color: W.txt3 }}>{'☆'.repeat(3 - n)}</span>
    </span>);
}

function LigneRegle({ r }) {
  const W = useW();
  const e = ETAT_REGLE[r.etat];
  const c = e.tint === 'txt3' ? W.txt3 : W[e.tint];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, padding: '8px 0' }}>
      <span style={{ display: 'flex', flexShrink: 0, marginTop: 1 }}><Ico n={e.ico} c={c} s={15} w={2.2} /></span>
      <span style={{ flex: 1, minWidth: 0, fontSize: 12.5, lineHeight: 1.45, color: r.etat === 'nd' ? W.txt2 : W.txt }}>{r.motif}</span>
      <span style={{ flexShrink: 0, fontSize: 11.5, fontWeight: 700, color: r.etat === 'ok' ? W.txt2 : W.txt3, fontVariantNumeric: 'tabular-nums' }}>{r.pts} / {r.max}</span>
    </div>);
}

// Bloc « règle de confiance » — une seule taille, partagé entre la fiche (US-183)
// et la fiche « pourquoi deux étoiles » de la tuile du Plan (US-180).
function BlocConfiance({ score, regles, note }) {
  const W = useW();
  const [tout, setTout] = useState(false);
  const n = etoilesDe(score);
  const visibles = tout ? regles : regles.filter((r) => r.etat !== 'ok');
  const caches = regles.length - visibles.length;
  return (
    <div style={{ background: W.cardAlt, borderRadius: 14, padding: '13px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
        <Etoiles n={n} size={19} />
        <span style={{ fontSize: 14, fontWeight: 700, color: W.txt }}>{CONF_LBL[n]}</span>
        <span style={{ marginLeft: 'auto', fontSize: 11.5, fontWeight: 700, color: W.txt3, fontVariantNumeric: 'tabular-nums' }}>{score} / 100</span>
      </div>
      <div style={{ marginTop: 6, borderTop: `1px solid ${W.border}` }}>
        {visibles.map((r, i) => <LigneRegle key={i} r={r} />)}
      </div>
      {caches > 0 &&
      <button onClick={() => setTout(true)} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'none', border: 'none', padding: '4px 0 0', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 600, color: W.brandText }}>
        Voir les {regles.length} règles<Ico n="chevD" c={W.brandText} s={14} w={2} />
      </button>}
      {tout && caches === 0 && regles.some((r) => r.etat === 'ok') &&
      <button onClick={() => setTout(false)} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: 'none', border: 'none', padding: '4px 0 0', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 600, color: W.brandText }}>
        Ne garder que ce qui a coûté des points<Ico n="chevD" c={W.brandText} s={14} w={2} />
      </button>}
      {note && <div style={{ fontSize: 11.5, color: W.txt3, lineHeight: 1.5, marginTop: 8 }}>{note}</div>}
    </div>);
}

function SelecteurAction({ actions, value, onChange }) {
  const W = useW();
  if (actions.length < 2) return null;
  return (
    <div style={{ display: 'flex', gap: 4, background: W.cardAlt, borderRadius: 11, padding: 4, marginBottom: 12 }}>
      {actions.map((a) => { const on = a.k === value; return (
        <button key={a.k} onClick={() => onChange(a.k)} aria-pressed={on} style={{ flex: 1, minWidth: 0, padding: '8px 6px', borderRadius: 8, border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12.5, fontWeight: on ? 700 : 500, background: on ? W.card : 'transparent', color: on ? W.txt : W.txt2, boxShadow: on ? W.shadow : 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.l}</span>
          <Etoiles n={etoilesDe(a.score)} size={11} />
        </button>); })}
    </div>);
}

function SerieStat({ label, value, muted }) {
  const W = useW();
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 9.5, fontWeight: 700, color: W.txt3, textTransform: 'uppercase', letterSpacing: '.04em' }}>{label}</div>
      <div style={{ fontSize: 13.5, fontWeight: muted ? 500 : 700, color: muted ? W.txt3 : W.txt, marginTop: 2, lineHeight: 1.3 }}>{value}</div>
    </div>);
}

function CarteSerie({ s }) {
  const W = useW();
  const vide = !s.levee;
  return (
    <div style={{ background: W.card, border: `1px ${vide ? 'dashed' : 'solid'} ${W.border}`, borderRadius: 13, padding: 13 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Ico n="pin" c={W.txt3} s={15} />
        <span style={{ fontFamily: wserif, fontSize: 14.5, fontWeight: 600, color: W.txt }}>{s.parcelle}</span>
        <Badge tint={s.origine === 'plantation' ? 'brand' : 'blue'}>{s.origineL}</Badge>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: 10, marginTop: 11, paddingTop: 10, borderTop: `1px solid ${W.borderSoft}` }}>
        <SerieStat label="Levée attendue" value={s.levee || '—'} muted={!s.levee} />
        <SerieStat label="1ʳᵉ récolte attendue" value={s.recolte || '—'} muted={!s.recolte} />
        <SerieStat label="Reste à courir" value={s.reste || '—'} muted={!s.reste} />
      </div>
      {s.ecart &&
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 10, background: W.amberSoft, borderRadius: 9, padding: '7px 10px' }}>
        <Ico n="clock" c={W.amber} s={14} />
        <span style={{ fontSize: 12, color: W.mode === 'dark' ? W.txt : W.amber, lineHeight: 1.4 }}>{s.ecart}</span>
      </div>}
      {!s.levee && <div style={{ fontSize: 11.5, color: W.txt3, marginTop: 9, lineHeight: 1.5 }}>Durée inconnue pour cette culture : aucune projection n’est calculée.</div>}
    </div>);
}

function BlocTitre({ children, sub }) {
  const W = useW();
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: W.txt3, textTransform: 'uppercase', letterSpacing: '.06em' }}>{children}</div>
      {sub && <div style={{ fontSize: 12, color: W.txt3, marginTop: 3, lineHeight: 1.45 }}>{sub}</div>}
    </div>);
}

// Corps de la fiche : 1) semer ou planter, 2) déjà en terre, 3) frise. La frise
// est en pied : la fiche sert d'abord à décider, la frise confirme.
function CorpsFiche({ d }) {
  const W = useW();
  // Pré-positionné sur l'action la mieux notée.
  const [act, setAct] = useState(() => d.actions.reduce((b, x) => x.score > (b ? b.score : -1) ? x : b, null)?.k);
  const a = d.actions.find((x) => x.k === act) || d.actions[0];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <section>
        <BlocTitre>Semer ou planter</BlocTitre>
        {d.sansCalendrier ?
        <div style={{ background: W.cardAlt, borderRadius: 14, padding: '14px 15px' }}>
          <div style={{ fontSize: 13, color: W.txt, lineHeight: 1.55 }}>Aucun calendrier pour {d.culture.toLowerCase()} dans la zone {d.zone} : la confiance ne peut pas être évaluée.</div>
          <a href="#calendrier" style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginTop: 9, fontSize: 12.5, fontWeight: 600, color: W.brandText }}>Compléter la fenêtre dans le calendrier<Ico n="chevR" c={W.brandText} s={14} w={2} /></a>
        </div> : <>
          <SelecteurAction actions={d.actions} value={act} onChange={setAct} />
          <div style={{ fontSize: 12.5, color: W.txt2, marginBottom: 10, lineHeight: 1.5 }}>
            Fenêtre conseillée en zone {d.zone} : <strong style={{ color: W.txt, fontWeight: 700 }}>{a.fenetre}</strong>
          </div>
          <BlocConfiance score={a.score} regles={a.regles} />
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, marginTop: 12 }}>
            <Ico n="basket" c={W.amber} s={17} />
            <div style={{ flex: 1, minWidth: 0, fontSize: 13, color: W.txt, lineHeight: 1.5 }}>
              Récolte attendue <strong style={{ fontWeight: 700 }}>{a.recolte}</strong> si le geste est fait le {d.dateRef}.
              {a.recolteNote && <div style={{ fontSize: 11.5, color: W.txt3, marginTop: 3 }}>{a.recolteNote}</div>}
            </div>
          </div>
          {d.nonLocalise && <div style={{ marginTop: 12 }}>
            <InfoBanner tint="blue" icon="pin" title="Potager non localisé" body="Sans localisation, la météo n’est pas lue : deux règles restent indéterminées et la troisième étoile est inaccessible." action={<Btn small icon="pin">Localiser</Btn>} />
          </div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
            <Btn kind="primary" icon={a.k === 'plantation' ? 'leaf' : 'sprout'}>{a.cta}</Btn>
          </div>
        </>}
      </section>

      {d.series.length > 0 &&
      <section>
        <BlocTitre sub="La plus ancienne en tête.">Déjà en terre · {d.series.length}</BlocTitre>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          {d.series.map((s, i) => <CarteSerie key={i} s={s} />)}
        </div>
      </section>}

      <section>
        <BlocTitre>{d.friseTitre}</BlocTitre>
        <MonthStrip semis={d.frise.semis} plant={d.frise.plant} rec={d.frise.rec} moisCourant={d.moisRef} legend />
      </section>
    </div>);
}

// Coquille : panneau latéral sur desktop, modale centrée en tablette, feuille
// plein écran sous 480 px. Même chrome que la modale des récoltes (US-073).
function FicheShell({ mode, d, onClose }) {
  const W = useW();
  const sheet = mode === 'sheet', side = mode === 'side';
  const box = sheet ?
    { position: 'absolute', inset: 0, borderRadius: 0, width: 'auto' } :
    side ?
    { position: 'absolute', top: 0, right: 0, bottom: 0, width: 460, borderRadius: 0, borderLeft: `1px solid ${W.border}` } :
    { position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: 'min(560px, calc(100% - 40px))', maxHeight: 'calc(100% - 48px)', borderRadius: 18 };
  return (
    <>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(12,18,6,.45)', zIndex: 60 }} />
      <div style={{ zIndex: 61, background: W.card, boxShadow: W.shadow, display: 'flex', flexDirection: 'column', overflow: 'hidden', ...box }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11, padding: '15px 17px', borderBottom: `1px solid ${W.border}`, flexShrink: 0 }}>
          <div style={{ width: 36, height: 36, borderRadius: 11, background: W.brandSoft, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Ico n="cal" c={W.brand} s={18} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: wserif, fontSize: 19, fontWeight: 600, color: W.txt, letterSpacing: '-.015em' }}>{d.culture}</div>
            <div style={{ fontSize: 12, color: W.txt3, marginTop: 2 }}>{d.variete || 'variété non précisée'} · zone {d.zone} · au {d.dateRef}</div>
          </div>
          <button onClick={onClose} aria-label="Fermer" style={{ display: 'flex', padding: 6, borderRadius: 9, border: 'none', background: W.cardAlt, cursor: 'pointer', flexShrink: 0 }}><Ico n="close" c={W.txt2} s={16} /></button>
        </div>
        <div className="s" style={{ padding: 17, overflowY: 'auto', minHeight: 0, flex: 1 }}><CorpsFiche d={d} /></div>
        <div style={{ padding: '12px 17px', borderTop: `1px solid ${W.border}`, background: W.cardAlt, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexShrink: 0 }}>
          <span style={{ fontSize: 11.5, color: W.txt3, lineHeight: 1.4 }}>Projections indicatives, recalculées à chaque ouverture.</span>
          <Btn onClick={onClose}>Fermer</Btn>
        </div>
      </div>
    </>);
}

// US-180 / CA11 — tuile de culture de l'écran Plan connecté : la confiance de la
// semaine s'ajoute à la ligne « famille · durée », sans toucher aux deux appuis
// existants (tuile, icône d'observations). La frise et la pastille ouvrent la fiche.
function TuilePlan({ c, onOuvrir, onPourquoi }) {
  const W = useW();
  const n = c.score == null ? null : etoilesDe(c.score);
  return (
    <div style={{ background: W.cardAlt, borderRadius: 13, padding: 13 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 3 }}>
        <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 5, background: c.organe === 'végétatif' ? W.brand : W.amber, flexShrink: 0 }} />
        <span style={{ fontFamily: wserif, fontSize: 15.5, fontWeight: 600, color: W.txt, textTransform: 'capitalize' }}>{c.culture}</span>
        {c.variete && <span style={{ fontFamily: wserif, fontStyle: 'italic', fontSize: 12.5, color: W.txt3, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.variete}</span>}
        <span style={{ marginLeft: 'auto', fontSize: 15, fontWeight: 700, color: W.brand, flexShrink: 0 }}>{c.nb}<span style={{ fontSize: 11, fontWeight: 600, color: W.txt3 }}> {c.unite}</span></span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11.5, color: W.txt3 }}>{c.famille || '—'} · {c.duree || '—'}</span>
        {n ?
        <button onClick={onPourquoi} title="Pourquoi ce niveau de confiance ?" style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, background: W.card, border: `1px solid ${W.border}`, borderRadius: 20, padding: '3px 9px', cursor: 'pointer', fontFamily: 'inherit', flexShrink: 0 }}>
          <Etoiles n={n} size={11} />
          <span style={{ fontSize: 11, fontWeight: 600, color: W.txt2 }}>{c.confLabel}</span>
        </button> :
        <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 600, color: W.txt3, flexShrink: 0 }}>— pas de calendrier</span>}
      </div>
      <button onClick={onOuvrir} title="Ouvrir la fiche calendrier" style={{ display: 'block', width: '100%', background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left' }}>
        <MonthStrip semis={c.frise.semis} plant={c.frise.plant} rec={c.frise.rec} moisCourant={c.moisRef} />
      </button>
    </div>);
}

Object.assign(window, { Etoiles, BlocConfiance, LigneRegle, CarteSerie, SelecteurAction, CorpsFiche, FicheShell, TuilePlan, etoilesDe, CONF_LBL });
