// ÉPIC 11 — US-207 : fiche culture. Six sections dans l'ordre d'utilité ;
// « Ouvrir la fiche calendrier » empile la FicheShell d'US-183, non modifiée.
const { useState } = React;

function Titre({ children, n }) {
  const W = useW();
  return <h3 style={{ margin: '0 0 10px', fontSize: 11, fontWeight: 700, color: W.txt3, textTransform: 'uppercase', letterSpacing: '.06em' }}>{children}{n != null ? ` · ${n}` : ''}</h3>;
}
function NonLu() {
  const W = useW();
  return <div style={{ fontSize: 12.5, color: W.txt3, border: `1px dashed ${W.border}`, borderRadius: 10, padding: '10px 12px' }}>Cette section n’a pas pu être lue.</div>;
}
function Absence({ children }) {
  const W = useW();
  return <div style={{ fontSize: 12.5, color: W.txt2, background: W.cardAlt, borderRadius: 10, padding: '10px 12px', lineHeight: 1.5 }}>{children}</div>;
}
function Lien({ children, title }) {
  const W = useW();
  return <button title={title} onClick={(e) => e.preventDefault()} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, color: W.brandText, textDecoration: 'underline', textUnderlineOffset: 3, textAlign: 'left' }}>{children}</button>;
}

function SectionMaintenant({ c, confKO, onCal }) {
  const W = useW();
  const etatPot = c.ph ? `${{ place:'En place', recolte:'En récolte', semee:'Semée' }[c.ph]} sur ${plur(c.parc, 'parcelle')}${c.lots ? ` · ${plur(c.lots, 'lot')} en pépinière` : ''}` : c.lots ? `${plur(c.lots, 'lot')} en pépinière` : 'Pas au potager';
  const txt = { fontSize: 12.5, color: W.txt2, lineHeight: 1.5 };
  let tete;
  if (!c.cal) tete = <>
    <div style={{ fontSize: 14, fontWeight: 700, color: W.txt }}>Pas de calendrier pour ta zone</div>
    <div style={{ ...txt, marginTop: 4 }}>Aucune fenêtre n’est connue pour {c.n.toLowerCase()} en zone {ZONE} : la confiance ne peut pas être évaluée. Dis au compagnon <code style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11.5, color: W.txt, background: W.card, borderRadius: 4, padding: '1px 5px' }}>/calendrier fenetre {norm(c.n)} …</code></div></>;
  else if (c.fen === 'maintenant') tete = <>
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px 10px', flexWrap: 'wrap' }}>
      <span style={{ fontSize: 15, fontWeight: 700, color: W.txt }}>{capz(c.geste)} maintenant</span>
      {confKO ? <span style={{ fontSize: 12, color: W.txt3 }}>confiance illisible</span> : <ConfCourte n={c.stars} />}
    </div>
    <div style={{ ...txt, marginTop: 4 }}>Fenêtre conseillée en zone {ZONE} : <b style={{ color: W.txt }}>{c.fenMois}</b></div>
    {c.recAtt && <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 8 }}><Ico n="basket" c={W.amber} s={16} /><span style={{ fontSize: 12.5, color: W.txt, lineHeight: 1.5 }}>Récolte attendue <b>{c.recAtt}</b> si le geste est fait le {DATE_REF}.</span></div>}</>;
  else tete = <>
    <div style={{ fontSize: 15, fontWeight: 700, color: W.txt }}>Rien à semer ni planter ce mois-ci</div>
    <div style={{ ...txt, marginTop: 4 }}>{c.fen === 'bientot' ? 'La fenêtre s’ouvre le mois prochain : ' : 'Prochaine fenêtre : '}<b style={{ color: W.txt }}>{c.geste} {c.fenMois}</b></div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap', ...txt }}><span>{`Meilleur geste ce jour : ${c.geste} ·`}</span>{confKO ? <span>confiance illisible</span> : <ConfCourte n={c.stars} />}</div></>;
  return (
    <section>
      <Titre>Maintenant</Titre>
      <div style={{ background: W.cardAlt, borderRadius: 14, padding: '13px 14px' }}>
        {tete}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, paddingTop: 10, borderTop: `1px solid ${W.border}`, fontSize: 12.5, color: W.txt }}>
          <Ico n="pin" c={W.txt3} s={15} />{etatPot}</div>
        {confKO && c.cal && <div style={{ fontSize: 11.5, color: W.txt3, marginTop: 6 }}>La météo n’a pas pu être lue : aucune étoile n’est affichée.</div>}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}><Btn kind="soft" icon="cal" onClick={onCal}>Ouvrir la fiche calendrier</Btn></div>
    </section>);
}

const REF_L = [['fam', 'Famille · délai de retour'], ['expo', 'Exposition'], ['eau', 'Besoin en eau'], ['rust', 'Rusticité minimale'], ['prof', 'Profondeur de semis'], ['levee', 'Levée'], ['delai', 'Délai avant plantation'], ['plantRec', 'Plantation → 1ʳᵉ récolte'], ['organe', 'Organe récolté']];

function SectionRef({ f }) {
  const W = useW();
  return (
    <section>
      <Titre>Référentiel</Titre>
      <div className="fc-ref">
        {REF_L.map(([k, l]) => (
          <div key={k} style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11.5, color: W.txt3 }}>{l}</div>
            <div style={{ fontSize: 13, fontWeight: f.ref[k] ? 600 : 400, color: f.ref[k] ? W.txt : W.txt3, marginTop: 1 }}>{f.ref[k] || 'non renseigné'}</div>
          </div>))}
      </div>
      <div style={{ fontSize: 11.5, color: W.txt3, marginTop: 10 }}>Source : Wind River Greens · CC BY 4.0</div>
    </section>);
}

function SectionVarietes({ f }) {
  const W = useW();
  return (
    <section>
      <Titre n={f.varietes.length}>Variétés cultivées</Titre>
      {!f.varietes.length ? <Absence>Pas au potager en ce moment.</Absence> :
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {f.varietes.map((v) => (
          <div key={v.v} style={{ border: `1px solid ${W.border}`, borderRadius: 12, padding: '10px 12px' }}>
            <div style={{ fontFamily: wserif, fontStyle: 'italic', fontSize: 14, color: W.txt }}>{v.v}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 7 }}>
              {(v.parc || []).map(([p, ph], i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                  <Lien title="Ouvre l’onglet Parcelles sur cette parcelle">{p}</Lien><PastillePhase ph={ph} small /></div>))}
              {(v.lots || []).map(([n, st, ou], i) => (
                <div key={'l' + i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                  <Lien title="Ouvre la fiche du lot dans la Pépinière">lot {n} · {ou}</Lien><span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ fontSize: 11.5, color: W.txt2 }}>{st}</span><PastillePhase ph="pep" small /></span></div>))}
            </div>
          </div>))}
      </div>}
    </section>);
}

function PastilleVois({ sens, t, trad }) {
  const W = useW();
  const plus = sens === '+';
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600, borderRadius: 999, padding: '3px 10px', background: trad ? 'transparent' : plus ? W.brandSoft : W.redSoft, color: plus ? W.brandText : W.red, border: trad ? `1px dashed ${plus ? W.brand : W.red}` : '1px solid transparent' }}>{plus ? '+' : '−'} {t}</span>;
}

function SectionVoisinages({ f }) {
  const W = useW();
  const v = f.vois;
  const vide = !v || !(v.plus.length + v.moins.length + v.tradPlus.length + v.tradMoins.length);
  return (
    <section>
      <Titre>Voisinages</Titre>
      {vide ? <Absence>Aucun voisinage connu pour cette culture. Ce n’est pas une absence de conflit.</Absence> : <>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{v.plus.map((t) => <PastilleVois key={t} sens="+" t={t} />)}{v.moins.map((t) => <PastilleVois key={t} sens="−" t={t} />)}</div>
        {(v.tradPlus.length + v.tradMoins.length) > 0 && <>
          <div style={{ fontSize: 11.5, color: W.txt3, margin: '10px 0 6px' }}>Selon la pratique traditionnelle, sans preuve établie</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{v.tradPlus.map((t) => <PastilleVois key={t} sens="+" t={t} trad />)}{v.tradMoins.map((t) => <PastilleVois key={t} sens="−" t={t} trad />)}</div></>}
      </>}
    </section>);
}

function SectionBio({ f }) {
  const W = useW();
  const [tout, setTout] = useState(false);
  const l = tout ? f.bio : f.bio.slice(0, 5);
  return (
    <section>
      <Titre n={f.bio.length}>Bioagresseurs</Titre>
      {!f.bio.length ? <Absence>Je n’ai pas l’information pour cette culture. Ce n’est pas une absence de risque.</Absence> :
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {l.map(([n, cat, per, sym]) => (
          <div key={n} style={{ background: W.cardAlt, borderRadius: 11, padding: '9px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <b style={{ fontSize: 13, color: W.txt }}>{n}</b><span style={{ fontSize: 11.5, color: W.txt3 }}>{cat}</span>
              {per && <span style={{ marginLeft: 'auto', fontSize: 11.5, fontWeight: 600, color: W.txt2, background: W.card, border: `1px solid ${W.border}`, borderRadius: 999, padding: '2px 9px', whiteSpace: 'nowrap' }}>risque : {per}</span>}
            </div>
            {sym && <div style={{ fontSize: 12, color: W.txt2, marginTop: 3, lineHeight: 1.45 }}>{sym}</div>}
          </div>))}
        {f.bio.length > 5 && !tout && <button onClick={() => setTout(true)} style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 5, background: 'none', border: 'none', padding: '4px 0 0', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, color: W.brandText }}>+ {f.bio.length - 5} autres<Ico n="chevD" c={W.brandText} s={14} w={2} /></button>}
      </div>}
    </section>);
}

// Coquille : même disposition adaptative que la FicheShell d'US-183 ; panneau de 560 px sur desktop.
function FicheCulture({ mode, c, ctx, echec, confKO, onClose, onCal }) {
  const W = useW();
  const f = ficheDe(c);
  const sheet = mode === 'sheet', side = mode === 'side';
  const box = sheet ? { position: 'absolute', inset: 0 } : side ?
    { position: 'absolute', top: 0, right: 0, bottom: 0, width: 560, borderLeft: `1px solid ${W.border}` } :
    { position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: 'min(600px, calc(100% - 40px))', height: 'calc(100% - 48px)', borderRadius: 18 };
  return (
    <>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(12,18,6,.45)', zIndex: 50 }} />
      <div role="dialog" aria-modal="true" aria-label={`Fiche culture : ${c.n}`} style={{ zIndex: 51, background: W.card, boxShadow: W.shadow, display: 'flex', flexDirection: 'column', overflow: 'hidden', ...box }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11, padding: '15px 17px', borderBottom: `1px solid ${W.border}`, flexShrink: 0 }}>
          <div style={{ width: 36, height: 36, borderRadius: 11, background: W.brandSoft, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Ico n="leaf" c={W.brand} s={18} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: wserif, fontSize: 20, fontWeight: 600, color: W.txt, letterSpacing: '-.015em' }}>{c.n}</div>
            <div style={{ fontSize: 12, color: W.txt3, marginTop: 2 }}>{c.fam || 'hors référentiel'} · zone {ZONE} · au {DATE_REF}</div>
            {ctx && <div style={{ marginTop: 7 }}><Badge tint="brand"><Ico n="pin" c={W.brand} s={12} w={2} />depuis {ctx.parcelle} · rang {ctx.rang}</Badge></div>}
          </div>
          <button onClick={onClose} aria-label="Fermer la fiche" style={{ display: 'flex', padding: 8, borderRadius: 9, border: 'none', background: W.cardAlt, cursor: 'pointer', flexShrink: 0 }}><Ico n="close" c={W.txt2} s={16} /></button>
        </div>
        <div className="s fc-body" style={{ padding: 17, overflowY: 'auto', minHeight: 0, flex: 1 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
            {f.horsRef ? <>
              <InfoBanner tint="blue" icon="book" title="Fiche absente du référentiel" body={`${c.n} n’est pas connue du référentiel : ni calendrier, ni caractéristiques, ni voisinages. Ce que tu cultives reste listé ci-dessous.`} />
              <SectionVarietes f={f} /></> : <>
              {echec && <InfoBanner tint="amber" icon="alert" title="Lecture incomplète" body="La composition de la fiche n’a pas pu être lue. « Maintenant » et la frise viennent de l’écran Cultures." action={<Btn small icon="swap">Réessayer</Btn>} />}
              <SectionMaintenant c={c} confKO={confKO} onCal={onCal} />
              <section>
                <Titre>Calendrier de la zone</Titre>
                {c.cal ? <MonthStrip {...c.frise} moisCourant={MOIS_REF} legend /> : <Absence>Aucune fenêtre connue pour cette zone.</Absence>}
                {c.cal && <div style={{ fontSize: 11.5, color: W.txt3, marginTop: 8 }}>Calendrier conseillé. Le calendrier recalé sur tes séries est dans la fiche calendrier.</div>}
              </section>
              {echec ? <><section><Titre>Référentiel</Titre><NonLu /></section><section><Titre>Variétés cultivées</Titre><NonLu /></section><section><Titre>Voisinages</Titre><NonLu /></section><section><Titre>Bioagresseurs</Titre><NonLu /></section></> : <>
                <SectionRef f={f} /><SectionVarietes f={f} /><SectionVoisinages f={f} /><SectionBio f={f} /></>}
            </>}
          </div>
        </div>
        <div style={{ padding: '12px 17px', borderTop: `1px solid ${W.border}`, background: W.cardAlt, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexShrink: 0 }}>
          <span style={{ fontSize: 11.5, color: W.txt3, lineHeight: 1.4 }}>Sources : Wind River Greens · CC BY 4.0 · EPPO</span>
          <Btn onClick={onClose}>Fermer</Btn>
        </div>
      </div>
    </>);
}

Object.assign(window, { FicheCulture });
