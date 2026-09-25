const { useState, useRef, useEffect } = React;

function Tip({ text, children }) {
  return <span className="wtip">{children || <span className="wtip-q">?</span>}<span className="wtip-b">{text}</span></span>;
}

function Card({ children, pad = 16, style }) {
  const W = useW();
  return <div style={{ background: W.card, border: `1px solid ${W.border}`, borderRadius: 14, boxShadow: W.shadow, padding: pad, ...style }}>{children}</div>;
}

function CardHead({ icon, tint = 'brand', title, sub, right, tip }) {
  const W = useW();
  const c = W[tint],soft = W[tint + 'Soft'];
  return (
    <div className="wcardhead" style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
      {icon && <div style={{ width: 40, height: 40, borderRadius: 11, background: soft, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Ico n={icon} c={c} s={20} /></div>}
      <div style={{ flex: '1 1 150px', minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: wserif, fontWeight: 600, fontSize: 17, color: W.txt, letterSpacing: '-.01em' }}>{title}</span>
          {tip && <Tip text={tip} />}
        </div>
        {sub && <div style={{ fontSize: 12.5, color: W.txt3, marginTop: 1 }}>{sub}</div>}
      </div>
      {right}
    </div>);
}

function Btn({ children, icon, kind = 'ghost', onClick, small, title }) {
  const W = useW();
  const iconOnly = icon && !children;
  const base = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: iconOnly ? 0 : 7, borderRadius: 10, cursor: 'pointer', fontFamily: 'inherit', fontSize: small ? 12.5 : 13.5, fontWeight: 600, padding: iconOnly ? small ? '7px' : '9px' : small ? '7px 11px' : '9px 15px', transition: 'all .18s', whiteSpace: 'nowrap' };
  const kinds = {
    primary: { background: W.brand, color: W.mode === 'dark' ? '#0F1409' : '#fff', border: `1px solid ${W.brand}` },
    ghost: { background: W.card, color: W.txt2, border: `1px solid ${W.border}` },
    soft: { background: W.brandSoft, color: W.brandText, border: `1px solid transparent` },
    quiet: { background: 'transparent', color: W.txt3, border: '1px solid transparent' }
  };
  return <button title={title} aria-label={iconOnly ? title : undefined} onClick={onClick} style={{ ...base, ...kinds[kind] }}>{icon && <Ico n={icon} s={small ? 14 : 16} w={2} />}{children}</button>;
}

function Badge({ children, tint = 'brand', solid }) {
  const W = useW();
  const c = W[tint],soft = W[tint + 'Soft'];
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, fontWeight: 600, padding: '3px 9px', borderRadius: 20, background: solid ? c : soft, color: solid ? W.mode === 'dark' ? '#0F1409' : '#fff' : c, whiteSpace: 'nowrap' }}>{children}</span>;
}

function Stat({ icon, tint = 'brand', value, unit, label, tip }) {
  const W = useW();
  const c = W[tint];
  return (
    <div style={{ background: W.card, border: `1px solid ${W.border}`, borderRadius: 14, boxShadow: W.shadow, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 13, minWidth: 0 }}>
      <div style={{ width: 44, height: 44, borderRadius: 12, background: W[tint + 'Soft'], display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Ico n={icon} c={c} s={21} /></div>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
          <span style={{ fontSize: 25, fontWeight: 700, color: W.txt, letterSpacing: '-.03em', lineHeight: 1.1 }}>{value}</span>
          {unit && <span style={{ fontSize: 13, fontWeight: 600, color: W.txt3 }}>{unit}</span>}
        </div>
        <div style={{ fontSize: 12.5, color: W.txt2, marginTop: 2, display: 'flex', alignItems: 'center', gap: 5 }}>{label}{tip && <Tip text={tip} />}</div>
      </div>
    </div>);
}

function ProgressBar({ pct, tint }) {
  const W = useW();
  const c = tint || (pct >= 80 ? W.red : pct >= 55 ? W.amber : W.brand);
  return <div style={{ height: 6, background: W.cardAlt, borderRadius: 4, overflow: 'hidden' }}><div style={{ height: '100%', width: `${Math.min(100, pct)}%`, background: c, borderRadius: 4 }} /></div>;
}

const CUR_MONTH = 7;
// `moisCourant` : mois mis en évidence quand l'écran hôte raisonne sur une date de
// référence (prop existante côté code, `MonthStrip.jsx`). Absent, le comportement ne change pas.
function MonthStrip({ semis = [], plant = [], rec = [], legend, moisCourant }) {
  const W = useW();
  const cur = moisCourant == null ? CUR_MONTH : moisCourant;
  const cellFor = (i) => {
    if (rec.includes(i)) return W.amber;
    if (plant.includes(i)) return W.brand;
    if (semis.includes(i)) return W.blue;
    return null;
  };
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12,1fr)', gap: 2.5 }}>
        {M_INI.map((_, i) => {const c = cellFor(i);return (
            <div key={i} style={{ height: 9, borderRadius: 3, background: c || W.cardAlt, outline: i === cur ? `1.5px solid ${W.txt}` : 'none', outlineOffset: 1.5 }} />);})}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12,1fr)', gap: 2.5, marginTop: 4 }}>
        {M_INI.map((m, i) => <div key={i} style={{ textAlign: 'center', fontSize: 9, fontWeight: i === cur ? 700 : 500, color: i === cur ? W.txt : W.txt3 }}>{m}</div>)}
      </div>
      {legend && <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
        {[['blue', 'Semis'], ['brand', 'Plantation'], ['amber', 'Récolte']].map(([k, l]) =>
        <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: W.txt2 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: W[k] }} />{l}</span>)}
      </div>}
    </div>);
}

function InfoBanner({ title, body, action, onClose, tint = 'brand', icon = 'help' }) {
  const W = useW();
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 13, background: W[tint + 'Soft'], border: `1px solid ${W.mode === 'dark' ? W.border : 'transparent'}`, borderRadius: 14, padding: '14px 16px', flexWrap: 'wrap' }}>
      <div style={{ width: 32, height: 32, borderRadius: 9, background: W.card, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Ico n={icon} c={W[tint]} s={17} /></div>
      <div style={{ flex: '1 1 190px', minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: W.mode === 'dark' ? W.txt : W[tint] }}>{title}</div>
        <div style={{ fontSize: 13, color: W.mode === 'dark' ? W.txt2 : W[tint], opacity: W.mode === 'dark' ? 1 : .88, marginTop: 3, lineHeight: 1.5 }}>{body}</div>
      </div>
      {action && <span className="wbanner-act" style={{ order: 4 }}>{action}</span>}
      <button onClick={() => {setOpen(false);onClose && onClose();}} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, display: 'flex', flexShrink: 0, order: 3 }}><Ico n="close" c={W[tint]} s={16} /></button>
    </div>);
}

function SearchField({ placeholder = 'Rechercher…', value, onChange, wide }) {
  const W = useW();
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: W.card, border: `1px solid ${W.border}`, borderRadius: 10, padding: '0 12px', height: 38, flex: wide ? 1 : 'none', minWidth: 0 }} data-comment-anchor="ca8fa88af8-div-117-5">
      <Ico n="search" c={W.txt3} s={15} />
      <input value={value} onChange={(e) => onChange && onChange(e.target.value)} placeholder={placeholder} style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', fontFamily: 'inherit', fontSize: 13.5, color: W.txt }} />
    </div>);
}

function Select({ value, options, onChange, icon, plain }) {
  const W = useW();
  if (plain) return (
    <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 7, background: W.card, color: W.txt2, border: `1px solid ${W.border}`, borderRadius: 10, padding: '9px 15px', fontSize: 13.5, fontWeight: 600 }}>
      {icon && <Ico n={icon} c={W.txt3} s={16} w={2} />}
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{ appearance: 'none', border: 'none', outline: 'none', background: 'transparent', fontFamily: 'inherit', fontSize: 13.5, fontWeight: 600, color: W.txt2, cursor: 'pointer' }}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>);
  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', background: W.card, border: `1px solid ${W.border}`, borderRadius: 10, height: 38, padding: '0 10px 0 12px', gap: 8 }}>
      {icon && <Ico n={icon} c={W.txt3} s={15} />}
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{ appearance: 'none', border: 'none', outline: 'none', background: 'transparent', fontFamily: 'inherit', fontSize: 13.5, color: W.txt, cursor: 'pointer', paddingRight: 4 }}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
      <Ico n="chevD" c={W.txt3} s={14} />
    </div>);
}

function IconSelect({ value, options, onChange, icons = {}, tints = {} }) {
  const W = useW();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    function onDoc(e) {if (ref.current && !ref.current.contains(e.target)) setOpen(false);}
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);
  const badge = (o, s) => {
    const ic = icons[o];
    if (!ic) return <span style={{ width: s, flexShrink: 0 }} />;
    const tint = tints[o];
    const bg = tint ? tint === 'txt3' ? W.cardAlt : W[tint + 'Soft'] : W.cardAlt;
    const c = tint ? W[tint] : W.txt3;
    return <span style={{ width: s, height: s, borderRadius: s * 0.35, background: bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Ico n={ic} c={c} s={s * 0.6} /></span>;
  };
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen((o) => !o)} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, background: W.card, color: W.txt2, border: `1px solid ${W.border}`, borderRadius: 10, padding: '9px 15px', fontFamily: 'inherit', fontSize: 13.5, fontWeight: 600, cursor: 'pointer' }}>
        <Ico n={icons[value] || 'filter'} c={W.txt3} s={16} w={2} />
        <span>{value}</span>
      </button>
      {open && <div style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, minWidth: 210, background: W.card, border: `1px solid ${W.border}`, borderRadius: 12, boxShadow: W.shadow, padding: 5, zIndex: 30, display: 'flex', flexDirection: 'column', gap: 1 }}>
        {options.map((o) =>
        <button key={o} onClick={() => {onChange(o);setOpen(false);}} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 8px', borderRadius: 8, border: 'none', background: o === value ? W.brandSoft : 'transparent', cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, color: o === value ? W.brandText : W.txt, textAlign: 'left', width: '100%' }}>
            {badge(o, 24)}{o}
          </button>)}
      </div>}
    </div>);
}

function TileNav({ items, active, onPick }) {
  const W = useW();
  return (
    <div className="wtiles">
      {items.map((it) => {
        const on = it.id === active;
        return (
          <button key={it.id} onClick={() => onPick(it.id)} title={it.help} style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, width: 84, height: 72, borderRadius: 13, cursor: 'pointer', fontFamily: 'inherit', flexShrink: 0, background: on ? W.brandSoft : W.card, border: `1px solid ${on ? W.brand : W.border}`, color: on ? W.brandText : W.txt2, transition: 'all .18s' }}>
            <Ico n={it.icon} c={on ? W.brand : W.txt3} s={20} />
            <span style={{ fontSize: 11.5, fontWeight: on ? 700 : 500, textAlign: 'center', lineHeight: 1.15 }}>{it.label}</span>
            {it.badge > 0 && <span style={{ position: 'absolute', top: -6, right: -6, minWidth: 19, height: 19, borderRadius: 10, background: W.brand, color: W.mode === 'dark' ? '#0F1409' : '#fff', fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 5px' }}>{it.badge}</span>}
          </button>);
      })}
    </div>);
}

function SectionLabel({ children, right }) {
  const W = useW();
  return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 10 }}>
    <span style={{ fontSize: 11.5, fontWeight: 700, color: W.txt3, textTransform: 'uppercase', letterSpacing: '.06em' }}>{children}</span>{right}</div>;
}

function SummaryBar({ items }) {
  const W = useW();
  return (
    <Card pad={14}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap', rowGap: 8 }}>
        {items.map((it, i) =>
        <div key={it.label} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '0 16px', borderLeft: i > 0 ? `1px solid ${W.border}` : 'none' }}>
          <Ico n={it.icon} c={W[it.tint || 'brand']} s={16} />
          <span style={{ fontSize: 13, color: W.txt2, whiteSpace: 'nowrap' }}>
            <strong style={{ color: W.txt, fontWeight: 700 }}>{it.value}</strong> {it.label}
          </span>
          {it.tip && <Tip text={it.tip} />}
        </div>)}
      </div>
    </Card>);
}

function GroupHead({ label, count, right, open, onToggle }) {
  const W = useW();
  return (
    <button onClick={onToggle} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, paddingBottom: 9, marginBottom: open ? 12 : 0, background: 'none', borderWidth: '0 0 1px', borderStyle: 'none none solid', borderColor: `transparent transparent ${W.border}`, cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left' }}>
      <span style={{ display: 'flex', transform: open ? 'none' : 'rotate(-90deg)', transition: 'transform .18s' }}><Ico n="chevD" c={W.txt3} s={15} w={2.2} /></span>
      <Ico n="leaf" c={W.brand} s={18} />
      <span style={{ fontFamily: wserif, fontSize: 19, fontWeight: 600, color: W.txt, letterSpacing: '-.015em' }}>{label}</span>
      <span style={{ fontSize: 13, color: W.txt3 }}>({count})</span>
      {right && <span style={{ marginLeft: 'auto', fontSize: 12.5, color: W.txt3 }}>{right}</span>}
    </button>);
}

function useGroups(keys) {
  const [closed, setClosed] = useState({});
  return [(k) => !closed[k], (k) => setClosed((c) => ({ ...c, [k]: !c[k] }))];
}

Object.assign(window, { Tip, Card, CardHead, Btn, Badge, Stat, ProgressBar, MonthStrip, InfoBanner, SearchField, Select, IconSelect, TileNav, SectionLabel, SummaryBar, GroupHead, useGroups, CUR_MONTH });
