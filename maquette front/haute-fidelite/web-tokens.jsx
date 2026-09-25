const { useState, useContext, createContext, useRef, useEffect } = React;

const WEB_LIGHT = { mode:'light',
  bg:'#F5F7F1', surface:'#FFFFFF', card:'#FFFFFF', cardAlt:'#F1F5EB', border:'#E2E7DA', borderSoft:'#EDF0E7',
  brand:'#4A7C22', brandDeep:'#2F5416', brandSoft:'#EAF3DE', brandText:'#3B6A1B',
  txt:'#16210C', txt2:'#5A6B4B', txt3:'#8A9880',
  amber:'#B0740F', amberSoft:'#FBF1DC', red:'#AF3A2F', redSoft:'#FAE5E2', blue:'#2A6E8F', blueSoft:'#E3EFF4', violet:'#6B4FA0', violetSoft:'#EDE8F7',
  headerFrom:'#2F5416', headerTo:'#4E8226', headerTxt:'#FFFFFF', headerDim:'rgba(255,255,255,.74)', headerGlass:'rgba(255,255,255,.18)',
  shadow:'0 1px 2px rgba(22,33,12,.06), 0 4px 14px rgba(22,33,12,.05)' };

const WEB_DARK = { mode:'dark',
  bg:'#0F1409', surface:'#161D0F', card:'#1A2313', cardAlt:'#212C18', border:'#2C3822', borderSoft:'#232E19',
  brand:'#8EC452', brandDeep:'#A5D66A', brandSoft:'#1E2D12', brandText:'#9FD164',
  txt:'#E4EDD3', txt2:'#93A57E', txt3:'#6B7C58',
  amber:'#D9A03C', amberSoft:'#2A1F0A', red:'#D06052', redSoft:'#2A100D', blue:'#6FAECB', blueSoft:'#12242C', violet:'#A48BD8', violetSoft:'#1E1830',
  headerFrom:'#111A0A', headerTo:'#243A17', headerTxt:'#E4EDD3', headerDim:'rgba(228,237,211,.6)', headerGlass:'rgba(228,237,211,.10)',
  shadow:'0 1px 2px rgba(0,0,0,.4), 0 4px 14px rgba(0,0,0,.3)' };

const WCtx = createContext(WEB_LIGHT);
const useW = () => useContext(WCtx);
const wserif = "'Lora', Georgia, serif";

const P = {
  home:['M3 10.6 12 3.2l9 7.4','M5.4 9.4V20.8h13.2V9.4'],
  grid:['M3.5 3.5h7v7h-7z','M13.5 3.5h7v7h-7z','M3.5 13.5h7v7h-7z','M13.5 13.5h7v7h-7z'],
  leaf:['M4.5 19.5c9 2.2 16.5-4.5 16-14.4C11.6 4 4.6 9.4 6.4 15.4','M4.5 19.5c2.2-4.6 5.4-7.6 9.5-9.6'],
  sprout:['M12 21v-7.2','M12 13.8c0-3.2 2.2-5.4 5.4-5.4 0 3.2-2.2 5.4-5.4 5.4z','M12 13.8c0-2.8-1.9-4.7-4.7-4.7 0 2.8 1.9 4.7 4.7 4.7z'],
  box:['M3.2 7.3 12 3.2l8.8 4.1v9.4L12 20.8l-8.8-4.1z','M3.2 7.3 12 11.5l8.8-4.2','M12 11.5v9.3'],
  journal:['M4 4.5h13a2.5 2.5 0 0 1 2.5 2.5v12.5H6.5A2.5 2.5 0 0 1 4 17z','M7.5 8.5h8','M7.5 12h8','M7.5 15.5h5'],
  chart:['M4 19.8V11.5','M9.4 19.8V5.8','M14.8 19.8v-5.6','M20.2 19.8V9.2','M2.5 21.4h19'],
  bell:['M18 8.6a6 6 0 1 0-12 0c0 6.6-2.6 7.8-2.6 7.8h17.2S18 15.2 18 8.6z','M13.7 20.2a2 2 0 0 1-3.4 0'],
  help:['M12 2.2a9.8 9.8 0 1 0 .01 19.6A9.8 9.8 0 0 0 12 2.2z','M9.3 9.2a2.8 2.8 0 1 1 3.7 2.7c-.7.3-1 .9-1 1.6v.6','M12 17.4h.01'],
  search:['M11 3.6a7.4 7.4 0 1 0 .01 14.8A7.4 7.4 0 0 0 11 3.6z','M16.5 16.5 21 21'],
  cal:['M4 5.5h16v15H4z','M4 10h16','M8.5 3v4','M15.5 3v4'],
  sun:['M12 7.6a4.4 4.4 0 1 0 .01 8.8A4.4 4.4 0 0 0 12 7.6z','M12 1.8v2.4','M12 19.8v2.4','M4.4 4.4l1.7 1.7','M17.9 17.9l1.7 1.7','M1.8 12h2.4','M19.8 12h2.4','M4.4 19.6l1.7-1.7','M17.9 6.1l1.7-1.7'],
  cloud:['M7.4 18.5h9.4a4 4 0 0 0 .6-8 5.6 5.6 0 0 0-10.8-.9 3.9 3.9 0 0 0 .8 8.9z'],
  moon:['M20.8 13.2A8.8 8.8 0 1 1 10.8 3.2a6.9 6.9 0 0 0 10 10z'],
  dots:['M12 6h.01','M12 12h.01','M12 18h.01'],
  drop:['M12 3.2s6.2 6.6 6.2 10.6a6.2 6.2 0 0 1-12.4 0C5.8 9.8 12 3.2 12 3.2z'],
  basket:['M3 9.2h18l-1.6 10.2a2 2 0 0 1-2 1.7H6.6a2 2 0 0 1-2-1.7z','M8.2 9.2 11.4 3','M15.8 9.2 12.6 3'],
  plus:['M12 5v14','M5 12h14'],
  chevD:['M6 9.5 12 15l6-5.5'],
  chevR:['M9.5 5.5 15.5 12l-6 6.5'],
  edit:['M12.5 20.2H21','M16.8 3.6a2.1 2.1 0 0 1 3 3L7.6 18.8l-4 1 1-4z'],
  filter:['M3.4 5h17.2l-6.8 8v6.2l-3.6 1.8V13z'],
  pin:['M12 2.4c-3.8 0-6.9 3.1-6.9 6.9 0 5.2 6.9 12.3 6.9 12.3s6.9-7.1 6.9-12.3c0-3.8-3.1-6.9-6.9-6.9z','M12 6.6a2.6 2.6 0 1 0 .01 5.2A2.6 2.6 0 0 0 12 6.6z'],
  ruler:['M4 9.4V4h5.4','M20 14.6V20h-5.4','M4 14.6V20h5.4','M20 9.4V4h-5.4'],
  check:['M20 6.4 9.2 17.2 4 12'],
  clock:['M12 2.6a9.4 9.4 0 1 0 .01 18.8A9.4 9.4 0 0 0 12 2.6z','M12 7v5.4l3.4 2'],
  alert:['M12 3.4 21 19.6H3z','M12 9.6v4','M12 16.4h.01'],
  close:['M6 6l12 12','M18 6 6 18'],
  fileCsv:['M13.4 2.8H7a2 2 0 0 0-2 2v14.4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.4z','M13.4 2.8v5.6H19','M9.6 12.4H8.2v3.2h1.4','M12.2 12.4h1.6l-1.6 1.6h1.6','M16 12.4v3.2'],
  fileJson:['M13.4 2.8H7a2 2 0 0 0-2 2v14.4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.4z','M13.4 2.8v5.6H19','M9.4 12.2c-1 0-1 1.4-2 1.4 1 0 1 1.4 2 1.4','M14.6 12.2c1 0 1 1.4 2 1.4-1 0-1 1.4-2 1.4'],
  arrowR:['M4.5 12h14','M13 6.2 18.8 12 13 17.8'],
  drag:['M9 6h.01','M9 12h.01','M9 18h.01','M15 6h.01','M15 12h.01','M15 18h.01'],
  tag:['M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2.5 12.5V2.5h10l8.1 8.1a2 2 0 0 1 0 2.8z','M7 7h.01'],
  euro:['M17.5 5.6a7 7 0 1 0 0 12.8','M4.5 10h9','M4.5 14h9'],
  user:['M12 3.4a4.2 4.2 0 1 0 .01 8.4A4.2 4.2 0 0 0 12 3.4z','M4.4 20.6c0-4.2 3.4-6.6 7.6-6.6s7.6 2.4 7.6 6.6'],
  layers:['M12 3 3 7.6l9 4.6 9-4.6z','M3 12.4l9 4.6 9-4.6','M3 16.9l9 4.6 9-4.6'],
  menu:['M4 7h16','M4 12h16','M4 17h16'],
  book:['M4 4.6h6.4a2.6 2.6 0 0 1 2.6 2.6v13a2 2 0 0 0-2-2H4z','M20 4.6h-4.4A2.6 2.6 0 0 0 13 7.2v13a2 2 0 0 1 2-2h5z'],
  send:['M21.4 2.6 10.6 13.4','M21.4 2.6 14.6 21.4l-4-8-8-4z'],
  users:['M16.4 20.6v-1.8a4 4 0 0 0-4-4H6.6a4 4 0 0 0-4 4v1.8','M9.5 3.4a3.8 3.8 0 1 0 .01 7.6A3.8 3.8 0 0 0 9.5 3.4','M21.4 20.6v-1.8a4 4 0 0 0-3-3.85','M16.4 3.6a4 4 0 0 1 0 7.75'],
  logout:['M9.4 20.6H5a2 2 0 0 1-2-2V5.4a2 2 0 0 1 2-2h4.4','M16.2 16.4 20.6 12l-4.4-4.4','M20.6 12H9.4'],
  key:['M14.6 3.4a6 6 0 1 0-5 9.6l-.2.2L3.4 19.2v1.4h3.2v-2.2h2.2v-2.2h2l1.2-1.2A6 6 0 0 0 14.6 3.4z','M16.6 7.4h.01'],
  eye:['M1.6 12S5.6 4.8 12 4.8 22.4 12 22.4 12 18.4 19.2 12 19.2 1.6 12 1.6 12z','M12 8.8a3.2 3.2 0 1 0 .01 6.4A3.2 3.2 0 0 0 12 8.8z'],
  eyeOff:['M9.9 5.1A9.6 9.6 0 0 1 12 4.8c6.4 0 10.4 7.2 10.4 7.2a17 17 0 0 1-3 3.9','M6.5 6.6A17 17 0 0 0 1.6 12s4 7.2 10.4 7.2a9.5 9.5 0 0 0 4.3-1','M9.8 9.8a3.2 3.2 0 0 0 4.4 4.4','M2.6 2.6l18.8 18.8'],
  copy:['M9.4 9.4h9.2a1.8 1.8 0 0 1 1.8 1.8v9.2a1.8 1.8 0 0 1-1.8 1.8H9.4a1.8 1.8 0 0 1-1.8-1.8v-9.2a1.8 1.8 0 0 1 1.8-1.8z','M4.6 14.6H3.4a1.8 1.8 0 0 1-1.8-1.8V3.4a1.8 1.8 0 0 1 1.8-1.8h9.4a1.8 1.8 0 0 1 1.8 1.8v1.2'],
  swap:['M15.4 3.4 20.6 8.6l-5.2 5.2','M20.6 8.6H4.6','M8.6 20.6 3.4 15.4l5.2-5.2','M3.4 15.4h16'],
  godet:['M7.4 12.6h9.2l-1 7a1.6 1.6 0 0 1-1.6 1.4h-3.8a1.6 1.6 0 0 1-1.6-1.4z','M6.8 12.6h10.4','M12 12.6V9.3','M12 9.3c0-2 1.5-3.4 3.4-3.4 0 2-1.5 3.4-3.4 3.4z','M12 9.3c0-1.6-1.2-2.7-2.7-2.7 0 1.6 1.2 2.7 2.7 2.7z'],
  scissors:['M3 6a3 3 0 1 0 6 0 3 3 0 1 0-6 0','M3 18a3 3 0 1 0 6 0 3 3 0 1 0-6 0','M20 4 8.1 15.9','M14.5 14.5 20 20','M8.1 8.1 12 12'],
  skull:['M12 3.4a7.4 7.4 0 0 0-7.4 7.4c0 2.5 1.1 4.6 3.1 6v2.6a1 1 0 0 0 1 1h6.6a1 1 0 0 0 1-1v-2.6c2-1.4 3.1-3.5 3.1-6A7.4 7.4 0 0 0 12 3.4z','M9.3 12.2h.01','M14.7 12.2h.01','M9.6 17.6v2.4M12 17.6v2.8M14.4 17.6v2.4'],
};
const Ico = ({ n, c = 'currentColor', s = 18, w = 1.7 }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, display: 'block' }}>
    {(P[n] || []).map((d, i) => <path key={i} d={d} />)}
  </svg>);

const M_INI = ['J','F','M','A','M','J','J','A','S','O','N','D'];
const M_FULL = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'];

const WPARCELLES = [
{ id:1, nom:'Planche oignon', expo:'Est', surface:28.5, occupe:14, sol:'limoneux',
  cultures:[{n:'Échalote',v:'',p:25},{n:'Oignon',v:'rouge',p:50},{n:'Oignon',v:'blanc',p:50}] },
{ id:2, nom:'Maison', expo:'Est-ouest', surface:20, occupe:62, sol:'argileux',
  cultures:[{n:'Tomate',v:'Cœur de bœuf',p:14},{n:'Fraise',v:'',p:12},{n:'Basilic',v:'',p:8},{n:'Courge',v:'Butternut',p:6}] },
{ id:3, nom:'Serre', expo:'Sud', surface:12, occupe:88, sol:'terreau',
  cultures:[{n:'Tomate',v:'Cerise',p:20},{n:'Concombre',v:'',p:4},{n:'Basilic',v:'grand vert',p:3}] },
{ id:4, nom:'Buttes nord', expo:'Sud-ouest', surface:35, occupe:45, sol:'sableux',
  cultures:[{n:'Courgette',v:'jaune',p:7},{n:'Courgette',v:'verte',p:12},{n:'Potiron',v:'',p:3},{n:'Butternut',v:'',p:10}] },
{ id:5, nom:'Planche légumes', expo:'Ouest', surface:18, occupe:70, sol:'limoneux',
  cultures:[{n:'Aubergine',v:'',p:3},{n:'Betterave',v:'',p:50},{n:'Blette',v:'',p:8},{n:'Cornichon',v:'',p:7}] }];

const WCULTURES = [
{ n:'Tomate', v:'Cœur de bœuf', fam:'Solanacée', duree:'70-90 j', expo:'Plein soleil', eau:'Régulier', plants:14, lieu:'Maison', semis:[2,3], plant:[4,5], rec:[6,7,8,9] },
{ n:'Courgette', v:'jaune', fam:'Cucurbitacée', duree:'50-60 j', expo:'Plein soleil', eau:'Élevé', plants:7, lieu:'Buttes nord', semis:[3,4], plant:[4,5], rec:[5,6,7,8,9] },
{ n:'Oignon', v:'rouge', fam:'Alliacée', duree:'120-150 j', expo:'Plein soleil', eau:'Faible', plants:50, lieu:'Planche oignon', semis:[1,2], plant:[2,3], rec:[6,7] },
{ n:'Betterave', v:'', fam:'Chénopodiacée', duree:'90-110 j', expo:'Mi-ombre', eau:'Modéré', plants:50, lieu:'Planche légumes', semis:[3,4,5], plant:[], rec:[7,8,9] },
{ n:'Basilic', v:'grand vert', fam:'Lamiacée', duree:'60-70 j', expo:'Plein soleil', eau:'Régulier', plants:11, lieu:'Serre', semis:[3,4], plant:[4,5], rec:[6,7,8,9] },
{ n:'Butternut', v:'', fam:'Cucurbitacée', duree:'110-130 j', expo:'Plein soleil', eau:'Modéré', plants:10, lieu:'Buttes nord', semis:[3,4], plant:[5], rec:[8,9] },
{ n:'Fraise', v:'', fam:'Rosacée', duree:'vivace', expo:'Mi-ombre', eau:'Régulier', plants:12, lieu:'Maison', semis:[], plant:[7,8], rec:[4,5] },
{ n:'Concombre', v:'', fam:'Cucurbitacée', duree:'55-70 j', expo:'Plein soleil', eau:'Élevé', plants:4, lieu:'Serre', semis:[3], plant:[4,5], rec:[6,7,8] },
{ n:'Aubergine', v:'', fam:'Solanacée', duree:'100-120 j', expo:'Plein soleil', eau:'Régulier', plants:3, lieu:'Planche légumes', semis:[1,2], plant:[4], rec:[7,8,9] },
{ n:'Blette', v:'', fam:'Chénopodiacée', duree:'60-80 j', expo:'Mi-ombre', eau:'Modéré', plants:8, lieu:'Planche légumes', semis:[3,4], plant:[4,5], rec:[6,7,8,9] }];

const WPEP = [
{ n:'Butternut', v:'récolte 2025', taux:100, total:20, plantes:10, vendus:1, restants:9, d:'02/04/2026', j:126, st:1, germ:100 },
{ n:'Courge', v:'musquée de Provence', taux:100, total:18, plantes:10, vendus:0, restants:8, d:'05/04/2026', j:123, st:1, germ:100 },
{ n:'Courgette', v:'jaune', taux:100, total:20, plantes:7, vendus:1, restants:12, d:'12/04/2026', j:116, st:2, germ:100 },
{ n:'Courgette', v:'verte', taux:100, total:22, plantes:12, vendus:0, restants:10, d:'12/04/2026', j:116, st:2, germ:100 },
{ n:'Tomate', v:'Cœur de bœuf', taux:89, total:45, plantes:29, vendus:9, restants:2, d:'15/03/2026', j:144, st:2, germ:89 },
{ n:'Potiron', v:'', taux:55, total:20, plantes:3, vendus:0, restants:8, d:'20/04/2026', j:108, st:1, germ:55 },
{ n:'Blette', v:'', taux:40, total:30, plantes:8, vendus:0, restants:4, d:'25/04/2026', j:103, st:0, germ:40 },
{ n:'Cornichon', v:'', taux:78, total:23, plantes:10, vendus:0, restants:8, d:'18/04/2026', j:110, st:1, germ:78 }];

const PEP_STADES = [{ l:'Germin.', k:'blue' }, { l:'Godet', k:'amber' }, { l:'Terre', k:'brand' }];

const WSTOCKS = [
{ n:'Ail', o:'Pied acheté', t:'achat', q:70, u:'gousses', rec:0 },
{ n:'Aubergine', o:'Pépinière', t:'pep', q:4, u:'plants', rec:0 },
{ n:'Basilic', o:'Pied acheté', t:'achat', q:8, u:'plants', rec:0 },
{ n:'Betterave', o:'Semis pleine terre', t:'semis', q:42, u:'graines', rec:0 },
{ n:'Blette', o:'Pépinière', t:'pep', q:12, u:'plants', rec:4 },
{ n:'Butternut', o:'Pépinière', t:'pep', q:8, u:'plants', rec:0 },
{ n:'Carotte', o:'Semis pleine terre', t:'semis', q:2, u:'m²', rec:3.5 },
{ n:'Concombre', o:'Pépinière', t:'pep', q:5, u:'plants', rec:1.4 },
{ n:'Cornichon', o:'Pépinière', t:'pep', q:12, u:'plants', rec:5.4 },
{ n:'Courgette', o:'Pépinière', t:'pep', q:7, u:'plants', rec:3.8 },
{ n:'Fraise', o:'Pied acheté', t:'achat', q:12, u:'plants', rec:1.8 },
{ n:'Tomate', o:'Pépinière', t:'pep', q:34, u:'plants', rec:2.4 }];

const WJOURNAL = [
{ d:'Aujourd’hui · 6 août', items:[
  { t:'recolte', c:'Courgette', txt:'Récolte de 1,2 kg de courgettes', loc:'Buttes nord', h:'08:40' },
  { t:'arrosage', c:'', txt:'Arrosage de la serre', loc:'Serre', h:'08:10' }] },
{ d:'Hier · 5 août', items:[
  { t:'vente', c:'Tomate', txt:'Vente de 3 pieds de tomate Cœur de bœuf', loc:'Pépinière', h:'17:20' },
  { t:'recolte', c:'Tomate', txt:'Récolte de 0,8 kg de tomates', loc:'Serre', h:'11:05' },
  { t:'entretien', c:'Tomate', txt:'Taille des gourmands sur 14 pieds', loc:'Maison', h:'10:30' }] },
{ d:'Lundi 3 août', items:[
  { t:'plantation', c:'Butternut', txt:'Mise en place de 8 plants de butternut', loc:'Buttes nord', h:'16:00' },
  { t:'perte', c:'Potiron', txt:'Perte de 4 godets de potiron (fonte des semis)', loc:'Pépinière', h:'11:40' },
  { t:'godet', c:'Courgette', txt:'Formation d’un lot godet de 20 courgettes', loc:'Pépinière', h:'10:05' },
  { t:'semis', c:'Mâche', txt:'Semis de mâche en pleine terre', loc:'Planche légumes', h:'09:15' }] }];

const WTODO = [
{ txt:'Repiquer les 8 butternut restants', qd:'Cette semaine', prio:'haute', loc:'Buttes nord' },
{ txt:'Tuteurer les tomates de la serre', qd:'Avant vendredi', prio:'haute', loc:'Serre' },
{ txt:'Semer les haricots de fin de saison', qd:'Cette semaine', prio:'moyenne', loc:'Planche légumes' },
{ txt:'Arroser les fraisiers', qd:'Demain', prio:'basse', loc:'Maison' }];

const WMETEO = { ville:'Argenteuil', temp:22, desc:'Ciel dégagé', ressenti:19, humid:44, vent:14,
  prev:[{ j:'VEN', ic:'sun', max:27, min:14, pluie:0 },{ j:'SAM', ic:'cloud', max:30, min:17, pluie:0 },{ j:'DIM', ic:'cloud', max:32, min:17, pluie:10 },{ j:'LUN', ic:'sun', max:32, min:21, pluie:3 }] };

const WRECOLTES = [
{ n:'Courgette', kg:3.8 },{ n:'Tomate', kg:2.4 },{ n:'Fraise', kg:1.8 },{ n:'Oignon', kg:1.6 },{ n:'Concombre', kg:1.4 },{ n:'Cornichon', kg:0.6 }];

const WHARVEST = {
  Courgette:{ 5:0.6, 6:2.0, 7:1.2 }, Tomate:{ 6:0.9, 7:1.5 }, Fraise:{ 4:1.1, 5:0.7 },
  Oignon:{ 5:0.8, 6:0.8 }, Concombre:{ 6:0.5, 7:0.9 }, Cornichon:{ 6:0.2, 7:0.4 } };
const WH_MOIS = [4,5,6,7];
const WH_LBL = { 3:'Avr.', 4:'Mai', 5:'Juin', 6:'Juil.', 7:'Août', 8:'Sept.', 9:'Oct.' };
const WCUMUL_MOIS = [3,4,5,6,7];
const FAM_OF = { Tomate:'Solanacée', Aubergine:'Solanacée', Poivron:'Solanacée',
  Courgette:'Cucurbitacée', Courge:'Cucurbitacée', Butternut:'Cucurbitacée', Potiron:'Cucurbitacée', Concombre:'Cucurbitacée', Cornichon:'Cucurbitacée',
  Oignon:'Alliacée', 'Échalote':'Alliacée', Ail:'Alliacée', Poireau:'Alliacée',
  Betterave:'Chénopodiacée', Blette:'Chénopodiacée', 'Épinard':'Chénopodiacée',
  Basilic:'Lamiacée', Fraise:'Rosacée', Carotte:'Apiacée', Chou:'Brassicacée', Salade:'Astéracée' };
function famOf(n) { return FAM_OF[n] || 'Autres'; }
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
const WCULT_CLR = {
  Courgette:{ l:'#A06B10', d:'#D9A03C' }, Tomate:{ l:'#B5451A', d:'#E0713A' }, Fraise:{ l:'#9A2848', d:'#D2607F' },
  Oignon:{ l:'#6E8A22', d:'#A8CC55' }, Concombre:{ l:'#2E7A52', d:'#5FBF8C' }, Cornichon:{ l:'#4A7C22', d:'#8EC452' } };
function wcultClr(n, W) { const c = WCULT_CLR[n]; return c ? (W.mode === 'dark' ? c.d : c.l) : W.brand; }

const WUSER = { prenom:'Rémy', nom:'Rémy Eremy', email:'remy@eremy.fr', initiale:'R', telegram:{ lie:true, compte:'@remy_potager' } };
const WPOTAGERS = [
{ id:1, nom:'Potager de Rémy', role:'owner', membres:3, parcelles:5, actif:true, ville:'Cormeilles-en-Parisis, Île-de-France', etat:'actif' },
{ id:2, nom:'Jardin partagé des Coteaux', role:'editor', membres:11, parcelles:14, actif:false, ville:'Lyon, Auvergne-Rhône-Alpes', etat:'actif' },
{ id:3, nom:'Serre expérimentale', role:'viewer', membres:2, parcelles:2, actif:false, ville:'', etat:'actif' }];
const WROLES = { owner:{ l:'Propriétaire', t:'brand' }, editor:{ l:'Éditeur', t:'blue' }, viewer:{ l:'Lecture seule', t:'violet' } };
const WARCHIVES = [
{ id:11, nom:'Potager de la Ferme', role:'owner', parcelles:6, membres:2, le:'12 nov. 2025' },
{ id:12, nom:'Balcon d’essai', role:'owner', parcelles:1, membres:1, le:'3 févr. 2026' }];
const WCORBEILLE = [
{ id:21, nom:'Potager test', parcelles:2, le:'8 août 2026', reste:'22 jours' }];
const WMEMBRES = [
{ nom:'Rémy Eremy', email:'remy@eremy.fr', role:'owner', depuis:'janv. 2026', moi:true },
{ nom:'Claire Bertin', email:'claire.bertin@gmail.com', role:'editor', depuis:'mars 2026' },
{ nom:'Paul Ménard', email:'p.menard@gmail.com', role:'viewer', depuis:'mai 2026' }];
const WAPI_VERSION = '1.12.0';


const WSUIVI = [
{ n:'Tomate', v:'Cœur de bœuf', fam:'Solanacée', et:'potager', o:'Pépinière', p:['Maison','Serre'], ent:45, u:'pieds', place:14, ven:9, per:3, rec:2.4, nrec:6 },
{ n:'Tomate', v:'Cerise', fam:'Solanacée', et:'potager', o:'Pépinière', p:['Serre'], ent:24, u:'pieds', place:20, ven:0, per:1, rec:1.1, nrec:3 },
{ n:'Aubergine', v:'', fam:'Solanacée', et:'potager', o:'Pépinière', p:['Planche légumes'], ent:6, u:'pieds', place:3, ven:0, per:1, rec:0, nrec:0 },
{ n:'Courgette', v:'jaune', fam:'Cucurbitacée', et:'potager', o:'Pépinière', p:['Buttes nord'], ent:20, u:'pieds', place:7, ven:1, per:0, rec:3.8, nrec:9 },
{ n:'Courgette', v:'verte', fam:'Cucurbitacée', et:'potager', o:'Pépinière', p:['Buttes nord'], ent:22, u:'pieds', place:12, ven:0, per:2, rec:2.2, nrec:5 },
{ n:'Butternut', v:'', fam:'Cucurbitacée', et:'potager', o:'Pépinière', p:['Buttes nord','Maison'], ent:20, u:'pieds', place:10, ven:1, per:0, rec:0, nrec:0 },
{ n:'Concombre', v:'', fam:'Cucurbitacée', et:'potager', o:'Pied acheté', p:['Serre'], ent:4, u:'pieds', place:4, ven:0, per:0, rec:1.4, nrec:4 },
{ n:'Cornichon', v:'', fam:'Cucurbitacée', et:'semis', o:'Semis pleine terre', p:['Planche légumes'], ent:23, u:'pieds', place:12, ven:0, per:3, rec:5.4, nrec:11 },
{ n:'Courge', v:'musquée de Provence', fam:'Cucurbitacée', et:'pep', o:'Pépinière', p:['Pépinière'], ent:18, u:'godets', place:8, ven:0, per:0, rec:0, nrec:0 },
{ n:'Potiron', v:'', fam:'Cucurbitacée', et:'pep', o:'Pépinière', p:['Pépinière'], ent:20, u:'godets', place:8, ven:0, per:9, rec:0, nrec:0 },
{ n:'Oignon', v:'rouge', fam:'Alliacée', et:'semis', o:'Semis pleine terre', p:['Planche oignon'], ent:60, u:'pieds', place:50, ven:0, per:6, rec:1.6, nrec:2 },
{ n:'Ail', v:'', fam:'Alliacée', et:'potager', o:'Pied acheté', p:['Planche oignon'], ent:74, u:'gousses', place:70, ven:0, per:4, rec:0, nrec:0 },
{ n:'Échalote', v:'', fam:'Alliacée', et:'potager', o:'Pied acheté', p:['Planche oignon'], ent:25, u:'pieds', place:25, ven:0, per:0, rec:0, nrec:0 },
{ n:'Betterave', v:'', fam:'Chénopodiacée', et:'semis', o:'Semis pleine terre', p:['Planche légumes'], ent:50, u:'pieds', place:42, ven:0, per:5, rec:0, nrec:0 },
{ n:'Blette', v:'', fam:'Chénopodiacée', et:'potager', o:'Pépinière', p:['Planche légumes'], ent:30, u:'pieds', place:8, ven:0, per:1, rec:0.4, nrec:1 },
{ n:'Fraise', v:'', fam:'Rosacée', et:'potager', o:'Pied acheté', p:['Maison'], ent:12, u:'pieds', place:12, ven:0, per:0, rec:1.8, nrec:7 },
{ n:'Basilic', v:'grand vert', fam:'Lamiacée', et:'potager', o:'Pied acheté', p:['Serre','Maison'], ent:13, u:'pieds', place:11, ven:0, per:2, rec:0, nrec:0 }];
const SUIVI_ET = { potager:{ l:'Au potager', t:'brand' }, pep:{ l:'En pépinière', t:'amber' }, semis:{ l:'Semis pleine terre', t:'blue' } };
function iniOf(n) { return n.normalize('NFD').replace(/[̀-ͯ]/g, '')[0].toUpperCase(); }

const PHASE = { semis:{ label:'Semis', key:'blue' }, plant:{ label:'Plantation', key:'brand' }, rec:{ label:'Récolte', key:'amber' } };

Object.assign(window, { WARCHIVES, WCORBEILLE });
Object.assign(window, { WEB_LIGHT, WEB_DARK, WCtx, useW, wserif, Ico, M_INI, M_FULL, WPARCELLES, WCULTURES, WPEP, PEP_STADES, WSTOCKS, WJOURNAL, WTODO, WMETEO, WRECOLTES, WHARVEST, WH_MOIS, WH_LBL, WCUMUL_MOIS, FAM_OF, famOf, ALPHABET, wcultClr, WUSER, WPOTAGERS, WROLES, WMEMBRES, WAPI_VERSION, PHASE, WSUIVI, SUIVI_ET, iniOf });
