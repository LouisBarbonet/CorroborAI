# Devpost — CorroborAI (The Optimizers) · version finale

---

## Project name

CorroborAI

## Elevator pitch (≤ 200 caractères)

Fini la validation manuelle : CorroborIA isole les vraies erreurs entre RH et Temps, justifie chaque verdict par une règle ou l'IA, et exporte un rapport prêt à investiguer.

---

## About the project

## Inspiration

Chez Loto-Québec, une corroboration compare déjà, champ par champ, l'extraction du système maître RH (Système A) et celle du système de gestion du temps (Système B). Mais **« différent » ne veut pas dire « erroné »** : un code de statut traduit par une jointure, un libellé concaténé ou une date au format Excel sont des écarts *légitimes*, qu'il faut aujourd'hui valider à la main — avec une bonne connaissance des systèmes et des interprétations variables.

Notre objectif : concentrer l'attention humaine sur les **vraies erreurs**, avec des verdicts compréhensibles, traçables et reproductibles.

## What it does

CorroborIA compare les deux extractions selon le fichier de mapping et classe chacun des **551 constats** :

- ✅ **Conforme** (361) : même valeur après normalisation (dates sérielles Excel ↔ ISO, vides, nombres, encodage).
- 🟡 **Écart justifié** (133) : différence expliquée par une règle métier (jointure Motif → code Remphor, type de contrat, P/A/S → booléens, concaténations, règle transformée de la date d'affectation), par un défaut d'encodage ou par l'IA (heures par défaut du poste).
- 🔴 **Anomalie** (57), **priorisée** et expliquée :
  - **13 erreurs nettes** : 1 affectation temporaire absente du Système B, 4 types de contrat mal dérivés, 2 libellés d'emplacement incohérents avec leur code, 6 heures non transmises (marquées « à valider » par un expert) ;
  - **44 cas de faible priorité**, confirmés comme erreurs par Loto-Québec : 22 courriels construits avec un identifiant autre que le matricule (préfixe d'environnement accepté ; erreur d'anonymisation du jeu de test, conservée dans la détection à leur demande) et 22 libellés de rôle dont le préfixe ne correspond pas au code emploi (substitution systématique).

Chaque verdict montre la valeur source, la valeur attendue selon la règle et la valeur reçue, le **niveau de décision** (comparaison, règle métier, IA ou expert), le texte de la règle avec sa ligne dans `Mapping.xlsx`, les preuves (lignes de jointure, historique du poste), une confiance, une priorité et la cause probable.

Les résultats se consultent dans une interface web (en ligne, sans installation) et s'exportent en **rapport Excel de 10 onglets** ou CSV ; le rapport généré est aussi publié dans le dépôt. Les cas ambigus sont arbitrés par **Google Gemini**, qui rédige aussi la synthèse par cause racine, et un **assistant IA** répond aux questions du jury en citant ses sources.

## How we built it

**Un pipeline hybride à 3 niveaux** — les règles tranchent tout ce qui est déterministe, l'IA intervient là où elles s'arrêtent :

1. **Comparaison brute normalisée** : dates, vides, booléens, nombres, réparation d'encodage (`Absence complÃ¨te` → `Absence complète`).
2. **Règles métier déterministes** lues directement dans `Mapping.xlsx` (table des types de contrat, table de situation d'emploi), avec les jointures *Motif* et *Détail du poste*.
3. **IA** :
   - **Détecteurs de motifs** raisonnant sur tout le jeu : valeur par défaut des heures, structure des courriels, substitution systématique des libellés de rôle (correspondance code ↔ libellé biunivoque) — ils diagnostiquent la cause probable de chaque anomalie ;
   - **scikit-learn** : une régression logistique, réentraînée à chaque exécution sur les verdicts déterministes et les corrections d'experts (poids ×5), donne une seconde opinion $P(\text{anomalie})$ ; un IsolationForest mesure l'atypicité $r$ ;
   - **Google Gemini** (`gemini-flash-lite-latest`, repli `gemini-flash-latest`) : arbitre les cas ambigus par lots, en JSON validé (verdict, confiance, justification), et rédige la synthèse par cause racine. S'il contredit l'analyse locale, le cas est marqué « à valider ».

La **priorité** combine criticité métier du champ $c$, confiance $k$, probabilité ML $p$, atypicité $r$ et nombre d'anomalies $n$ du même employé :

$$
\text{priorité} = 100 \times \left(0{,}50\,c + 0{,}25\,k + 0{,}10\,p + 0{,}10\,r + 0{,}05\,\min\!\left(\tfrac{n}{4},\,1\right)\right)
$$

**Calibration de règle** : quand une règle du mapping est ambiguë, le moteur confronte ses interprétations aux données et documente son choix.

**Boucle expert** : un expert corrige un verdict pour un cas ou pour *tous les cas du même motif* ; la correction devient une règle apprise traçable et réentraîne le modèle de priorisation.

**Version en ligne** : site statique sur GitHub Pages (Vite) qui affiche instantanément un instantané des résultats ; le **vrai moteur Python tourne dans le navigateur** grâce à Pyodide (pandas, scikit-learn) pour le recalcul, le téléversement de fichiers, les corrections et les exports. Les appels LLM passent par un **relais Cloudflare Worker** : la clé Gemini y est un secret, le relais construit lui-même les consignes et n'accepte que des données structurées, avec CORS, validation stricte, cache KV, limite par IP et plafond quotidien. Chaîne de repli automatique (Claude, Ollama, Groq, Gemini, OpenRouter, gabarit local) : tout fonctionne aussi **sans clé, hors ligne**.

**Qualité** : fichiers sources en lecture seule (contrôle sha256), 52 tests automatisés (33 Python, 19 JavaScript — dont un test qui vérifie que chaque repère cité par le chat existe), CLI, API FastAPI, notebook Jupyter, rapport publié.

## Challenges we ran into

- **Une règle contredite par les données.** Le mapping dit « date la *plus ancienne* » pour la date d'affectation. Nous avons mesuré trois lectures : littérale **0/22**, via l'unité administrative **19/22**, règle transformée (détail de poste courant) **22/22**. Loto-Québec a confirmé que la destination applique la règle transformée : les trois écarts qui semblaient des erreurs sont en fait justifiés.
- **Distinguer anonymisation et erreur.** Courriels et libellés diffèrent sur toutes les lignes. Plutôt que de deviner, nous avons questionné les organisateurs : préfixe d'environnement accepté, identifiants et libellés incohérents signalés comme anomalies de faible priorité — à leur demande — pour ne pas masquer les 13 vraies erreurs.
- **Plusieurs affectations par employé** (primaire, temporaire, secondaires) sans numéro de poste côté cible : clé d'appariement avec repli.
- **Extractions imparfaites** : CSV tassé dans une seule colonne Excel, dates sérielles vs ISO, accents mal encodés.
- **LLM gratuits peu fiables et hallucinations** : quotas, JSON invalide, repères inventés. D'où la chaîne de repli, la validation stricte des réponses et la neutralisation automatique des repères inexistants.
- **Publier sans exposer la clé** : moteur Python dans le navigateur + relais sécurisé.

## Accomplishments that we're proud of

- Les **13 erreurs nettes** sont détectées avec leur cause probable (ex. « WHX correspond à un employé Occasionnel alors que la source indique permanent, temps plein »).
- Une **traçabilité complète** : on distingue toujours une décision par règle d'une décision par IA, et l'on voit la règle et les données qui ont mené au verdict.
- Une IA **utile, pas décorative** : arbitrage, diagnostic de motifs, priorisation, calibration de règle, synthèse, apprentissage des corrections, chat avec citations.
- Des choix **validés avec les organisateurs** plutôt que supposés.
- Un prototype **en ligne, sans installation**, qui fonctionne aussi 100 % hors ligne, couvert par 52 tests.

## What we learned

- L'approche hybride est la plus fiable : les règles assurent l'exactitude et l'auditabilité, l'IA traite l'ambiguïté et l'explication.
- Confronter une règle métier aux données révèle des écarts de documentation aussi précieux que les erreurs de données.
- Savoir dire « à valider » ou poser la question vaut mieux que deviner : l'explication compte autant que le verdict.

## What's next for CorroborAI (The Optimizers)

- Généraliser les détecteurs à d'autres interfaces RH et systèmes cibles.
- Historique et multi-utilisateurs pour les corrections d'experts.
- Corroborations planifiées avec suivi des tendances d'anomalies.
- Proposition automatique de nouvelles règles métier à partir des corrections validées.

---

## Built with (25 tags)

python · pandas · scikit-learn · numpy · fastapi · uvicorn · javascript · vite · html5 · css3 · openpyxl · pyodide · cloudflare-workers · github-pages · github-actions · google-gemini · claude · claude-code · ollama · groq · llm · machine-learning · pytest · vitest · jupyter

## "Try it out" links

- Démo en ligne : https://louisbarbonet.github.io/CorroborAI/
- Code source : https://github.com/LouisBarbonet/CorroborAI
- Rapport de corroboration (Excel) : https://github.com/LouisBarbonet/CorroborAI/blob/main/rapport/rapport_corroboration.xlsx

## Project Media — image gallery (ordre suggéré, format 3:2)

1. `01_tableau_de_bord.png` — Tableau de bord : 57 anomalies, synthèse Gemini par cause racine, calibration 0/22 · 19/22 · 22/22
2. `02_anomalies_priorisees.png` — Anomalies triées par priorité
3. `03_anomalie_type_contrat.png` — Vraie anomalie expliquée : type de contrat JWN attendu, WHX reçu
4. `04_ecart_justifie_regle_transformee_historique.png` — Écart justifié par la règle transformée, historique du poste
5. `05_ecart_justifie_ia_heures.png` — Écart justifié par l'IA : heures par défaut du poste, avis Gemini
6. `06_ecart_justifie_jointure_motif.png` — Écart justifié par règle : jointure Motif 807 → 170
7. `07_anomalie_libelle_role.png` — Libellé de rôle : substitution systématique détectée
8. `08_couverture_mapping_moteurs_ia.png` — Couverture du mapping et relais Cloudflare → Gemini
9. `09_correction_expert_formulaire.png` — Correction par un expert, portée « motif »
10. `10_regle_apprise_expert.png` — Règle apprise appliquée aux cas similaires (moteur Python dans le navigateur)
11. `01_tableau_de_bord_sombre.png` — Mode sombre (facultatif)

## Rappels de soumission

- Sélectionner **un seul prix** : celui du défi **Loto-Québec – CorroborAI**.
- Même nom d'équipe et mêmes membres que sur HxBuddy.
- Ajouter la vidéo de démonstration (scénario : `devpost/SCRIPT_PRESENTATION.md`) montrant au minimum un cas conforme, un écart justifié automatiquement et une vraie anomalie.
