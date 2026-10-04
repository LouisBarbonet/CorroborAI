# Aide-mémoire — Présentation CorroborIA

**Lien démo :** https://louisbarbonet.github.io/CorroborAI/ · **Code :** https://github.com/LouisBarbonet/CorroborAI

## Avant de commencer (checklist)

- [ ] Ouvrir le site **5 minutes avant** et cliquer « Relancer » une fois : le moteur Python se charge (30-90 s), il sera ensuite instantané.
- [ ] Vider les corrections de test : réglages du navigateur → données du site, ou console : `localStorage.clear()`.
- [ ] Préparer un 2e onglet sur le panneau 2762457 · contractTypeCode (au cas où).
- [ ] Ouvrir un 2e onglet sur `rapport/RESULTATS.md` (GitHub) et garder le rapport Excel téléchargé (plans B si le réseau est lent).
- [ ] Vérifier le relais : https://corroboria-relais.louis-barbonet.workers.dev/health → `"ok":true`.
- [ ] Zoom du navigateur à 110-125 % pour la lisibilité à l'écran.

## Le message en une phrase

> CorroborIA ne dit pas seulement « identique / différent » : il trie chaque écart en **conforme**, **justifié** ou
> **vraie anomalie**, explique pourquoi avec la règle et les preuves, et ne montre à l'humain que ce qui mérite d'être investigué.

## Chiffres clés (à connaître par cœur)

| | |
|---|---|
| Constats analysés | **551** (23 affectations × 24 champs du mapping + existence des affectations) |
| Anomalies | **57** = 13 erreurs nettes + 22 courriels + 22 libellés de rôle (faible priorité, erreurs confirmées par Loto-Québec) ; 6 à valider (heures) |
| Écarts justifiés automatiquement | **133** |
| Conformes | **361** |
| Temps de calcul | ~5 s (serveur) |
| Calibration de règle | littérale **0/22** · unité adm. **19/22** · règle transformée retenue **22/22** |
| Tests automatisés | **33** Python + **19** JavaScript |
| Appels LLM par exécution | **3** (heures par lots + synthèse), réponses en cache |

## Les 57 anomalies (regroupées, par priorité)

1. **1 affectation manquante** — 1545850, affectation temporaire (poste 45985) absente du Système B.
2. **4 types de contrat erronés** — 2762457, 4625374, 3712987, 7254364 (ex. V + permanent + temps plein → JWN attendu, WHX reçu = « Occasionnel »).
3. **2 libellés de site** — 6035643, 3241002 : libellé d'un autre site que le code.
4. **6 heures à valider** — 2911996, 4402456, 7683990 : 35 h / 36 h dans RH, 40 h du poste dans Temps (override non transmis ?).
5. **22 courriels** (priorité basse, 52-60) — préfixe `dev-08-v2_` accepté comme l'a précisé Loto-Québec,
   mais l'adresse utilise un identifiant autre que le matricule (ex. 1545850 → `PNom10370370`). Loto-Québec a confirmé :
   erreur d'anonymisation du jeu de test, et a souhaité que ce cas reste dans la détection des anomalies.
6. **22 libellés de rôle** (priorité basse, 52-59) — préfixe ≠ code emploi (ex. code 6203 → `4367-Empl4367`).
   Loto-Québec : « il s'agit d'une erreur », à signaler. Diagnostic : substitution systématique (table de libellés en amont).

> **Plus une anomalie** : les 3 dates d'affectation (9989151, 4402456, 3241002). Loto-Québec a confirmé que la destination
> applique la règle transformée (détail de poste courant) → écarts justifiés, 22/22 lignes expliquées.

## Les 3 cas de démo exigés

| Type | Où cliquer | Phrase clé |
|---|---|---|
| ✅ Conforme | recherche `8142123` · onboardDate | « Date Excel `1985-09-01` vs `1985-09-01T00:00:00.000Z` : même date, juste un format différent. » |
| 🟡 Justifié (règle) | `7603160` · statusReasonCode | « 807 → 170 : jointure avec la table Motif, prévue par le mapping. » |
| 🟡 Justifié (règle transformée) | `9989151` · assignmentStartDate | « La source ne porte que la date d'effet du poste ; la destination prend le détail de poste le plus récent — confirmé par Loto-Québec. » |
| 🟡 Justifié (IA) | `3712987` · weeklyHoursOverride | « Pas d'heures dans RH : Temps applique les 40 h du poste — valeur par défaut légitime ; Gemini confirme. » |
| 🔵 Anomalie faible | `1545850` · contactEmail | « Préfixe accepté selon Loto-Québec, mais l'identifiant n'est pas le matricule. Cause confirmée : anonymisation ; cas gardé à leur demande. » |
| 🔴 Anomalie | `2762457` · contractTypeCode | « JWN attendu, WHX reçu — WHX veut dire Occasionnel : le type d'employé est mal dérivé. » (priorité 84) |

## Architecture en 3 niveaux (le schéma mental)

1. **Comparaison brute** normalisée (dates, vides, encodage) → déterministe.
2. **Règles métier** lues dans Mapping.xlsx (jointures Motif, Détail du poste, table des contrats) → déterministe.
3. **IA** pour ce que les règles ne tranchent pas → patterns + scikit-learn + Gemini.
4. **Expert** : une correction devient une règle apprise.

## Où est l'IA ? (critère 25 pts)

- **Arbitrage des cas ambigus** : heures (détecteurs + Gemini, avis croisés).
- **Détection de motifs** : substitution systématique des libellés de rôle, structure des courriels (diagnostic des anomalies).
- **Diagnostic** de la cause probable de chaque anomalie.
- **Priorisation** : LogisticRegression + IsolationForest → score 0-100.
- **Synthèse** par cause racine rédigée par Gemini.
- **Calibration** d'une règle ambiguë contre les données (0/22, 19/22, 22/22).
- **Apprentissage** des corrections d'experts (règles apprises + réentraînement).
- **Chat du jury** avec citations cliquables.
- Désaccord IA locale / LLM → **« à valider »** (l'IA ne décide pas seule).

## Explicabilité (critère 20 pts)

Chaque constat : valeur A · valeur attendue · valeur B · règle (+ ligne Excel) · décidé par (niveau 1/2/3/expert) ·
confiance · priorité · cause probable · preuves (historique du poste, jointure).

## Qualité technique (critère 20 pts)

Fichiers sources en lecture seule (sha256) · 52 tests · rapport publié dans `rapport/` · CLI + API + interface web · rapport Excel 10 onglets ·
notebook · version en ligne sans installation · relais sécurisé (clé jamais dans le navigateur).

## Questions probables — réponses courtes

- **« Pourquoi la règle de date dit "plus ancienne" et vous prenez autre chose ? »**
  → On a mesuré trois lectures : littérale 0/22, unité adm. 19/22, règle transformée 22/22. Loto-Québec a confirmé que la
    destination applique la règle transformée : les 3 écarts restants sont donc justifiés. Configurable (`ASSIGN_START_MODE`).
- **« Et si le LLM se trompe ? »**
  → Il ne décide jamais seul : les règles tranchent tout le déterministe ; sur les cas ambigus, désaccord = « à valider ». Sans LLM, tout fonctionne (gabarit local).
- **« Confidentialité ? »**
  → Le LLM ne reçoit que les valeurs anonymisées du champ concerné, jamais les fichiers. Clé Gemini = secret Cloudflare. Mode 100 % local possible.
- **« Et les courriels ? »**
  → Loto-Québec a précisé : code = matricule, préfixe `dev-08-v2_` optionnel à accepter. On l'accepte (règle déterministe),
    mais les 22 adresses utilisent un autre identifiant que le matricule. Nous leur avons demandé : c'est une erreur
    d'anonymisation du jeu de test, mais ils souhaitent que le cas reste détecté (en production ce serait une vraie erreur).
    D'où : anomalie, avec la priorité la plus basse et la cause expliquée.
- **« Les heures, erreur ou pas ? »**
  → Ambigu : le Système B garde les heures du poste. Marqué « à valider », et l'expert peut trancher pour tous les cas d'un coup.
- **« Ça passe à l'échelle ? »**
  → Moteur pandas vectorisable, LLM appelé par lots et seulement sur les cas ambigus, cache des réponses.
- **« Quel modèle ? »**
  → Google Gemini `gemini-flash-lite-latest` (repli `gemini-flash-latest`). Interchangeable : Claude, Ollama local, Groq…
- **« Outils utilisés ? »**
  → Python, pandas, scikit-learn, FastAPI, Vite, Pyodide, Cloudflare Workers, Gemini ; développé avec l'assistance de Claude Code.

## Plans B

- Moteur Python lent à charger → montrer l'instantané (tout est déjà affiché) et le rapport Excel téléchargé.
- Relais LLM indisponible / quota → questions d'exemple du chat (réponses pré-enregistrées, instantanées).
- Pas de réseau → `dist/index.html` en local (instantané + réponses pré-enregistrées) ou captures d'écran.
