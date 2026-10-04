# Script de présentation — CorroborIA (≈ 4 minutes)

> Texte à lire en **romain**. Les actions à l'écran sont entre **[crochets]**. Les durées sont indicatives.
> Version courte (3 min) : sauter les passages marqués *(optionnel)*.

---

## 1. Le problème — 0:00 → 0:30

**[Écran : page d'accueil du site, indicateurs visibles]**

Bonjour, je vous présente CorroborIA.

Chez Loto-Québec, on compare déjà, champ par champ, les données du système RH et celles du système de gestion du
temps. Le problème, c'est que « différent » ne veut pas dire « erroné ». Un code traduit par une jointure, un libellé
concaténé, une date dans un autre format : ce sont des écarts normaux. Aujourd'hui, quelqu'un doit les valider à la main.

Notre objectif : que l'humain ne regarde plus que les vraies erreurs.

## 2. Le résultat — 0:30 → 1:00

**[Montrer les 4 indicateurs]**

Sur les extractions fournies, CorroborIA analyse 551 constats en quelques secondes.
361 sont conformes. 133 écarts sont justifiés automatiquement. Il reste 57 anomalies : **13 erreurs nettes** à
investiguer en priorité, puis, en bas de liste, 22 courriels et 22 libellés de rôle — j'y reviens.

**[Pointer la carte « Synthèse IA »]**

Ici, Gemini regroupe ces anomalies par cause racine, par ordre d'importance, avec une recommandation pour chacune :
affectation manquante, types de contrat mal dérivés, heures non transmises, libellés de site incohérents.

## 3. Comment ça marche — 1:00 → 1:30

**[Pointer la carte « Comment le verdict est décidé »]**

L'approche est hybride, en trois niveaux.
Un : on compare les valeurs après normalisation des formats.
Deux : on applique les règles métier, lues directement dans le fichier de mapping, avec les jointures sur les tables
Motif et Détail du poste. Ces deux niveaux sont entièrement déterministes.
Trois : seulement pour ce que les règles ne peuvent pas trancher, l'IA intervient.

## 4. Les trois types de cas — 1:30 → 2:45

**[Recherche « 8142123 », ouvrir onboardDate]**

Un cas **conforme** : la date d'embauche. Dans le système RH, c'est une date Excel ; dans le système Temps, un
horodatage ISO avec heure et fuseau. Une comparaison brute dirait « différent » ; après normalisation, c'est la même
date, le 1er septembre 1985. Niveau 1.

**[Fermer, recherche « 7603160 », ouvrir statusReasonCode]**

Un **écart justifié par une règle** : le code de statut passe de 807 à 170. Ce n'est pas une erreur : c'est la
jointure avec la table des motifs prévue par le mapping. On voit la règle, et la ligne de jointure utilisée comme preuve.

**[Fermer, ouvrir 3712987 · weeklyHoursOverride]** *(optionnel)*

Un **écart justifié par l'IA** : le système RH ne donne pas d'heures pour cet employé ; le système Temps applique les
40 heures du poste. Nos détecteurs reconnaissent une valeur par défaut légitime ; Gemini confirme. Les deux avis sont affichés.

**[Fermer, ouvrir 1545850 · contactEmail]** *(optionnel)*

Les courriels : Loto-Québec nous a précisé que le code est le matricule et qu'un préfixe d'environnement doit être
accepté. On l'accepte ; mais l'adresse utilise un autre identifiant que le matricule. Nous leur avons posé la question :
c'est une erreur d'anonymisation du jeu de test, mais ils souhaitent que ce cas reste détecté, car en production ce serait
une vraie erreur. Il est donc signalé, avec la priorité la plus basse et la cause expliquée. Même logique pour les
libellés de rôle, que Loto-Québec qualifie d'erreur : nos détecteurs montrent en plus que la substitution est systématique.

**[Fermer, ouvrir 2762457 · contractTypeCode]**

Et une **vraie anomalie** : l'employé est permanent, à temps plein, catégorie V : la règle donne « JWN ».
Le système Temps a reçu « WHX », qui correspond à un employé occasionnel. Le panneau explique la cause probable,
cite la règle et sa ligne dans le fichier Excel, et donne une priorité de 84 sur 100 calculée par un modèle scikit-learn.

## 5. L'IA qui aide vraiment — 2:45 → 3:30

**[Pointer l'encart jaune « Calibration »]**

Un exemple que nous trouvons parlant : le mapping dit de prendre la date « la plus ancienne » pour la date
d'affectation. Nous avons mesuré plusieurs lectures de cette règle contre les données : la lecture littérale ne correspond
à aucune ligne, zéro sur vingt-deux ; la règle transformée — le détail de poste le plus récent — les explique toutes,
vingt-deux sur vingt-deux. Loto-Québec nous l'a confirmé. Le moteur documente ce choix au lieu de produire de fausses alertes.

**[Ouvrir 2911996 · weeklyHoursOverride, corriger en « Écart justifié », portée « motif », Enregistrer]** *(optionnel)*

Quand un cas est ambigu, comme ces heures, c'est l'expert qui tranche. Ici, je le corrige pour tout le motif :
les six cas similaires basculent, la correction devient une règle apprise et réentraîne le modèle de priorité.

**[Ouvrir l'Assistant IA, cliquer une question d'exemple, puis poser une question libre]**

Enfin, un assistant répond aux questions sur les résultats, en citant ses sources : les repères sont cliquables
et ouvrent directement le constat.

## 6. Conclusion — 3:30 → 4:00

**[Cliquer « Exporter le rapport Excel »]**

Tout se termine par un rapport Excel exportable : les anomalies, leur justification et les preuves.

En résumé : des règles pour l'exactitude, de l'IA pour l'ambiguïté et l'explication, un expert toujours dans la
boucle, et des fichiers sources jamais modifiés. Le tout est en ligne, sans installation, et la clé du LLM reste
protégée côté serveur.

Merci ! Je réponds volontiers à vos questions.

---

### Repères de timing

| Section | Fin à |
|---|---|
| Problème | 0:30 |
| Résultat | 1:00 |
| Fonctionnement | 1:30 |
| 3 types de cas | 2:45 |
| IA utile (calibration, expert, chat) | 3:30 |
| Conclusion | 4:00 |

### Si le temps manque

Garder dans l'ordre : résultat (2) → conforme / justifié règle / anomalie (4) → calibration (5) → conclusion (6).
