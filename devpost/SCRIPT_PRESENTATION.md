# Script de présentation — CorroborIA, démo sur le site en ligne (≈ 4 minutes)

> Texte à lire en **romain**. Les actions à l'écran sont entre **[crochets]**. Les durées sont indicatives.
> Version courte (3 min) : sauter les passages marqués *(optionnel)*.

**Site :** https://louisbarbonet.github.io/CorroborAI/ · **Résultats dans le dépôt :** `rapport/RESULTATS.md`

---

## 0. Préparation (5 minutes avant, hors chrono)

1. Ouvrir le site dans Chrome, faire **Ctrl+F5**, zoom **110-125 %**.
2. En bas de page (« Intégrité des sources »), vérifier que la **version du site** correspond au dernier commit du dépôt.
3. Vider d'éventuelles corrections de test : touche **F12** → Console → `localStorage.clear()` → recharger la page.
4. Cliquer **« Relancer »** une fois et attendre la fin (≈ 1 à 2 min) : le badge en haut passe à
   **« Moteur Python exécuté dans le navigateur (Pyodide) »**. Le moteur reste chargé tant que l'onglet est ouvert :
   la correction expert et l'export seront ensuite quasi instantanés. **Ne plus recharger la page.**
5. Ouvrir puis fermer l'« Assistant IA » pour vérifier qu'il répond (cliquer une question d'exemple).
6. Plan B prêt dans un 2e onglet : `rapport/RESULTATS.md` sur GitHub (tableaux des résultats finaux).

---

## 1. Le problème — 0:00 → 0:30

**[Écran : page d'accueil du site en ligne, indicateurs visibles]**

Bonjour, je vous présente CorroborIA, accessible directement en ligne, sans installation.

Chez Loto-Québec, on compare déjà, champ par champ, les données du système RH et celles du système de gestion du
temps. Le problème, c'est que « différent » ne veut pas dire « erroné ». Un code traduit par une jointure, un libellé
concaténé, une date dans un autre format : ce sont des écarts normaux. Aujourd'hui, quelqu'un doit les valider à la main.

Notre objectif : que l'humain ne regarde plus que les vraies erreurs.

## 2. Le résultat — 0:30 → 1:00

**[Montrer les indicateurs]**

Sur les extractions fournies, CorroborIA analyse 551 constats. 361 sont conformes. 133 écarts sont justifiés
automatiquement. Il reste 57 anomalies : **13 erreurs nettes** à investiguer en priorité, puis, en bas de liste,
22 courriels et 22 libellés de rôle — j'y reviens.

**[Pointer la carte « Synthèse IA »]**

Gemini regroupe ces anomalies par cause racine, par ordre d'importance, avec une recommandation pour chacune :
affectation manquante, types de contrat mal dérivés, heures non transmises, libellés de site incohérents.

## 3. Comment ça marche — 1:00 → 1:30

**[Pointer la carte « Comment le verdict est décidé »]**

L'approche est hybride, en trois niveaux.
Un : on compare les valeurs après normalisation des formats.
Deux : on applique les règles métier, lues directement dans le fichier de mapping, avec les jointures sur les tables
Motif et Détail du poste. Ces deux niveaux sont entièrement déterministes.
Trois : seulement pour ce que les règles ne peuvent pas trancher, l'IA intervient.

**[Pointer le badge en haut « Moteur Python exécuté dans le navigateur »]** *(optionnel)*

Et ce que vous voyez tourne réellement : le moteur Python s'exécute ici, dans le navigateur ; seuls les cas ambigus,
anonymisés, partent vers Gemini, par un relais qui garde la clé secrète.

## 4. Les trois types de cas — 1:30 → 2:45

**[Barre de recherche : taper « 8142123 », cliquer la ligne onboardDate]**

Un cas **conforme** : la date d'embauche. Dans le système RH, c'est une date Excel ; dans le système Temps, un
horodatage ISO avec heure et fuseau. Une comparaison brute dirait « différent » ; après normalisation, c'est la même
date, le 1er septembre 1985. Niveau 1.

**[Échap, rechercher « 7603160 », ouvrir statusReasonCode]**

Un **écart justifié par une règle** : le code de statut passe de 807 à 170. Ce n'est pas une erreur : c'est la
jointure avec la table des motifs prévue par le mapping. On voit la règle, et la ligne de jointure utilisée comme preuve.

**[Échap, rechercher « 3712987 », ouvrir weeklyHoursOverride]** *(optionnel)*

Un **écart justifié par l'IA** : le système RH ne donne pas d'heures pour cet employé ; le système Temps applique les
40 heures du poste. Nos détecteurs reconnaissent une valeur par défaut légitime ; Gemini confirme. Les deux avis sont affichés.

**[Échap, rechercher « 1545850 », ouvrir contactEmail]** *(optionnel)*

Les courriels : Loto-Québec nous a précisé que le code est le matricule et qu'un préfixe d'environnement doit être
accepté. On l'accepte ; mais l'adresse utilise un autre identifiant que le matricule. Nous leur avons posé la question :
c'est une erreur d'anonymisation du jeu de test, mais ils souhaitent que ce cas reste détecté, car en production ce serait
une vraie erreur. Il est donc signalé, avec la priorité la plus basse et la cause expliquée. Même logique pour les
libellés de rôle, que Loto-Québec qualifie d'erreur : nos détecteurs montrent en plus que la substitution est systématique.

**[Échap, rechercher « 2762457 », ouvrir contractTypeCode]**

Et une **vraie anomalie** : l'employé est permanent, à temps plein, catégorie V : la règle donne « JWN ».
Le système Temps a reçu « WHX », qui correspond à un employé occasionnel. Le panneau explique la cause probable,
cite la règle et sa ligne dans le fichier Excel, et donne une priorité de 84 sur 100 calculée par un modèle scikit-learn.

## 5. L'IA qui aide vraiment — 2:45 → 3:30

**[Échap, vider la recherche, pointer l'encart jaune « Calibration »]**

Un exemple que nous trouvons parlant : le mapping dit de prendre la date « la plus ancienne » pour la date
d'affectation. Nous avons mesuré plusieurs lectures de cette règle contre les données : la lecture littérale ne correspond
à aucune ligne, zéro sur vingt-deux ; la règle transformée — le détail de poste le plus récent — les explique toutes,
vingt-deux sur vingt-deux. Loto-Québec nous l'a confirmé. Le moteur documente ce choix au lieu de produire de fausses alertes.

**[Rechercher « 2911996 », ouvrir weeklyHoursOverride → « Corriger le verdict » : « Écart justifié », portée « Tous les cas
du même motif », commentaire court → « Enregistrer la correction »]** *(optionnel — nécessite le moteur préchargé, étape 0.4)*

Quand un cas est ambigu, comme ces heures, c'est l'expert qui tranche. Ici, je le corrige pour tout le motif : le
moteur recalcule dans le navigateur, les six cas similaires basculent, les anomalies passent de 57 à 51, et la
correction devient une règle apprise qui réentraîne le modèle de priorité.

**[Bouton « Assistant IA » en bas à droite : cliquer une question d'exemple, puis taper une question libre,
ex. « Quelle affectation manque dans le Système B ? »]**

Enfin, un assistant répond aux questions sur les résultats, en citant ses sources : les repères sont cliquables
et ouvrent directement le constat. Les questions fréquentes ont une réponse instantanée ; les autres passent par Gemini.

## 6. Conclusion — 3:30 → 4:00

**[Cliquer « Exporter le rapport Excel »]**

Tout se termine par un rapport Excel, généré ici dans le navigateur : les anomalies, leur justification et les preuves.
Les résultats finaux sont aussi publiés directement dans notre dépôt GitHub, pour une évaluation sans exécuter le code.

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

### En cas de souci pendant la démo

- **Le moteur n'a pas été préchargé** : sauter la correction expert (elle prendrait 1 à 2 min) ; tout le reste fonctionne
  instantanément à partir de l'instantané.
- **Correction expert faite par erreur** : F12 → `localStorage.clear()` puis recharger (le moteur devra être rechargé).
- **Chat en erreur (quota du relais)** : utiliser les questions d'exemple, toujours disponibles.
- **Réseau indisponible** : montrer l'onglet `rapport/RESULTATS.md` ou les captures d'écran.
