// [US-271] Parler au compagnon depuis la PWA — la logique pure du panneau.
//
// Le panneau ne décide de RIEN (cadrage §4.6, règle R5) : il envoie la phrase à
// `POST /compagnon/messages`, montre ce qui revient, et clique pour confirmer ou
// abandonner. Ce module range ce qui se calcule sans écran : les deux modes, le fil de
// la conversation (historique + messages spontanés + réponses), l'état d'une carte et
// les erreurs dites en clair (CA4). Testé par `npm test` (`compagnon.test.js`).

/** CA1 — les deux modes du panneau. Extra viendra avec US-274. */
export const MODES = [
  {
    id: 'normal',
    libelle: 'Normal',
    aide: 'Noter un geste, poser une question, demander une action.',
    invite: 'Ex. : j’ai arrosé la serre',
  },
  {
    id: 'support',
    libelle: 'Support',
    aide: 'Comprendre l’application. Rien n’est écrit dans ce mode.',
    invite: 'Ex. : comment effacer mon carnet ?',
  },
]
export const MODE_DEFAUT = 'normal'

export const modeValide = (id) => MODES.some((m) => m.id === id)
export const modeDe = (id) => MODES.find((m) => m.id === id) ?? MODES[0]

// ── CA4 : les erreurs, en clair ─────────────────────────────────────────────

const MOTIF_RESEAU = /failed to fetch|networkerror|load failed|network request failed|fetch failed/i

export const TEXTE_RESEAU =
  'Pas de connexion : ton message n’est pas parti, rien n’a été enregistré. Vérifie le réseau puis réessaie.'

/**
 * La phrase d'erreur que le jardinier lit. Jamais un code, jamais « Erreur API 500 » seul :
 * ce qui s'est passé, et ce qui n'a pas été fait.
 */
export function messageErreur(err) {
  if (!err) return 'Quelque chose n’a pas marché. Rien n’a été enregistré.'
  const message = typeof err === 'string' ? err : err.message ?? ''
  if (err.name === 'TypeError' || MOTIF_RESEAU.test(message)) return TEXTE_RESEAU
  switch (err.statut) {
    case 404:
      return 'Cette proposition n’existe plus : elle a expiré ou une plus récente l’a remplacée. Rien n’a été enregistré.'
    case 409:
      // Le serveur dit déjà où et quand (« Cette proposition a déjà été confirmée à 14 h 02, dans Telegram »).
      return message || 'Cette proposition a déjà été traitée : je ne refais rien.'
    case 403:
      return message || 'Tu n’as pas le droit d’enregistrer sur ce potager (lecture seule).'
    case 503:
      return message || 'Le service de langage est indisponible un instant. Rien n’a été enregistré, réessaie dans quelques minutes.'
    case 422:
      return message || 'Je n’ai pas compris ce message.'
    default:
  }
  if (/^Erreur API \d+/.test(message) || !message) {
    return 'Quelque chose n’a pas marché de mon côté. Rien n’a été enregistré, réessaie dans un instant.'
  }
  return message
}

/** Une erreur de proposition déjà traitée ou disparue : la carte ne se rejoue plus. */
export const carteDefinitivementFermee = (err) => err?.statut === 404 || err?.code === 'deja_traitee'

// ── CA2 : l'état d'une carte ────────────────────────────────────────────────

/**
 * Ce qu'une carte montre de son état. `finale` : plus aucun bouton n'a de sens.
 * `tone` suit les teintes du design system (brand, amber, red, blue).
 */
export function etatCarte(carte) {
  if (!carte) return { id: 'inconnu', libelle: '', tone: 'blue', finale: true }
  const base = etatDeBase(carte)
  // [US-272 / CA3] Traitée dans l'autre fenêtre : « ✅ Confirmé depuis Telegram à 14:32 ».
  return base.finale && carte.etat_dit && carte.traite_canal === 'telegram' ? { ...base, libelle: carte.etat_dit } : base
}

function etatDeBase(carte) {
  switch (carte.etat) {
    case 'confirmee':
      return { id: 'confirmee', libelle: '✅ Confirmé', tone: 'brand', finale: true }
    case 'abandonnee':
      return { id: 'abandonnee', libelle: '❌ Abandonné', tone: 'red', finale: true }
    case 'perimee':
      return { id: 'perimee', libelle: '⌛ Expiré', tone: 'amber', finale: true }
    case 'remplacee':
      return { id: 'remplacee', libelle: 'Remplacé', tone: 'blue', finale: true }
    // [US-289] Une commande confirmée dont le service a refusé l'écriture : rien n'est écrit, elle ne se rejoue pas.
    case 'echouee':
      return { id: 'echouee', libelle: '⚠️ Non exécuté', tone: 'red', finale: true }
    default:
      if (carte.erreur) return { id: 'erreur', libelle: '⚠️ Non enregistré', tone: 'red', finale: false }
      return {
        id: 'en_attente',
        libelle: carte.confirmable ? 'À confirmer' : 'À confirmer dans Telegram',
        tone: carte.confirmable ? 'amber' : 'blue',
        finale: false,
      }
  }
}

/** Les trois boutons d'une carte à confirmer — [Confirmer] [Corriger] [Abandonner] (CA2). */
export function boutonsCarte(carte, occupe = false) {
  const etat = etatCarte(carte)
  if (etat.finale) return []
  return [
    { id: 'confirmer', libelle: 'Confirmer', kind: 'primary', actif: !occupe && Boolean(carte.confirmable) },
    // Corriger n'a de sens que pour un geste : on reprend la phrase, la nouvelle remplace la carte.
    ...(carte.phrase ? [{ id: 'corriger', libelle: 'Corriger', kind: 'ghost', actif: !occupe }] : []),
    { id: 'abandonner', libelle: 'Abandonner', kind: 'quiet', actif: !occupe },
  ]
}

/** La carte après l'issue d'une confirmation ou d'un abandon (`ResultatConfirmation.en_donnees`). */
export function carteApresIssue(carte, issue) {
  if (!issue?.carte) return carte
  return { ...carte, ...issue.carte, erreur: issue.erreur ?? null, enregistres: issue.enregistres ?? [] }
}

/** Une carte dont le serveur dit qu'elle n'attend plus (409/404) : fermée, avec la raison. */
export function carteFermee(carte, err) {
  // [US-272 / CA2] Le 409 porte l'état réel (`detail.etat`) : il prime sur la lecture du message.
  const ETATS_FINAUX = ['confirmee', 'abandonnee', 'remplacee', 'perimee']
  const etat = ETATS_FINAUX.includes(err?.etat) ? err.etat
    : /remplac/i.test(err?.message ?? '') ? 'remplacee'
    : /abandonn|laissé tomber/i.test(err?.message ?? '') ? 'abandonnee'
    : /confirm/i.test(err?.message ?? '') ? 'confirmee'
    : 'perimee'
  return { ...carte, etat, erreur: null, note: messageErreur(err) }
}

// ── CA3 : le fil de la conversation ─────────────────────────────────────────

let compteur = 0
const cle = (prefixe) => `${prefixe}-${++compteur}`

/**
 * Le fil à l'ouverture : d'abord ce que le compagnon a dit de lui-même (CA3), puis la conversation
 * récente, puis les cartes qui attendent. Les messages spontanés sont horodatés à l'heure locale du
 * serveur et les échanges en UTC : on ne les entrelace pas, on les range en deux blocs lisibles.
 */
export function filDepuisHistorique(historique) {
  const fil = (historique?.spontanes ?? []).map((m) => ({
    cle: `spontane-${m.id}`, role: 'spontane', texte: m.texte, ts: m.envoye_le, genre: m.genre, themes: m.themes ?? [],
  }))
  ;(historique?.echanges ?? []).forEach((e, i) => {
    fil.push({ cle: `echange-${i}-j`, role: 'jardinier', texte: e.jardinier, ts: e.ts })
    fil.push({ cle: `echange-${i}-c`, role: 'compagnon', texte: e.compagnon, ts: e.ts, cartes: [], resume: true })
  })
  const cartes = historique?.cartes ?? []
  if (cartes.length) {
    fil.push({ cle: cle('cartes'), role: 'compagnon', texte: 'Ce qui attend votre réponse :', cartes, vers: 'geste' })
  }
  // [US-272 / CA9] Sans compagnon de terrain activé : l'invitation, une seule fois (le serveur en décide).
  if (historique?.invitation_telegram) {
    fil.push({ cle: 'invitation-telegram', role: 'spontane', texte: historique.invitation_telegram, genre: 'invitation' })
  }
  return fil
}

/**
 * La clé de la bulle du jardinier, choisie AVANT l'envoi : c'est elle qui permet, au retour de la
 * réponse (ou de l'erreur), de savoir que la phrase est déjà à l'écran et de ne pas la remettre.
 */
export const cleDePhrase = () => cle('j')

/**
 * La phrase du jardinier s'affiche dès l'envoi, pas au retour de la réponse : pendant que « Gaston
 * réfléchit », elle reste lisible au lieu de disparaître avec la saisie vidée.
 */
export const ajouterPhrase = (fil, phrase, cleJ = cle('j')) => [...fil, { cle: cleJ, role: 'jardinier', texte: phrase }]

/** La bulle du jardinier à ajouter : aucune si elle est déjà dans le fil (`ajouterPhrase`), sinon la sienne. */
const bulleAbsente = (fil, phrase, cleJ) => (
  cleJ != null && fil.some((e) => e.cle === cleJ)
    ? []
    : [{ cle: cleJ ?? cle('j'), role: 'jardinier', texte: phrase }]
)

/**
 * Ajoute l'échange qui vient d'avoir lieu : la phrase du jardinier (si elle n'est pas déjà affichée,
 * voir `ajouterPhrase`), puis la réponse du compagnon.
 */
export function ajouterEchange(fil, phrase, reponse, cleJ = null) {
  // [US-289] « Vas-y » dit dans le panneau : la carte déjà affichée change d'état, elle n'est pas dupliquée.
  if (reponse.vers === 'decision' && reponse.propositions?.length) {
    fil = reponse.propositions.reduce(remplacerCarte, fil)
    reponse = { ...reponse, propositions: [] }
  }
  return [
    ...fil,
    ...bulleAbsente(fil, phrase, cleJ),
    {
      cle: cle('c'), role: 'compagnon', texte: reponse.texte, vers: reponse.vers,
      cartes: reponse.propositions ?? [], avertissements: reponse.avertissements ?? [],
      routageLogId: reponse.routage_log_id ?? null, etage: reponse.etage ?? null,
      // [US-273] La phrase dite, pour « Approfondir » sous une réponse ; les sources d'une analyse.
      phrase,
      ...(reponse.vers === 'analyse' ? { sources: reponse.sources ?? [], borne: reponse.borne ?? null } : {}),
    },
  ]
}

/** Ajoute une erreur affichée dans le fil, en clair (CA4). */
export function ajouterErreur(fil, err, phrase = null, cleJ = null) {
  const suite = phrase ? bulleAbsente(fil, phrase, cleJ) : []
  return [...fil, ...suite, { cle: cle('e'), role: 'erreur', texte: messageErreur(err) }]
}

/** Remplace la carte du même identifiant partout dans le fil. */
export function remplacerCarte(fil, carte) {
  return fil.map((entree) => (
    entree.cartes?.some((c) => c.id === carte.id)
      ? { ...entree, cartes: entree.cartes.map((c) => (c.id === carte.id ? carte : c)) }
      : entree
  ))
}

/** Les cartes qui attendent encore (toutes entrées confondues). */
export const cartesEnAttente = (fil) =>
  fil.flatMap((e) => e.cartes ?? []).filter((c) => !etatCarte(c).finale)

/** Quand une réponse propose une nouvelle carte, les anciennes cartes d'attente deviennent « remplacées » côté écran. */
export function remplacerLesAnciennes(fil, nouvelles) {
  if (!nouvelles?.length) return fil
  const nouveaux = new Set(nouvelles.map((c) => c.id))
  return fil.map((entree) => (entree.cartes
    ? {
      ...entree,
      cartes: entree.cartes.map((c) => (
        nouveaux.has(c.id) || etatCarte(c).finale || c.nature !== nouvelles[0].nature
          ? c
          : { ...c, etat: 'remplacee' }
      )),
    }
    : entree))
}

// ── Saisie ──────────────────────────────────────────────────────────────────

export const LONGUEUR_MAX = 1000

export const peutEnvoyer = (texte, occupe) => !occupe && texte.trim().length > 0 && texte.length <= LONGUEUR_MAX

// ── [US-273] « Approfondir » : une analyse en lecture seule ─────────────────

/** Le mode demandé à l'API pour une analyse : un geste ponctuel, pas un mode du panneau. */
export const MODE_ANALYSE = 'analyse'

/** L'attente d'une analyse est plus longue qu'une réponse : plusieurs lectures de suite. */
export const TEXTE_ANALYSE_EN_COURS = 'Gaston regarde votre potager en détail…'

/** Le bouton de la saisie : la même règle qu'« Envoyer ». */
export const peutApprofondir = peutEnvoyer

/**
 * « Approfondir » sous une réponse : seulement après une réponse à une question (jamais sous un
 * geste, une commande ou une analyse déjà faite), et seulement si la phrase dite est connue.
 */
export const peutApprofondirEntree = (entree) => (
  entree?.role === 'compagnon' && entree.vers === 'question' && Boolean(entree.phrase?.trim())
)

/** L'analyse a été coupée par une borne : l'écran le dit au-dessus de la synthèse. */
export const analyseBornee = (entree) => entree?.vers === 'analyse' && Boolean(entree.borne)

/** « Corriger » : la phrase d'origine revient dans la zone de saisie, pour être refaite. */
export const texteACorriger = (carte) => carte?.phrase ?? ''

/** Un geste enregistré : l'écran courant doit se relire (le journal, le plan, les stocks). */
// [US-289] Une commande ou un plan exécuté dans la PWA n'écrit pas dans le carnet (`enregistres` vide) mais
// change quand même les données (parcelle créée ou modifiée) : les écrans doivent se relire.
export const aEnregistre = (issue) => Boolean(issue && !issue.erreur && (
  (issue.enregistres?.length ?? 0) > 0
  || (issue.carte?.nature !== 'geste' && issue.carte?.etat === 'confirmee')
))

// ── La maquette « Compagnon.html » : Gaston, trois états ────────────────────

export const GASTON = { nom: 'Gaston', espece: 'la carotte' }

/** Les trois états de la maquette : replié sur le bord droit, présent en bas à droite, chat ouvert. */
export const ETATS = ['replie', 'present', 'chat']
export const ETAT_PAR_DEFAUT = 'present'

/**
 * Les passages d'un état à l'autre : on ouvre depuis « présent » (l'avatar), on referme vers
 * « présent », on replie depuis « présent », on déplie depuis « replié » (le chevron).
 */
export function etatSuivant(etat, action) {
  switch (action) {
    case 'ouvrir': return 'chat'
    case 'fermer': return etat === 'chat' ? 'present' : etat
    case 'replier': return etat === 'present' ? 'replie' : etat
    case 'deplier': return etat === 'replie' ? 'present' : etat
    default: return etat
  }
}

export const CLE_ETAT = 'potager_compagnon_etat'

/** L'état retenu d'une visite à l'autre : replié ou présent, jamais « chat » (recharger ne rouvre pas le chat). */
export function lireEtat(stockage) {
  try {
    const e = stockage?.getItem(CLE_ETAT)
    return e === 'replie' || e === 'present' ? e : ETAT_PAR_DEFAUT
  } catch {
    return ETAT_PAR_DEFAUT
  }
}

/** [US-292 / CA10] Le lien rendu par un assistant IA connecté (`/?compagnon=ouvrir`) ouvre le
 *  panneau, où la carte à confirmer attend ; sinon l'état retenu d'une visite à l'autre. */
export const PARAM_OUVRIR = 'compagnon'

export function etatInitial(stockage, recherche) {
  try {
    if (new URLSearchParams(recherche || '').get(PARAM_OUVRIR) === 'ouvrir') return 'chat'
  } catch { /* adresse illisible : l'état retenu */ }
  return lireEtat(stockage)
}

export function ecrireEtat(stockage, etat) {
  if (etat !== 'replie' && etat !== 'present') return
  try { stockage?.setItem(CLE_ETAT, etat) } catch { /* navigation privée : on n'en retient rien */ }
}

export const BULLE_PRESENT = 'Besoin d’un coup de main ?'

export const ACCUEIL = {
  normal: `Bonjour 👋 Je suis ${GASTON.nom}, ${GASTON.espece} du potager. Dites-moi ce que vous avez fait, ou posez-moi une question sur vos semis, vos godets ou la météo.`,
  support: `Mode Support : je réponds avec l’aide de l’application, et je n’écris rien dans votre carnet. Que cherchez-vous ?`,
}

/** Les raccourcis proposés sous l'accueil (maquette : quatre, un emoji devant). */
export const SUGGESTIONS = {
  normal: ['🌱 Que semer cette semaine ?', '🪴 Où en sont mes godets ?', '🍅 Quand repiquer mes tomates ?', '🌦️ Gel prévu ce week-end ?'],
  support: ['📖 Comment confirmer un geste ?', '🔒 Où effacer mon carnet ?', '💬 Que sait faire le compagnon ?'],
}

/** La question envoyée par un raccourci : l'emoji d'illustration n'en fait pas partie. */
export const questionDeSuggestion = (s) => s.replace(/^\S+\s/, '')

export const PLACEHOLDER = {
  normal: 'Un geste à noter, une question…',
  support: 'Une question sur l’application…',
}

/** « Recommencer » : l'écran repart d'un accueil ; seules les cartes qui attendent encore restent à l'écran. */
export function filApresRecommencer(historique) {
  const cartes = historique?.cartes ?? []
  return cartes.length
    ? [{ cle: cle('cartes'), role: 'compagnon', texte: 'Ce qui attend votre réponse :', cartes, vers: 'geste' }]
    : []
}

// ── [US-272] Deux fenêtres : l'état réel des cartes, et ce qui n'a pas été lu ─

/** CA5 : le panneau ouvert se relit toutes les 15 s ; fermé, la pastille toutes les minutes. Sans WebSocket. */
export const INTERVALLE_OUVERT_MS = 15000
export const INTERVALLE_FERME_MS = 60000

const cartesDu = (fil) => fil.flatMap((e) => e.cartes ?? [])

/**
 * CA5 : le fil après une relecture de `GET /compagnon/etat`. Une carte déjà montrée prend l'état
 * que le serveur lui donne quand il a CHANGÉ (confirmée dans Telegram, remplacée…) ; une carte
 * nouvelle qui attend (proposée dans Telegram, ou dans un autre onglet) s'ajoute ; un message
 * spontané nouveau s'ajoute. Les échanges ne sont pas relus : le fil local les a déjà.
 */
export function fusionnerEtat(fil, etat) {
  if (!etat) return fil
  const montrees = new Map(cartesDu(fil).map((c) => [c.id, c]))
  let suite = fil
  for (const carte of [...(etat.traitees ?? []), ...(etat.cartes ?? [])]) {
    const ancienne = montrees.get(carte.id)
    if (ancienne && ancienne.etat !== carte.etat) {
      suite = remplacerCarte(suite, {
        ...ancienne, ...carte, erreur: null,
        avertissements: carte.avertissements?.length ? carte.avertissements : (ancienne.avertissements ?? []),
      })
    }
  }
  const nouvelles = (etat.cartes ?? []).filter((c) => !montrees.has(c.id) && !etatCarte(c).finale)
  const dejaLus = new Set(suite.map((e) => e.cle))
  const spontanes = (etat.spontanes ?? [])
    .filter((m) => !dejaLus.has(`spontane-${m.id}`))
    .map((m) => ({ cle: `spontane-${m.id}`, role: 'spontane', texte: m.texte, ts: m.envoye_le, genre: m.genre, themes: m.themes ?? [] }))
  if (spontanes.length) suite = [...suite, ...spontanes]
  if (nouvelles.length) {
    suite = [...suite, { cle: cle('cartes'), role: 'compagnon', texte: 'Ce qui attend votre réponse :', cartes: nouvelles, vers: 'geste' }]
  }
  return suite
}

export const CLE_VU = 'potager_compagnon_vu'

/** Le plus grand identifiant vu, par sorte : les identifiants de la base ne font que croître. */
export function vuDepuisEtat(etat, avant = null) {
  const max = (liste, depart) => (liste ?? []).reduce((m, x) => Math.max(m, Number(x.id) || 0), depart)
  return {
    spontane: max(etat?.spontanes, avant?.spontane ?? 0),
    carte: max([...(etat?.cartes ?? []), ...(etat?.traitees ?? [])], avant?.carte ?? 0),
  }
}

/** CA5 : la pastille — les messages spontanés et les cartes en attente arrivés depuis la dernière ouverture. */
export function compterNonLus(etat, vu) {
  if (!etat || !vu) return 0
  const spontanes = (etat.spontanes ?? []).filter((m) => Number(m.id) > (vu.spontane ?? 0)).length
  const cartes = (etat.cartes ?? []).filter((c) => Number(c.id) > (vu.carte ?? 0) && !etatCarte(c).finale).length
  return spontanes + cartes
}

/** Le « vu » retenu sur cet appareil (une commodité, pas un suivi de présence : D12). */
export function lireVu(stockage) {
  try {
    const brut = stockage?.getItem(CLE_VU)
    const vu = brut ? JSON.parse(brut) : null
    return vu && typeof vu === 'object' ? vu : null
  } catch {
    return null
  }
}

export function ecrireVu(stockage, vu) {
  try { stockage?.setItem(CLE_VU, JSON.stringify(vu)) } catch { /* navigation privée : la pastille repart de zéro */ }
}

/** Ce que la pastille affiche : rien à zéro, « 9+ » au-delà de neuf. */
export const libellePastille = (n) => (n > 9 ? '9+' : n > 0 ? String(n) : '')
