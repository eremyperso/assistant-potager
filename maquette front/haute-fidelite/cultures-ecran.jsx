// ÉPIC 11 — US-205 : écran Cultures. Tokens et composants de la maquette figée,
// pastille de phase reprise de la maquette gelée « Plan – rangs et places ».
const { useState } = React;

const Svg = ({ c, s = 13, w = 2.2, children }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, display: 'block' }}>{children}</svg>);
const PH_ICO = {
  place: <><path d="M3 20.5h18M12 20.5V11" /><path d="M12 14c0-4 2.6-6.6 6.6-6.6 0 4-2.6 6.6-6.6 6.6z" /><path d="M12 11c0-3.4-2.2-5.6-5.6-5.6 0 3.4 2.2 5.6 5.6 5.6z" /></>,
  recolte: <><path d="M3 10h18l-1.7 9.2a2 2 0 0 1-2 1.6H6.7a2 2 0 0 1-2-1.6z" /><path d="M8 10l3-6.5M16 10l-3-6.5M9 14.5v2.5M15 14.5v2.5" /></>,
  semee: <><path d="M3 20.5h18" /><ellipse cx="7" cy="15.5" rx="2" ry="2.8" transform="rotate(-30 7 15.5)" /><ellipse cx="16.5" cy="15.5" rx="2" ry="2.8" transform="rotate(30 16.5 15.5)" /><path d="M12 4v6M9.5 7.5 12 10l2.5-2.5" /></>,
  pep: <><path d="M7.4 12.6h9.2l-1 7a1.6 1.6 0 0 1-1.6 1.4h-3.8a1.6 1.6 0 0 1-1.6-1.4z" /><path d="M6.8 12.6h10.4M12 12.6V9.3" /><path d="M12 9.3c0-2 1.5-3.4 3.4-3.4 0 2-1.5 3.4-3.4 3.4z" /></> };

// PastillePhase (US-194) — couleur = phase, et toujours le mot (RT4).
function PastillePhase({ ph, small }) {
  const W = useW();
  const d = { place:['En place', W.brandSoft, W.brandText], recolte:['En récolte', W.amberSoft, W.mode === 'dark' ? W.amber : '#8A5A08'], semee:['Semée', W.violetSoft, W.violet], pep:['En pépinière', W.cardAlt, W.txt2] }[ph];
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: small ? 11.5 : 12, fontWeight: 600, borderRadius: 999, padding: small ? '2px 8px' : '3px 10px', background: d[1], color: d[2], whiteSpace: 'nowrap', border: ph === 'pep' ? `1px solid ${W.border}` : '1px solid transparent' }}>
      <Svg c={d[2]}>{PH_ICO[ph]}</Svg>{d[0]}</span>);
}

function PasAuPotager({ sugg }) {
  const W = useW();
  return <span style={{ display: 'inline-flex', alignItems: 'center', fontSize: 12, fontWeight: 600, borderRadius: 999, padding: '3px 10px', border: `1px dashed ${sugg ? W.brand : W.txt3}`, color: sugg ? W.brandText : W.txt2, whiteSpace: 'nowrap' }}>{sugg ? 'suggestion — pas au potager' : 'pas au potager'}</span>;
}

function ConfCourte({ n }) {
  const W = useW();
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexShrink: 0 }}><Etoiles n={n} size={12} /><span style={{ fontSize: 11.5, fontWeight: 600, color: W.txt2 }}>{CONF_MOT[n]}</span></span>;
}

function Presence({ c }) {
  const W = useW();
  const t = { fontSize: 12, color: W.txt2, whiteSpace: 'nowrap' };
  if (c.ph) return <span style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', minWidth: 0 }}><PastillePhase ph={c.ph} /><span style={t}>· {plur(c.parc, 'parcelle')}{c.lots ? ` · ${plur(c.lots, 'lot')}` : ''}</span></span>;
  if (c.lots) return <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><PastillePhase ph="pep" /><span style={t}>· {plur(c.lots, 'lot')}</span></span>;
  return null;
}

// Carte d'une culture (US-205 / CA5 à CA8). Aucune quantité : c'est le rôle de Stocks.
function CarteCulture({ c, sugg, confKO, onOpen }) {
  const W = useW();
  const [aide, setAide] = useState(false);
  const fl = fenLabel(c);
  const n = confKO ? null : c.stars;
  const sub = c.horsRef ? 'hors référentiel' : c.present ? `${plur(c.vars.length, 'variété')} · ${c.fam}` : c.fam;
  const aria = [c.n, c.ph ? { place:'en place', recolte:'en récolte', semee:'semée' }[c.ph] : c.lots ? 'en pépinière' : 'pas au potager', sugg ? 'suggestion de la semaine' : '', c.horsRef ? 'hors référentiel' : !c.cal ? 'pas de calendrier' : n ? `confiance ${CONF_MOT[n]}, ${n} étoiles sur 3` : 'confiance indisponible', fl ? fl.t : ''].filter(Boolean).join(', ');
  return (
    <div role="button" tabIndex={0} aria-label={aria} className="cu-card" onClick={onOpen} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(); } }}
      style={{ background: sugg ? 'transparent' : W.card, border: `1px ${sugg ? 'dashed' : 'solid'} ${sugg ? W.brand : W.border}`, borderRadius: 14, boxShadow: sugg ? 'none' : W.shadow, padding: '14px 15px 12px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 11, minWidth: 0, textAlign: 'left' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: wserif, fontSize: 16.5, fontWeight: 600, color: W.txt, lineHeight: 1.2 }}>{c.n}</div>
          <div style={{ fontSize: 12, color: c.horsRef ? W.txt2 : W.txt3, marginTop: 2, fontStyle: c.horsRef ? 'normal' : 'italic', fontFamily: c.horsRef ? 'inherit' : wserif }}>{sub}</div>
        </div>
        {c.horsRef ? null : !c.cal ? <span style={{ fontSize: 11.5, fontWeight: 600, color: W.txt3, border: `1px dashed ${W.border}`, borderRadius: 6, padding: '2px 7px', whiteSpace: 'nowrap' }}>pas de calendrier</span> :
          n ? <ConfCourte n={n} /> : <span style={{ fontSize: 13, color: W.txt3 }} aria-hidden="true">—</span>}
      </div>
      {c.horsRef ?
        <div style={{ fontSize: 12, color: W.txt3, background: W.cardAlt, borderRadius: 8, padding: '8px 10px', lineHeight: 1.45 }}>Inconnue du référentiel : ni calendrier ni confiance.</div> :
        <div style={{ opacity: c.cal ? 1 : .55 }}><MonthStrip {...c.frise} moisCourant={MOIS_REF} /></div>}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px 10px', flexWrap: 'wrap', marginTop: 'auto' }}>
        {c.present ? <Presence c={c} /> : <PasAuPotager sugg={sugg} />}
        {fl ? <span style={{ fontSize: 12, color: fl.b ? W.txt : W.txt2, fontWeight: fl.b ? 700 : 400 }}>{fl.t}</span> :
          !c.cal && !c.horsRef ? <button onClick={(e) => { e.stopPropagation(); setAide((a) => !a); }} aria-expanded={aide} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 600, color: W.brandText, textDecoration: 'underline', textUnderlineOffset: 3 }}>compléter</button> : null}
      </div>
      {aide && <div onClick={(e) => e.stopPropagation()} style={{ fontSize: 12, color: W.txt2, background: W.cardAlt, borderRadius: 9, padding: '9px 11px', lineHeight: 1.5, cursor: 'default' }}>
        Aucune fenêtre n’est connue pour {c.n.toLowerCase()} en zone {ZONE}. Dis au compagnon : <code style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5, color: W.txt, background: W.card, borderRadius: 4, padding: '1px 5px' }}>/calendrier fenetre {norm(c.n)} …</code></div>}
    </div>);
}

function CarteSquelette() {
  const W = useW();
  const b = (w, h, mt = 0) => <div style={{ width: w, height: h, borderRadius: 5, background: W.cardAlt, marginTop: mt }} />;
  return <div aria-hidden="true" style={{ background: W.card, border: `1px solid ${W.border}`, borderRadius: 14, padding: 15 }}>{b('45%', 15)}{b('30%', 10, 7)}{b('100%', 9, 16)}{b('100%', 7, 5)}<div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>{b('38%', 20)}{b('32%', 12)}</div></div>;
}

function Onglets({ tab, setTab, nP, nT, full }) {
  const W = useW();
  return (
    <div role="tablist" aria-label="Périmètre" style={{ display: 'flex', gap: 4, background: W.cardAlt, borderRadius: 11, padding: 4, flexShrink: 0, flex: full ? 1 : 'none' }}>
      {[['potager', `Au potager · ${nP}`], ['toutes', `Toutes · ${nT}`]].map(([k, l]) => { const on = tab === k; return (
        <button key={k} role="tab" aria-selected={on} onClick={() => setTab(k)} style={{ padding: '8px 13px', borderRadius: 8, border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, fontWeight: on ? 700 : 500, background: on ? W.card : 'transparent', color: on ? W.txt : W.txt2, boxShadow: on ? W.shadow : 'none', whiteSpace: 'nowrap', minHeight: 36, flex: full ? 1 : 'none' }}>{l}</button>); })}
    </div>);
}

function Puce({ on, children, onClick }) {
  const W = useW();
  return <button aria-pressed={on} onClick={onClick} style={{ padding: '6px 12px', borderRadius: 999, border: `1px solid ${on ? W.brand : W.border}`, background: on ? W.brandSoft : W.card, color: on ? W.brandText : W.txt2, fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap', minHeight: 32 }}>{children}</button>;
}

const TRIS = ['Confiance ↓', 'A → Z', 'Par famille'];
const MOIS_OPT = ['Tous les mois', ...M_FULL.map((m) => capz(m))];

function EcranCultures({ mode, etat, onOpen }) {
  const W = useW();
  const [tab, setTab] = useState('potager');
  const [q, setQ] = useState('');
  const [tri, setTri] = useState(TRIS[0]);
  const [fam, setFam] = useState(null);
  const [mois, setMois] = useState(MOIS_OPT[0]);
  const confKO = etat === 'conf', vide = etat === 'vide';
  const presents = vide ? [] : CULTURES.filter((c) => c.present);
  const sugg = confKO ? [] : suggestionsDe(vide ? CULTURES.map((c) => ({ ...c, present: false })) : CULTURES).map((s) => CULTURES.find((c) => c.id === s.id));
  const base = tab === 'potager' ? [...presents, ...sugg] : CULTURES;
  const nq = norm(q.trim());
  const matchQ = (c) => !nq || norm(c.n).includes(nq) || (tab === 'potager' && c.vars.some((v) => norm(v).includes(nq)));
  const mi = MOIS_OPT.indexOf(mois) - 1;
  const liste = base.filter(matchQ).filter((c) => !fam || c.fam === fam).filter((c) => mi < 0 || moisActifs(c).includes(mi));
  const autres = tab === 'potager' && nq ? CULTURES.filter((c) => !base.includes(c) && norm(c.n).includes(nq)).length : 0;
  const st = (c) => confKO ? 0 : c.stars || 0;
  const byConf = (a, b) => (st(b) - st(a)) || (FEN_ORD[a.fen] - FEN_ORD[b.fen]) || a.n.localeCompare(b.n, 'fr');
  const byNom = (a, b) => a.n.localeCompare(b.n, 'fr');
  const tries = [...liste].sort(tri === 'Confiance ↓' ? byConf : byNom);
  const familles = [...new Set(base.map((c) => c.fam).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr'));
  const narrow = mode === 'sheet';
  const carte = (c) => <CarteCulture key={c.id} c={c} sugg={tab === 'potager' && sugg.includes(c)} confKO={confKO} onOpen={() => onOpen(c.id)} />;
  const grille = (items) => <div className="cu-grid-wrap"><div className="cu-grid">{items}</div></div>;

  const [panneau, setPanneau] = useState(null);
  const nActifs = (fam ? 1 : 0) + (mi >= 0 ? 1 : 0) + (tri !== TRIS[0] ? 1 : 0);
  const pBtn = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6, height: 44, padding: '0 12px', borderRadius: 10, border: `1px solid ${W.border}`, fontFamily: 'inherit', fontSize: 13, fontWeight: 600, cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap' };
  const puces = (wrap) => (
    <div role="group" aria-label="Filtrer par famille" style={{ display: 'flex', gap: 6, flexWrap: wrap }}>
      <Puce on={!fam} onClick={() => setFam(null)}>Toutes familles</Puce>
      {familles.map((f) => <Puce key={f} on={fam === f} onClick={() => setFam(fam === f ? null : f)}>{f}</Puce>)}
    </div>);
  const sep = <span style={{ width: 1, height: 16, background: W.border }} />;
  const dateBtn = <button type="button" title="Date de référence" style={{ display: 'flex', alignItems: 'center', gap: 7, fontFamily: 'inherit', fontSize: 13, fontWeight: 600, color: W.txt2, background: W.card, border: `1px solid ${W.border}`, borderRadius: 10, padding: narrow ? '0 10px' : '0 13px', cursor: 'pointer', height: narrow ? 44 : 38, flexShrink: 0 }}><Ico n="cal" c={W.txt3} s={15} /><span style={{ whiteSpace: 'nowrap' }}>{narrow ? `${DATE_REF_C.replace(' 2026', '')}` : `au ${DATE_REF_C}`}</span></button>;
  const legende = (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 18px', background: W.card, border: `1px solid ${W.border}`, borderRadius: 12, padding: '10px 16px', fontSize: 12.5, color: W.txt2 }}>
      {[['blue', 'Semis'], ['brand', 'Plantation'], ['amber', 'Récolte']].map(([k, l]) => <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: W[k] }} /><span>{l}</span></span>)}
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, outline: `1.5px solid ${W.txt}`, outlineOffset: 1 }} /><span>{capz(M_FULL[MOIS_REF])}</span></span>
      {!narrow && sep}
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Etoiles n={3} size={11} /><span>confiance du meilleur geste ce jour</span></span>
      {!narrow && sep}
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Ico n="pin" c={W.txt3} s={14} /><span>{`Zone ${ZONE}, déduite de la ville du potager`}</span></span>
      <span style={{ color: W.txt3 }}>Calendriers : Wind River Greens · CC BY 4.0</span>
    </div>);
  let corps;
  if (etat === 'chargement') corps = grille(Array.from({ length: 6 }, (_, i) => <CarteSquelette key={i} />));
  else if (etat === 'echec') corps = (
    <Card><div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <Ico n="alert" c={W.red} s={20} /><div style={{ flex: '1 1 200px', fontSize: 13.5, color: W.txt, lineHeight: 1.5 }}>Les cultures n’ont pas pu être lues. Rien n’a été modifié.</div><Btn icon="swap">Réessayer</Btn></div></Card>);
  else if (vide && tab === 'potager') corps = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card><div style={{ fontFamily: wserif, fontSize: 16, fontWeight: 600, color: W.txt }}>Rien au potager en ce moment</div>
        <div style={{ fontSize: 13, color: W.txt2, marginTop: 4, lineHeight: 1.5 }}>Aucune culture n’est en place ni en pépinière au {DATE_REF}. Voici ce dont la fenêtre est ouverte dans ta zone.</div>
        <button onClick={() => setTab('toutes')} style={{ marginTop: 10, background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, fontWeight: 600, color: W.brandText, display: 'inline-flex', alignItems: 'center', gap: 4 }}>Voir les {CULTURES.length} cultures du référentiel<Ico n="chevR" c={W.brandText} s={14} w={2} /></button></Card>
      {grille(sugg.map(carte))}</div>);
  else if (!tries.length) corps = <div style={{ fontSize: 13, color: W.txt2, padding: '18px 4px' }}>Aucune culture ne correspond{autres ? '' : ' à ces filtres'}.</div>;
  else if (tri === 'Par famille') corps = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {[...new Set(tries.map((c) => c.fam || 'Hors référentiel'))].map((f) => (
        <div key={f}><div style={{ fontSize: 11, fontWeight: 700, color: W.txt3, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>{f} · {tries.filter((c) => (c.fam || 'Hors référentiel') === f).length}</div>
          {grille(tries.filter((c) => (c.fam || 'Hors référentiel') === f).map(carte))}</div>))}
    </div>);
  else corps = grille(tries.map(carte));

  return (
    <div className="s" style={{ height: '100%', overflowY: 'auto', background: W.bg }}>
      <div style={{ padding: narrow ? '16px 14px 40px' : '22px 24px 48px', display: 'flex', flexDirection: 'column', gap: narrow ? 10 : 14, maxWidth: 1320, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: narrow ? '10px 8px' : '10px 14px', flexWrap: 'wrap' }}>
          <span style={{ fontFamily: wserif, fontSize: narrow ? 21 : 24, fontWeight: 600, color: W.txt, letterSpacing: '-.015em', order: 0 }}>Cultures</span>
          <div style={{ order: 1, flex: narrow ? '1 1 auto' : '0 0 auto', marginLeft: narrow ? 'auto' : 0, display: 'flex' }}><Onglets tab={tab} setTab={setTab} nP={presents.length} nT={CULTURES.length} full={narrow} /></div>
        </div>

        {narrow ? <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {dateBtn}
            <div style={{ flex: 1, minWidth: 0, display: 'flex' }}><SearchField wide value={q} onChange={setQ} placeholder={tab === 'potager' ? 'Culture, variété…' : 'Rechercher…'} /></div>
            <button onClick={() => setPanneau(panneau === 'filtres' ? null : 'filtres')} aria-expanded={panneau === 'filtres'} aria-label={`Filtres${nActifs ? ', ' + nActifs + ' actifs' : ''}`} title="Filtres" style={{ ...pBtn, minWidth: 44, padding: '0 10px', background: panneau === 'filtres' || nActifs ? W.brandSoft : W.card, color: nActifs ? W.brandText : W.txt2, borderColor: nActifs ? W.brand : W.border }}><Ico n="filter" s={16} w={2} c="currentColor" />{nActifs ? <span>{nActifs}</span> : null}</button>
            <button onClick={() => setPanneau(panneau === 'legende' ? null : 'legende')} aria-expanded={panneau === 'legende'} aria-label="Légende" title="Légende" style={{ ...pBtn, width: 44, padding: 0, background: panneau === 'legende' ? W.brandSoft : W.card }}><Ico n="help" s={17} c={W.txt2} /></button>
          </div>
          {panneau === 'filtres' && <div style={{ display: 'flex', flexDirection: 'column', gap: 10, background: W.card, border: `1px solid ${W.border}`, borderRadius: 12, padding: 12 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><Select value={tri} options={TRIS} onChange={setTri} icon="filter" /><Select value={mois} options={MOIS_OPT} onChange={setMois} icon="cal" /></div>
            {puces('wrap')}
            {nActifs > 0 && <button onClick={() => { setFam(null); setMois(MOIS_OPT[0]); setTri(TRIS[0]); }} style={{ alignSelf: 'flex-start', background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, color: W.brandText }}>Tout effacer</button>}
          </div>}
          {panneau === 'legende' && legende}
        </> : <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {dateBtn}
            <div style={{ flex: '1 1 200px', maxWidth: 340, minWidth: 0, display: 'flex' }}><SearchField wide value={q} onChange={setQ} placeholder={tab === 'potager' ? 'Culture ou variété…' : 'Rechercher une culture…'} /></div>
            <Select value={tri} options={TRIS} onChange={setTri} icon="filter" />
            <div aria-label="Filtrer par mois de semis ou de plantation"><Select value={mois} options={MOIS_OPT} onChange={setMois} icon="cal" /></div>
          </div>
          {puces('wrap')}
          {legende}
        </>}

        {confKO && <InfoBanner tint="amber" icon="cloud" title="Confiance indisponible" body="La météo du potager n’a pas pu être lue : aucune étoile n’est affichée. Frises et présence au potager restent à jour." />}

        {autres > 0 && etat !== 'chargement' && etat !== 'echec' &&
          <button onClick={() => setTab('toutes')} style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 6, background: W.cardAlt, border: `1px solid ${W.border}`, borderRadius: 10, padding: '8px 12px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, fontWeight: 600, color: W.brandText, minHeight: 40 }}>{plur(autres, 'autre')} dans Toutes<Ico n="arrowR" c={W.brandText} s={15} w={2} /></button>}

        {corps}
      </div>
    </div>);
}

Object.assign(window, { EcranCultures, PastillePhase, CarteCulture, PasAuPotager, ConfCourte, Svg });
