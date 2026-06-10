**ID :** US-032
**Titre :** Enregistrer et afficher le prix unitaire des ventes de plants

**Story :**
En tant que jardinier
Je veux pouvoir indiquer le prix de vente par plant lors d'une vente de godet
Afin de suivre mes revenus de pépinière et visualiser les montants en euros dans le récapitulatif

**Critères d'acceptance :**
- [ ] CA1 : Le bot accepte naturellement le prix lors d'une vente ("vendu 5 tomates cerise à 1,50€")
- [ ] CA2 : Groq extrait le prix unitaire ou le montant total en plus de la quantité
- [ ] CA3 : Le prix est stocké dans un nouveau champ `prix_unitaire` (ou `commentaire` comme fallback temporaire) sur l'événement `vendu`
- [ ] CA4 : Le frontend pépinière affiche le montant total dans le bandeau récap (ex: "13 pieds vendus · 21,50 €")
- [ ] CA5 : Si aucun prix n'est saisi, le bandeau affiche uniquement le nombre de pieds (comportement actuel)
- [ ] CA6 : Le prix est visible dans la timeline détail d'une culture en pépinière

**Notes fonctionnelles :**
- Zone fonctionnelle : pépinière + enregistrement bot
- Migration BDD requise : oui — ajout colonne `prix_unitaire NUMERIC(6,2)` sur `evenements` (nullable, uniquement valorisée pour `type_action = 'vendu'`)
- Dépendances : US-026 (pépinière frontend), implémentation partielle de la vente déjà en place (US-031 affiche les pieds vendus sans montant)
- Option alternative légère : stocker `{prix: 1.5}` dans le champ `commentaire` JSON — évite la migration mais moins propre

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le jardinier a vendu 5 plants de tomate cerise
When il dicte "vendu 5 tomates cerise à 1 euro 50"
Then l'événement vendu est enregistré avec quantite=5 et prix_unitaire=1.50
And le bandeau pépinière affiche "5 pieds vendus · 7,50 €"
```

**Labels GitHub :** `us`, `sprint-backlog`, `pépinière`, `bot`
