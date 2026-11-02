// [US-265] Écran « Mon compagnon » — le carnet du compagnon.
//
// Ce que le compagnon a retenu de ce que le jardinier lui a dit (« j'arrose le
// soir »), le niveau qu'il lui prête et ses objectifs de saison. Le jardinier voit,
// corrige, oublie un point ou tout oublier (RGPD : accès et effacement, CA3, CA6).
// Rien ne s'ajoute ici : un fait entre au carnet par la conversation, sur
// confirmation (R9) ; l'écran ne fait que montrer et corriger.
//
// Rendu en `Modal` comme les autres destinations du menu Compte. Le contenu vit
// dans un conteneur (`@container/compagnon`) : la mise en page suit la largeur de
// la fenêtre, pas celle de l'écran (frontend/CLAUDE.md).
import { useState, useEffect, useCallback } from 'react'
import { NotebookPen, Pencil, Trash2, Check, X, Target, Sprout } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Card, SectionLabel, Btn, InfoBanner } from './ui'

const LIBELLE_NIVEAU = { debutant: 'Débutant', confirme: 'Confirmé' }

export default function ModalMonCompagnon({ onClose }) {
  const [carnet, setCarnet] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [enEdition, setEnEdition] = useState(null) // { id, texte }
  const [objectifs, setObjectifs] = useState([''])
  const [confirmerTout, setConfirmerTout] = useState(false)
  const [occupe, setOccupe] = useState(false)

  const appliquer = useCallback((c) => {
    setCarnet(c)
    setObjectifs(c.objectifs.length ? c.objectifs : [''])
  }, [])

  useEffect(() => {
    api.carnet().then(appliquer).catch((e) => setErreur(e.message))
  }, [appliquer])

  async function agir(action) {
    if (occupe) return
    setOccupe(true)
    setErreur(null)
    try {
      await action()
    } catch (e) {
      setErreur(e.message)
    } finally {
      setOccupe(false)
    }
  }

  const recharger = () => api.carnet().then(appliquer)
  const limites = carnet?.limites ?? { fait: 200, faits: 30, objectifs: 3, objectif: 80 }

  const enregistrerFait = () => agir(async () => {
    appliquer(await api.modifierFaitCarnet(enEdition.id, enEdition.texte))
    setEnEdition(null)
  })
  const oublier = (id) => agir(async () => { await api.oublierFaitCarnet(id); await recharger() })
  const toutOublier = () => agir(async () => {
    await api.toutOublierCarnet()
    setConfirmerTout(false)
    await recharger()
  })
  const regler = (niveau) => agir(async () => appliquer(await api.reglerNiveauCarnet(niveau)))
  const enregistrerObjectifs = () => agir(async () => {
    appliquer(await api.reglerObjectifsCarnet(objectifs.map((o) => o.trim()).filter(Boolean)))
  })

  const vide = carnet && !carnet.faits.length && !carnet.objectifs.length && !carnet.niveau

  return (
    <Modal
      title="Mon compagnon"
      icon={NotebookPen}
      sub="Ce qu'il retient de vous"
      onClose={onClose}
      width={560}
      disposition="adaptative"
      bodyClassName="p-4 overflow-y-auto min-h-0 flex-1 @container/compagnon"
      foot="Rien n'est retenu sans votre accord. Vous pouvez tout corriger ou effacer à tout moment."
    >
      {erreur && <div role="alert" className="mb-3 text-[13px] text-red">{erreur}</div>}
      {!carnet && !erreur && <div className="text-[13px] text-txt3">Chargement…</div>}

      {carnet && (
        <div className="flex flex-col gap-4">
          {vide && (
            <InfoBanner
              title="Le carnet est vide"
              body="Dites à votre compagnon une habitude, par exemple « j'arrose toujours le soir » : il vous proposera de la retenir."
            />
          )}

          <section>
            <SectionLabel>Niveau</SectionLabel>
            <Card pad="p-3">
              {carnet.niveau ? (
                <div className="flex flex-col gap-2 @[420px]/compagnon:flex-row @[420px]/compagnon:items-center @[420px]/compagnon:justify-between">
                  <span className="text-[14px] text-txt">{LIBELLE_NIVEAU[carnet.niveau]}</span>
                  <Btn small kind="quiet" onClick={() => regler(null)} disabled={occupe}>Revoir mon niveau</Btn>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {carnet.niveau_propose && (
                    <p className="text-[13.5px] text-txt2">
                      D'après votre activité, je vous vois plutôt{' '}
                      <strong>{LIBELLE_NIVEAU[carnet.niveau_propose].toLowerCase()}</strong>. C'est juste ?
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(LIBELLE_NIVEAU).map(([cle, libelle]) => (
                      <Btn key={cle} small kind={cle === carnet.niveau_propose ? 'primary' : 'ghost'}
                        onClick={() => regler(cle)} disabled={occupe}>
                        {libelle}
                      </Btn>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </section>

          <section>
            <SectionLabel>Objectifs de saison</SectionLabel>
            <Card pad="p-3">
              <div className="flex flex-col gap-2">
                {objectifs.map((objectif, i) => (
                  <label key={i} className="flex items-center gap-2">
                    <Target size={15} className="text-brand shrink-0" aria-hidden="true" />
                    <input
                      value={objectif}
                      maxLength={limites.objectif}
                      onChange={(e) => setObjectifs(objectifs.map((o, j) => (j === i ? e.target.value : o)))}
                      placeholder="Ex. autonomie en tomates"
                      aria-label={`Objectif ${i + 1}`}
                      className="flex-1 min-w-0 text-[14px] bg-surface border border-border rounded-[9px] px-3 py-2 text-txt"
                    />
                  </label>
                ))}
                <div className="flex flex-wrap gap-2">
                  {objectifs.length < limites.objectifs && (
                    <Btn small kind="quiet" onClick={() => setObjectifs([...objectifs, ''])}>Ajouter un objectif</Btn>
                  )}
                  <Btn small kind="soft" onClick={enregistrerObjectifs} disabled={occupe}>Enregistrer</Btn>
                </div>
              </div>
            </Card>
          </section>

          <section>
            <SectionLabel>Ce que j'ai retenu ({carnet.faits.length}/{limites.faits})</SectionLabel>
            {carnet.faits.length === 0 ? (
              <p className="text-[13px] text-txt3">Rien pour l'instant.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {carnet.faits.map((fait) => (
                  <li key={fait.id}>
                    <Card pad="p-3">
                      {enEdition?.id === fait.id ? (
                        <div className="flex flex-col gap-2">
                          <textarea
                            value={enEdition.texte}
                            maxLength={limites.fait}
                            rows={2}
                            onChange={(e) => setEnEdition({ id: fait.id, texte: e.target.value })}
                            aria-label="Modifier ce point"
                            className="w-full text-[14px] bg-surface border border-border rounded-[9px] px-3 py-2 text-txt"
                          />
                          <div className="flex gap-2">
                            <Btn small kind="primary" icon={Check} onClick={enregistrerFait} disabled={occupe}>Enregistrer</Btn>
                            <Btn small kind="quiet" icon={X} onClick={() => setEnEdition(null)}>Annuler</Btn>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-2 @[420px]/compagnon:flex-row @[420px]/compagnon:items-start @[420px]/compagnon:justify-between">
                          <div className="min-w-0">
                            <p className="text-[14px] text-txt break-words">{fait.texte}</p>
                            {fait.cree_le && (
                              <p className="text-[11.5px] text-txt3 mt-0.5">
                                Retenu le {new Date(fait.cree_le).toLocaleDateString('fr-FR')}
                                {fait.origine ? ` · « ${fait.origine} »` : ''}
                              </p>
                            )}
                          </div>
                          <div className="flex gap-1.5 shrink-0">
                            <Btn small kind="ghost" icon={Pencil} aria-label="Modifier ce point"
                              onClick={() => setEnEdition({ id: fait.id, texte: fait.texte })} disabled={occupe}>
                              Modifier
                            </Btn>
                            <Btn small kind="ghost" icon={Trash2} aria-label="Oublier ce point"
                              onClick={() => oublier(fait.id)} disabled={occupe}>
                              Oublier
                            </Btn>
                          </div>
                        </div>
                      )}
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {!vide && (
            <section>
              {confirmerTout ? (
                <Card pad="p-3">
                  <p className="text-[13.5px] text-txt2 mb-2">
                    Effacer tous les faits, les objectifs et le niveau ? Cela ne se défait pas.
                  </p>
                  <div className="flex gap-2">
                    <Btn small kind="primary" icon={Trash2} onClick={toutOublier} disabled={occupe}>Oui, tout oublier</Btn>
                    <Btn small kind="quiet" onClick={() => setConfirmerTout(false)}>Non</Btn>
                  </div>
                </Card>
              ) : (
                <Btn small kind="ghost" icon={Sprout} onClick={() => setConfirmerTout(true)}>Tout oublier</Btn>
              )}
            </section>
          )}
        </div>
      )}
    </Modal>
  )
}
