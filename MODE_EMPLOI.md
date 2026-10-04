# Mode d'emploi — CorroborIA

**Démo en ligne : https://louisbarbonet.github.io/CorroborAI/** — aucune installation, aucun compte.

## 1. Ce que vous voyez à l'ouverture

Les résultats de la corroboration des extractions fournies par Loto-Québec s'affichent immédiatement (instantané
calculé par le moteur avec Google Gemini) :

- **Indicateurs** : 38 anomalies (dont 22 courriels de faible priorité), 152 écarts justifiés automatiquement,
  361 conformes, 6 cas à valider par un expert, 551 constats. Cliquer un indicateur filtre le tableau.
- **Synthèse IA** : résumé et causes racines rédigés par Gemini, avec une recommandation par cause.
- **Comment le verdict est décidé** : les 3 niveaux (comparaison, règles métier, IA) et la *calibration* d'une règle
  ambiguë du mapping (0/22 contre 19/22).
- **Tableau** trié par priorité, filtrable par verdict, champ, niveau de décision, « à valider » et recherche libre.
- En bas : couverture du mapping (chaque ligne de Mapping.xlsx), moteurs d'IA et contrôle d'intégrité des fichiers.

## 2. Comprendre un verdict

Cliquer une ligne ouvre le panneau **« Pourquoi ce verdict »** : valeur du Système A, valeur attendue selon la règle,
valeur du Système B, justification, cause probable, texte de la règle (avec sa ligne dans Mapping.xlsx), analyse IA
(signaux, avis du LLM, probabilité du modèle ML), historique du poste et preuves.

Exemples conseillés (tapez le matricule dans la recherche) :

| Type de cas | Matricule · champ | À observer |
|---|---|---|
| Conforme | 8142123 · onboardDate | date sérielle Excel ≡ date ISO (niveau 1) |
| Écart justifié (règle) | 7603160 · statusReasonCode | jointure Motif 807 → code Remphor 170 (niveau 2) |
| Écart justifié (IA) | 1545850 · positionName | libellé pseudonymisé de façon cohérente (niveau 3, avis Gemini) |
| Anomalie (courriel) | 1545850 · contactEmail | préfixe `dev-08-v2_` accepté, mais identifiant ≠ matricule ; cause confirmée par Loto-Québec : erreur d'anonymisation du jeu de test (faible priorité) |
| Vraie anomalie | 2762457 · contractTypeCode | JWN attendu, WHX reçu ; cause : code « Occasionnel » |
| Anomalie avec historique | 9989151 · assignmentStartDate | la cible reprend la date du dernier détail du poste |
| À valider | 2911996 · weeklyHoursOverride | 35 h dans RH, 40 h du poste dans Temps |

## 3. Corriger un verdict (expert fonctionnel)

Dans le panneau, section « Corriger le verdict » : choisir le verdict, la portée (**ce cas** ou **tous les cas du même
motif**), un commentaire, puis « Enregistrer ». Exemple : heures de 2911996 → « Écart justifié », portée *motif* :
les 6 cas d'heures basculent en « Expert — règle apprise » et les anomalies passent de 38 à 32. Même principe pour
tout autre motif.

> Version en ligne : la première correction démarre le **moteur Python dans votre navigateur** (Pyodide) : environ
> 30 à 90 secondes la première fois selon la connexion (téléchargement de pandas et scikit-learn), quelques secondes ensuite. Vos
> corrections sont conservées dans votre navigateur et réappliquées à la prochaine visite. Pour repartir de zéro,
> effacez les données du site dans votre navigateur.

## 4. Lancer une corroboration sur d'autres fichiers

« Charger des fichiers » → choisir un ou plusieurs fichiers (les autres restent ceux du défi) → « Lancer la
corroboration ». En ligne, les fichiers sont traités **localement dans votre navigateur** ; seuls les cas ambigus
(valeurs anonymisées du champ concerné) sont envoyés au relais LLM. Décocher « Utiliser un LLM » pour un calcul 100 % local.

Astuce de test : copier `Employe_Destination_Anonymise_VF.xlsx`, modifier une valeur (ex. `payGradeId` de la 1re
ligne → `999`), la charger comme « Extraction cible » : la modification apparaît comme une nouvelle anomalie.

## 5. Exporter le rapport

« Exporter le rapport Excel » (onglets Synthèse, Anomalies, Écarts justifiés, Conformes, Tous les constats, Par champ,
Règles, Couverture mapping, Fournisseurs IA, Intégrité) ou « CSV ». En ligne, le rapport est généré dans le navigateur.

## 6. Assistant IA (chat)

Bouton **« Assistant IA »** en bas à droite :

- **Questions d'exemple** (sous la zone de saisie) : réponse **instantanée**, pré-enregistrée (mention visible).
- **Question libre** (800 caractères max) : envoyée à Google Gemini via un relais sécurisé ; la mention
  « Réponse en cache » indique qu'une question identique a déjà été posée (gratuit et instantané).
- Les repères comme `R-CONTRACT` ou `2762457/contractTypeCode` sont **cliquables** : règle du catalogue ou panneau du constat.
- Limites du relais : 6 questions par minute et par personne, 100 par jour au total. En cas de dépassement, un message
  l'indique et les questions d'exemple restent disponibles.

## 7. Confidentialité et ce qui n'est pas en ligne

- La clé Gemini n'est jamais dans le navigateur : elle est un secret du relais Cloudflare, qui construit lui-même
  les consignes et n'accepte que des requêtes structurées (pas de consigne libre).
- Les données publiées sont les extractions **anonymisées** fournies pour le défi, non modifiées (contrôle sha256).
- Non exposés en ligne : le serveur Python local (API FastAPI), le cache local des réponses, les corrections des autres
  visiteurs, le PDF de consignes et la présentation (non nécessaires au calcul).

## 8. En local (pour aller plus loin)

Voir le [README](README.md#démarrage-rapide) : `pip install -r requirements.txt`, `npm install`, `npm run build`,
`uvicorn api.main:app` → http://127.0.0.1:8000 (même interface, moteur Python côté serveur, LLM configurable dans `.env`).

## Outils et usage de l'IA

Moteur Python (pandas, scikit-learn), interface Vite, Pyodide, GitHub Pages, relais Cloudflare Workers, LLM Google
Gemini (`gemini-flash-lite-latest`, repli `gemini-flash-latest`). Le code a été conçu et écrit avec l'assistance de
Claude Code (Anthropic). Détails : README, sections « Utilisation de l'IA » et « Outils, sources et modèles utilisés ».
