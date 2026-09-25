// ÉPIC 11 — données de la maquette Cultures (US-204 à US-207).
// Date de référence : 18 septembre 2026 (mois 8, indexé depuis 0). Zone océanique.
// Parcelles reprises de la maquette gelée « Plan – rangs et places ».
const DATE_REF = '18 septembre 2026', DATE_REF_C = '18 sept. 2026', MOIS_REF = 8, ZONE = 'océanique';
const R_ = (a, b) => { const o = []; for (let i = a; i <= b; i++) o.push(i % 12); return o; };

// fen : maintenant | bientot | plustard | aucune (US-204 / CA5). stars : geste le mieux noté (US-180).
const CULTURES = [
{ id:'tomate', n:'Tomate', fam:'Solanacée', vars:['cœur de bœuf','cerise','noire de Crimée'], ph:'recolte', parc:3, lots:1, stars:1, fen:'plustard', geste:'semer en pépinière', fenMois:'février → mars', frise:{ semis:[1,2], plant:[3,4], rec:[6,7,8] } },
{ id:'courgette', n:'Courgette', fam:'Cucurbitacée', vars:['jaune','non précisée'], ph:'recolte', parc:3, lots:0, stars:1, fen:'plustard', geste:'semer en pépinière', fenMois:'avril → mai', frise:{ semis:[3,4,5], plant:[4,5], rec:[6,7,8] } },
{ id:'haricot', n:'Haricot', fam:'Fabacée', vars:['nain beurre'], ph:'semee', parc:1, lots:0, stars:1, fen:'plustard', geste:'semer en place', fenMois:'mai → juillet', frise:{ semis:[4,5,6], plant:[], rec:[6,7,8] } },
{ id:'ail', n:'Ail', fam:'Alliacée', vars:['violet de Cadours'], ph:'place', parc:2, lots:0, stars:null, fen:'aucune', cal:false, frise:{ semis:[], plant:[], rec:[] } },
{ id:'carotte', n:'Carotte', fam:'Apiacée', vars:['nantaise'], ph:'place', parc:2, lots:0, stars:1, fen:'plustard', geste:'semer en place', fenMois:'mars → juillet', frise:{ semis:R_(2,6), plant:[], rec:R_(6,10) } },
{ id:'poivron', n:'Poivron', fam:'Solanacée', vars:['doux d’Espagne','piment d’Espelette'], ph:'recolte', parc:1, lots:0, stars:1, fen:'plustard', geste:'semer en pépinière', fenMois:'février → mars', frise:{ semis:[1,2], plant:[4], rec:[7,8] } },
{ id:'rutabaga', n:'Rutabaga', fam:'Brassicacée', vars:['champêtre'], ph:'semee', parc:1, lots:0, stars:1, fen:'plustard', geste:'semer en place', fenMois:'juin → juillet', frise:{ semis:[5,6], plant:[], rec:[9,10,11] } },
{ id:'laitue', n:'Laitue', fam:'Astéracée', vars:['merveille d’hiver'], ph:null, parc:0, lots:1, stars:3, fen:'maintenant', geste:'planter', fenMois:'septembre → octobre', recAtt:'entre mars et avril', frise:{ semis:[7,8], plant:[8,9], rec:[2,3] } },
{ id:'chou', n:'Chou', fam:'Brassicacée', vars:['cabus de printemps'], ph:'place', parc:1, lots:0, stars:2, fen:'bientot', geste:'planter', fenMois:'octobre → novembre', frise:{ semis:[7], plant:[9,10], rec:[2,3,4] } },
{ id:'verveine', n:'Verveine', fam:null, vars:['citronnelle'], ph:'place', parc:1, lots:0, stars:null, fen:'aucune', horsRef:true, cal:false, frise:null },
{ id:'epinard', n:'Épinard', fam:'Amaranthacée', vars:[], stars:3, fen:'maintenant', geste:'semer en place', fenMois:'août → octobre', recAtt:'entre le 25 octobre et le 15 novembre', frise:{ semis:[2,3,7,8,9], plant:[], rec:[4,5,10,11] } },
{ id:'mache', n:'Mâche', fam:'Caprifoliacée', vars:[], stars:3, fen:'maintenant', geste:'semer en place', fenMois:'juillet → octobre', recAtt:'à partir de mi-novembre', frise:{ semis:R_(6,9), plant:[], rec:[10,11,0,1,2] } },
{ id:'fraisier', n:'Fraisier', fam:'Rosacée', vars:[], stars:3, fen:'maintenant', geste:'planter', fenMois:'août → septembre', recAtt:'à partir de mai 2027', frise:{ semis:[], plant:[7,8], rec:[4,5,6] } },
{ id:'navet', n:'Navet', fam:'Brassicacée', vars:[], stars:2, fen:'maintenant', geste:'semer en place', fenMois:'juillet → septembre', recAtt:'entre mi-novembre et décembre', frise:{ semis:[2,3,6,7,8], plant:[], rec:[4,5,9,10] } },
{ id:'oignon', n:'Oignon blanc', fam:'Alliacée', vars:[], stars:2, fen:'maintenant', geste:'semer en place', fenMois:'août → septembre', recAtt:'entre avril et mai', frise:{ semis:[7,8], plant:[], rec:[3,4] } },
{ id:'radis', n:'Radis', fam:'Brassicacée', vars:[], stars:2, fen:'maintenant', geste:'semer en place', fenMois:'mars → septembre', recAtt:'vers le 15 octobre', frise:{ semis:R_(2,8), plant:[], rec:R_(3,9) } },
{ id:'feve', n:'Fève', fam:'Fabacée', vars:[], stars:2, fen:'bientot', geste:'semer en place', fenMois:'octobre → novembre', frise:{ semis:[9,10,1,2], plant:[], rec:[4,5] } },
{ id:'poireau', n:'Poireau', fam:'Alliacée', vars:[], stars:1, fen:'plustard', geste:'semer en pépinière', fenMois:'février → avril', frise:{ semis:[1,2,3], plant:[4,5,6], rec:[9,10,11,0,1] } },
{ id:'basilic', n:'Basilic', fam:'Lamiacée', vars:[], stars:1, fen:'plustard', geste:'semer en pépinière', fenMois:'mars → avril', frise:{ semis:[2,3], plant:[4,5], rec:[6,7,8] } },
{ id:'betterave', n:'Betterave', fam:'Amaranthacée', vars:[], stars:1, fen:'plustard', geste:'semer en place', fenMois:'avril → juin', frise:{ semis:[3,4,5], plant:[], rec:R_(6,9) } },
{ id:'pois', n:'Pois', fam:'Fabacée', vars:[], stars:1, fen:'plustard', geste:'semer en place', fenMois:'février → avril', frise:{ semis:[1,2,3], plant:[], rec:[4,5,6] } },
{ id:'aubergine', n:'Aubergine', fam:'Solanacée', vars:[], stars:1, fen:'plustard', geste:'semer en pépinière', fenMois:'février → mars', frise:{ semis:[1,2], plant:[4], rec:[7,8] } },
{ id:'persil', n:'Persil', fam:'Apiacée', vars:[], stars:1, fen:'plustard', geste:'semer en place', fenMois:'mars → juin', frise:{ semis:R_(2,5), plant:[], rec:R_(5,10) } },
{ id:'celeri', n:'Céleri', fam:'Apiacée', vars:[], stars:null, fen:'aucune', cal:false, frise:{ semis:[], plant:[], rec:[] } }];
CULTURES.forEach((c) => { c.present = !!(c.ph || c.lots); if (c.cal === undefined) c.cal = true; });

const FEN_ORD = { maintenant:0, bientot:1, plustard:2, aucune:3 };
const CONF_MOT = { 3:'élevée', 2:'moyenne', 1:'faible' };
const capz = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const plur = (n, s, p) => `${n} ${n > 1 ? (p || s + 's') : s}`;

// US-204 / CA6 — au plus trois, absentes, fenêtre ouverte, ≥ 2 étoiles ; seuils écrits ici seulement.
const SUGG_MAX = 3, SUGG_MIN_ETOILES = 2;
function suggestionsDe(list) {
  return list.filter((c) => !c.present && c.fen === 'maintenant' && (c.stars || 0) >= SUGG_MIN_ETOILES)
    .sort((a, b) => b.stars - a.stars || a.n.localeCompare(b.n, 'fr')).slice(0, SUGG_MAX);
}
function fenLabel(c) {
  if (!c.cal) return null;
  if (c.fen === 'maintenant') return { b: true, t: `${capz(c.geste)} maintenant` };
  if (c.fen === 'bientot') return { t: `bientôt : ${c.geste} ${c.fenMois}` };
  return { t: `prochaine fenêtre : ${c.geste} ${c.fenMois}` };
}
function moisActifs(c) { return c.frise ? [...c.frise.semis, ...c.frise.plant] : []; }

// US-206 — composition de la fiche. null = « non renseigné », jamais deviné (CA2, CA3).
const PARC = ['planche-centrale', 'planche-ombre', 'planche-est'];
const FICHE = {
  tomate: { ref:{ fam:'Solanacée · retour 4 ans', expo:'Plein soleil', eau:'Élevé', rust:'Gélive · 2 °C', prof:'0,5 cm', levee:'6 à 10 j', delai:'6 à 8 semaines', plantRec:'60 à 80 j', organe:'Reproducteur' },
    varietes:[{ v:'cœur de bœuf', parc:[['planche-centrale','recolte'],['planche-ombre','place']] },
      { v:'cerise', parc:[['planche-ombre','recolte'],['planche-est','place']], lots:[['#128','en godet','Serre']] },
      { v:'noire de Crimée', parc:[['planche-centrale','place'],['planche-ombre','place']] }],
    vois:{ plus:['basilic','carotte','persil'], moins:['pomme de terre','fenouil'], tradPlus:['œillet d’Inde'], tradMoins:['chou'] },
    bio:[['Mildiou','champignon','juillet → septembre','Taches brunes sur les feuilles, feutrage blanc au revers'],['Doryphore','insecte','mai → août','Feuilles dévorées, larves orangées'],['Oïdium','champignon',null,'Feutrage blanc et poudreux sur les feuilles'],['Aleurode','insecte','juin → septembre',null],['Botrytis','champignon',null,'Pourriture grise sur tiges et fruits'],['Puceron','insecte','avril → juillet',null],['Noctuelle','insecte',null,null]] },
  courgette: { ref:{ fam:'Cucurbitacée · retour 3 ans', expo:'Plein soleil', eau:'Élevé', rust:null, prof:'2 à 3 cm', levee:'5 à 8 j', delai:'3 à 4 semaines', plantRec:'45 à 60 j', organe:'Reproducteur' },
    varietes:[{ v:'jaune', parc:[['planche-centrale','recolte'],['planche-ombre','place'],['planche-est','recolte']] }, { v:'non précisée', parc:[['planche-centrale','semee']] }],
    vois:{ plus:['haricot','maïs'], moins:['pomme de terre'], tradPlus:['capucine'], tradMoins:[] },
    bio:[['Oïdium','champignon','juillet → septembre','Feutrage blanc sur les feuilles âgées'],['Limace','mollusque','avril → juin','Jeunes plants rongés au collet'],['Puceron','insecte',null,null],['Mosaïque du concombre','virus',null,'Marbrures jaunes, fruits déformés']] },
  epinard: { ref:{ fam:'Amaranthacée · retour 3 ans', expo:'Mi-ombre', eau:'Régulier', rust:'−8 °C', prof:'2 cm', levee:'7 à 14 j', delai:null, plantRec:null, organe:'Végétatif' },
    varietes:[], vois:null,
    bio:[['Mildiou de l’épinard','champignon',null,'Taches jaunes dessus, duvet violacé dessous'],['Mouche de la betterave','insecte','mai → juin','Galeries translucides dans les feuilles']] },
  ail: { ref:{ fam:'Alliacée · retour 4 ans', expo:'Plein soleil', eau:'Faible', rust:'−15 °C', prof:null, levee:null, delai:null, plantRec:null, organe:'Végétatif' },
    varietes:[{ v:'violet de Cadours', parc:[['planche-est','place'],['planche-ombre','place']] }],
    vois:{ plus:['carotte','tomate'], moins:['haricot','pois'], tradPlus:[], tradMoins:[] },
    bio:[['Rouille','champignon',null,'Pustules orangées sur les feuilles'],['Teigne du poireau','insecte','mai → septembre',null]] },
  laitue: { ref:{ fam:'Astéracée · retour 2 ans', expo:'Mi-ombre', eau:'Régulier', rust:'−6 °C', prof:'0,5 cm', levee:'4 à 8 j', delai:'4 à 5 semaines', plantRec:null, organe:'Végétatif' },
    varietes:[{ v:'merveille d’hiver', parc:[], lots:[['#131','semé en caissette','Serre']] }],
    vois:{ plus:['radis','carotte'], moins:[], tradPlus:[], tradMoins:[] }, bio:[['Limace','mollusque','toute l’année','Feuilles trouées, traces de mucus'],['Puceron','insecte',null,null]] },
  mache: { ref:{ fam:'Caprifoliacée · retour 2 ans', expo:'Mi-ombre', eau:'Modéré', rust:'−15 °C', prof:'1 cm', levee:'10 à 15 j', delai:null, plantRec:null, organe:'Végétatif' }, varietes:[], vois:null, bio:[] },
  verveine: { horsRef:true, varietes:[{ v:'citronnelle', parc:[['planche-est','place']] }] } };

function ficheDe(c) {
  if (FICHE[c.id]) return FICHE[c.id];
  let k = 0;
  return { ref:{ fam:c.fam, expo:null, eau:null, rust:null, prof:null, levee:null, delai:null, plantRec:null, organe:null },
    varietes:c.vars.map((v) => ({ v, parc:Array.from({ length:Math.max(1, Math.round(c.parc / c.vars.length)) }, () => [PARC[k++ % 3], c.ph]).filter((p) => p[1]) })),
    vois:null, bio:[] };
}

// Données passées à la fiche calendrier d'US-183 (FicheShell, non modifiée).
const RG = (etat, motif, pts, max) => ({ etat, motif, pts, max });
function calDe(c, ctx) {
  const f = ficheDe(c);
  let series = [];
  f.varietes.forEach((v) => (v.parc || []).forEach(([p, ph]) => series.push({ parcelle:p, origine:ph === 'semee' ? 'semis' : 'plantation', origineL:(ph === 'semee' ? 'Semée' : 'Plantée') + (v.v !== 'non précisée' ? ' · ' + v.v : '') })));
  if (ctx) series.sort((a, b) => (b.parcelle === ctx.parcelle) - (a.parcelle === ctx.parcelle));
  const base = { culture:c.n, variete:'', zone:ZONE, dateRef:DATE_REF, moisRef:MOIS_REF, series, frise:c.frise || { semis:[], plant:[], rec:[] } };
  if (!c.cal) return { ...base, sansCalendrier:true, actions:[], friseTitre:'Aucune fenêtre connue pour cette zone' };
  const k = c.geste.includes('pépinière') ? 'pepiniere' : c.geste.startsWith('planter') ? 'plantation' : 'semis_place';
  const regles = c.stars === 3 ?
    [RG('ok','Dans la fenêtre conseillée pour ta zone',40,40), RG('ok','Dernière gelée moyenne passée',20,20), RG('ok','Aucun gel annoncé sur 14 jours',20,20), RG('ko','Nuits fraîches : levée lente probable',0,10), RG('ok','La récolte arriverait avant la fin de saison',10,10)] :
    c.stars === 2 ?
    [RG('ko',`Fenêtre conseillée le mois prochain : ${c.fenMois}`,20,40), RG('ok','Dernière gelée moyenne passée',20,20), RG('ok','Aucun gel annoncé sur 14 jours',20,20), RG('ko','Nuits fraîches : levée lente probable',0,10), RG('ko','La récolte arriverait tard dans la saison',0,10)] :
    [RG('ko',`Hors de la fenêtre conseillée : ${c.fenMois}`,0,40), RG('ok', k === 'pepiniere' ? 'Semis en pépinière : gelée sans objet' : 'Dernière gelée moyenne passée',20,20), RG('ko','Du gel est possible avant la récolte',0,20), RG('ok','Nuits douces sur les 7 prochains jours',10,10), RG('ko','La récolte arriverait après la fin de saison',0,10)];
  const score = regles.reduce((s, r) => s + r.pts, 0);
  return { ...base, actions:[{ k, l:capz(c.geste), cta:k === 'plantation' ? 'Enregistrer la plantation' : 'Enregistrer le semis', fenetre:c.fenMois, score,
    recolte:c.recAtt || 'hors de la fenêtre de récolte de la zone', regles }],
    friseTitre: ctx ? `Calendrier recalé sur la série de ${ctx.parcelle}` : series.length ? 'Calendrier recalé sur les séries en terre' : `Calendrier conseillé pour la zone ${ZONE}` };
}

Object.assign(window, { DATE_REF, DATE_REF_C, MOIS_REF, ZONE, CULTURES, FEN_ORD, CONF_MOT, capz, norm, plur, suggestionsDe, fenLabel, moisActifs, ficheDe, calDe, SUGG_MAX });
