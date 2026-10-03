# CorroborIA — Détection intelligente des écarts (défi Loto-Québec)

CorroborIA compare l'extraction du **Système A (RH)** à celle du **Système B (Temps)**. Il applique les règles
métier du mapping et classe chaque écart en **Conforme**, **Écart justifié** ou **Anomalie**. Chaque verdict est
accompagné de la règle appliquée, des preuves utilisées et d'une justification lisible. Le rapport final met en
évidence uniquement les vraies erreurs de données, triées par priorité.

**▶ Démo en ligne : https://louisbarbonet.github.io/CorroborAI/** (aucune installation ; mode d'emploi : [MODE_EMPLOI.md](MODE_EMPLOI.md))

## Résultat sur les extractions fournies

551 constats (23 affectations × 24 champs du mapping, plus l'existence de chaque affectation), traités en environ 5 s :

| Verdict | Nombre | Exemples |
|---|---|---|
| **Anomalie** | **16** | 1 affectation temporaire absente de B (1545850). 4 `contractTypeCode` erronés (2762457, 4625374, 3712987, 7254364). 3 `assignmentStartDate` qui reprennent le dernier détail du poste (9989151, 4402456, 3241002). 2 `siteName` incohérents avec `siteCode` (6035643, 3241002). 6 heures non transmises, **à valider** (2911996, 4402456, 7683990). |
| **Écart justifié** | 174 | Jointure Motif (807 → code Remphor 170), concaténations `divisionName`, dérivation du type de contrat, P/A/S → booléens, courriels et libellés pseudonymisés, encodage `Absence complÃ¨te`, heures par défaut du poste |
| **Conforme** | 361 | Dates sérielles Excel ≡ ISO, codes, libellés identiques |

Les fichiers sources ne sont jamais modifiés. Leur sha256 est vérifié contre `manifest.json` à chaque exécution.

## Démarrage rapide

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
npm install                        # outillage de l'interface (Vite, Vitest, Wrangler)

python cli.py                      # rapport dans ./output (Excel + CSV)
python cli.py --no-llm             # IA 100 % locale, aucun appel externe
npm run build                      # construit l'interface (dist/)
uvicorn api.main:app               # interface web + API : http://127.0.0.1:8000
npm run dev                        # (variante) interface Vite avec rechargement, proxy /api → :8000
pytest -q                          # 30 tests Python
npm test                           # 19 tests JS (relais, réponses pré-enregistrées)
```

Aucune clé n'est requise : sans configuration, l'IA locale (patterns, scikit-learn et gabarit) fonctionne hors ligne et gratuitement.
Pour activer un LLM gratuit, voir [Couche LLM](#couche-llm-gratuite-avec-repli-automatique).

## Architecture

```
corroborai-participants/   (lecture seule)            output/
        │                                               ▲ rapport_corroboration.xlsx / .csv, anomalies.csv
        ▼                                               │ feedback.json (corrections expert) · cache LLM : .cache/llm/
 io_loader ─► normalize ─► matcher ─► engine ──────────► report
 (sha256,      (dates,      (clé       │  niveau 1 : comparaison brute normalisée
  CSV tassé,    vides,       matricule │  niveau 2 : rules.py (règles lues dans Mapping.xlsx)
  mapping)      encodage)    + emploi  │  niveau 3 : ai/patterns → ai/scorer (ML) → ai/llm/router (LLM + repli)
                             + type)   └─ ai/feedback : corrections expert → règles apprises
                                        api/main.py (FastAPI) ─► web/ (Vite)   ·   cli.py   ·   notebook/
```

| Module | Rôle |
|---|---|
| `corroborai/io_loader.py` | Lecture xlsx en `dtype=object`, reparsing du *détail du poste* (CSV dans une seule colonne), lecture du mapping (règles multilignes fusionnées), contrôle sha256 |
| `corroborai/normalize.py` | Vides (`None`, `NaN`, `-`, `""`), dates (sériel Excel, ISO, datetime), booléens (Oui/true), nombres (`7,2`), zéros de tête, **réparation du mojibake** (ftfy), accents |
| `corroborai/matcher.py` | Appariement `(Matricule, CodeEmploi, P/A/S)` avec repli. Détecte les affectations manquantes ou en surplus. |
| `corroborai/mapping.py` | Spécification déclarative des 24 champs du mapping (type, règle, criticité, éligibilité IA). Vérifie que chaque ligne du mapping est couverte. |
| `corroborai/rules.py` | Règles métier déterministes. Les tables du type de contrat et de la situation d'emploi sont **lues dans Mapping.xlsx**. |
| `corroborai/engine.py` | Pipeline à 3 niveaux, fusion des avis IA, calibration des règles, synthèse |
| `corroborai/ai/` | `patterns.py` (détecteurs), `scorer.py` (scikit-learn), `llm/` (chaîne de fournisseurs), `feedback.py` (boucle expert) |
| `corroborai/report.py` | Excel mis en forme (Synthèse, Anomalies, Écarts justifiés, Conformes, Tous, Par champ, Règles, Couverture, Fournisseurs IA, Intégrité) et CSV |
| `corroborai/serialize.py`, `chat_context.py` | Format JSON unique (API, instantané, Pyodide) ; contexte du chat du jury (règles, mapping, résultats, repères citables) |
| `corroborai/ai/llm/relay.py` | Routeur utilisé dans le navigateur : appelle le relais Cloudflare, rejoue l'instantané, repli local |
| `prompts/prompts.json` | **Source unique des consignes LLM**, partagée par le serveur Python et le relais Cloudflare |

## Version en ligne (GitHub Pages + relais Cloudflare)

```
GitHub Pages (statique, dist/)                         Cloudflare Worker « corroboria-relais »
 index.html (single-file, Vite)                         POST /judge  /summary  /chat   GET /health
  ├─ instantané embarqué (résultats + réponses LLM)     1. origine autorisée (CORS), sinon 403
  ├─ réponses pré-enregistrées du chat                  2. validation stricte (structure, ≤ 800 car.)
  ├─ moteur Python dans le navigateur (Pyodide,  ─────► 3. cache KV 30 j (avant les limites)
  │   chargé à la demande) : recalcul, téléversement,    4. limite par IP (6 / min)
  │   corrections expert, exports Excel/CSV             5. plafond quotidien global (100)
  └─ chat du jury ─────────────────────────────────────► 6. Gemini REST (2 tentatives + modèle de repli)
                                                        clé Gemini = secret Cloudflare, jamais dans le navigateur
```

- **Instantané** : `npm run snapshot` exécute le moteur avec Gemini et écrit `web/src/generated/snapshot.json` (résultats +
  réponses LLM enregistrées) et `worker/src/data.generated.json` (consignes, contexte du chat, repères citables).
  Le site s'affiche instantanément, même ouvert hors ligne (`dist/index.html`).
- **Moteur dans le navigateur** : le paquet `corroborai` tourne tel quel dans Pyodide (pandas, scikit-learn, openpyxl).
  Les réponses LLM de l'instantané sont rejouées sans appel ; les cas nouveaux passent par le relais. Les corrections
  expert sont conservées dans le navigateur (`localStorage`).
- **Le relais construit lui-même les consignes** : il n'accepte que des données structurées (champ + cas ambigus,
  statistiques, ou une question ≤ 800 caractères), il ne peut donc pas servir de proxy Gemini générique.
  Les repères inventés par le modèle sont neutralisés (crochets retirés) avant d'être renvoyés.
- **Réponses pré-enregistrées** : `data/chat-questions.json` → `npm run precompute` → `data/precomputed/chat.json`
  (servies instantanément ; un test vérifie que chaque repère cité existe réellement).
- **Déploiement** : `.github/workflows/pages.yml` (tests Python + JS, build avec `VITE_CHAT_URL = vars.CHAT_URL`,
  publication Pages) ; relais : `npm run worker:deploy` ; clé : `npm run wrangler -- secret put GEMINI_API_KEY --config worker/wrangler.toml`.
- **Non exposé en ligne** : la clé Gemini, le serveur FastAPI (`/api/...`), le cache disque local `.cache/llm/`, les
  corrections expert des autres visiteurs (chacun garde les siennes dans son navigateur), le PDF de consignes et la
  présentation (non nécessaires au calcul ; le contrôle d'intégrité les signale « non embarqués »).

## Règles prises en charge

| Id | Champ(s) B | Règle |
|---|---|---|
| R-DIRECT | givenName, surname, onboardDate, personId, siteName, siteCode, divisionId, divisionCode, positionId, positionCode, payGradeId, weekly/dailyHoursOverride | Valeur identique après normalisation |
| R-EMAIL | contactEmail | 1re lettre du prénom + nom + 3 derniers chiffres du matricule + `@loto-quebec.com`, sans accents |
| R-DIVNAME | divisionName | `CodeDirection` sur 5 chiffres + `-` + libellé |
| R-POSNAME | positionName | `CodeEmploi` + `-` + intitulé |
| R-STATUS / -CAD / -CADP | detailedStatus, statusReasonCode, expectedReturnDate | Code d'accès 00/01 → Actif, nulls. 02/03/06/07 → Absence complète, code Remphor obtenu par **jointure** `CodeRaisonStatut ⋈ Motif`, date de retour. |
| R-CONTRACT | contractTypeCode | Table EMPTP_CD / PERM_IND / FT_IND → JWN, XFLR, KELH, WHX… (lue dans le mapping) |
| R-AFFTYPE | isPrimaryAssignment, isTemporaryAssignment | P → (true, false), A → (false, true), S → (false, false) |
| R-ASSIGN-START | assignmentStartDate | Combinaison de `DateEntréePoste` et de la date d'entrée en vigueur de l'unité adm. courante (détection des changements dans le détail du poste, sinon MIN EFFDT) |
| R-ASSIGN-END | assignmentEndDate, termEndDate | Date la plus ancienne entre l'expiration du poste et la fin de l'unité adm. (effdt suivant − 1 jour si l'unité change) |
| R-RECORD | (affectation) | Chaque affectation source doit exister dans B |
| R-NORMALISATION | tout champ texte | Valeur identique après réparation de l'encodage → écart justifié, avec une recommandation de correction de l'export |

`LibelléImputation` n'a pas de champ cible dans le mapping (`-`). Il est donc exclu, comme l'exige la consigne.

## Utilisation de l'IA

L'approche est **hybride** : les règles tranchent tout ce qui est déterministe. L'IA intervient pour les cas
ambigus, la priorisation, l'explication et l'apprentissage. Chaque constat indique `niveau` et `decide_par`, ce
qui permet de toujours distinguer une décision par règle d'une décision par IA.

1. **Détecteurs de patterns** (`ai/patterns.py`, raisonnement sur l'ensemble du jeu de données) :
   - **Courriel** : reconnaît un préfixe d'environnement (`dev-08-v2_`). Vérifie la structure *initiale + nom + identifiant + 3 derniers chiffres de cet identifiant*, le domaine, ainsi que l'unicité et la stabilité de l'adresse par employé. Conclusion : identifiant pseudonymisé, écart justifié.
   - **Libellé d'emploi** : vérifie que la correspondance code d'emploi ↔ libellé cible est **biunivoque** sur tous les employés. Si oui, il s'agit d'une pseudonymisation cohérente. Toute incohérence est signalée comme anomalie.
   - **Heures** : compare aux heures contractuelles du *détail du poste*. Une source vide correspond au défaut du poste (justifié). Une norme employé différente indique un override non transmis : anomalie **à valider**, avec une confiance de 0,6.
   - **Diagnostic des anomalies déterministes** : explique la cause probable. Exemples : « la cible reprend la date d'effet du DERNIER détail du poste (changement de gestionnaire, sans changement d'unité) » ; « WHX correspond à EMPTP_CD=O alors que la source indique V ».
2. **Apprentissage automatique** (`ai/scorer.py`, scikit-learn) :
   - Une régression logistique est entraînée à chaque exécution sur les verdicts déterministes et sur les corrections d'experts (poids ×5). Elle donne une seconde opinion P(anomalie).
   - Un IsolationForest mesure l'atypicité des anomalies.
   - La **priorité (0-100)** combine la criticité métier du champ, la confiance, P(anomalie), l'atypicité et la concentration d'anomalies par employé.
3. **LLM (arbitrage et explication)** :
   - **Google Gemini** (`gemini-flash-lite-latest`, repli `gemini-flash-latest`) reçoit les cas ambigus **par lots, un par champ** (5 appels par exécution, réponses mises en cache) avec la règle du mapping et les signaux locaux.
   - Le LLM rend un verdict, une confiance et une justification en français. Il rédige aussi la **synthèse exécutive par cause racine**.
   - Si le LLM confirme l'analyse locale, la confiance augmente. S'il la contredit, le cas est marqué **à valider** et les deux avis sont conservés dans le rapport.
4. **Calibration de règle** :
   - Le moteur confronte les interprétations possibles d'une règle ambiguë aux données. Pour `assignmentStartDate`, la lecture littérale « plus ancienne » concorde sur **0/22** lignes et « plus récente » sur **19/22**.
   - L'interprétation retenue est donc « plus récente » (`ASSIGN_START_MODE=max`), documentée dans le rapport, à faire confirmer par l'équipe fonctionnelle.
5. **Chat du jury** : un assistant répond aux questions sur les résultats, les règles et la méthode, uniquement à partir
   du contexte du projet, en citant ses sources (`[R-CONTRACT]`, `[2762457/contractTypeCode]`, cliquables dans l'interface).
6. **Boucle expert** :
   - Dans l'interface, un expert corrige un verdict pour **ce cas** ou pour **tous les cas du même motif** (signature).
   - La correction est stockée dans `output/feedback.json` (version en ligne : dans le navigateur), réappliquée aux exécutions suivantes (`decide_par = Expert — règle apprise`) et utilisée pour réentraîner le modèle ML.

### Couche LLM gratuite avec repli automatique

`ai/llm/router.py` essaie les fournisseurs dans l'ordre `LLM_PROVIDERS`. Si l'un est indisponible ou échoue
(délai, quota, HTTP, JSON invalide), il passe au suivant. Le **gabarit local** garantit qu'une exécution aboutit
toujours. Le fournisseur réellement utilisé est tracé sur chaque constat et dans le rapport.

| Ordre | Fournisseur | Coût | Configuration (`.env`, voir `.env.example`) |
|---|---|---|---|
| 1 | Claude (Anthropic, `claude-opus-5-5`) | payant | `ANTHROPIC_API_KEY` |
| 2 | **Ollama** (local, ex. `qwen2.5:7b`) | gratuit, aucune donnée ne sort | installer Ollama + `ollama pull qwen2.5:7b` |
| 3 | **Groq** (`llama-3.3-70b-versatile`) | clé gratuite | `GROQ_API_KEY` |
| 4 | **Google Gemini** (`gemini-flash-lite-latest`, utilisé pour la démo) | clé gratuite | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| 5 | **OpenRouter** (modèles `:free`) | clé gratuite | `OPENROUTER_API_KEY` |
| 6 | Pollinations (sans clé) | gratuit, best-effort | `ALLOW_KEYLESS_PUBLIC_LLM=1` (désactivé par défaut) |
| 7 | **Gabarit local** | gratuit, hors ligne | toujours actif |

Le cache disque local est dans `.cache/llm/` (vidage : `npm run cache:clear`). L'état de chaque fournisseur est visible dans l'interface (badge « IA » et tableau « Moteurs d'IA »), ainsi que via `GET /api/llm-status`.

**Confidentialité :**
- Seul un contexte minimal est transmis aux LLM : les valeurs du champ concerné, déjà anonymisées, et les signaux de l'analyse locale. Les fichiers complets ne sont jamais envoyés.
- Pour aucun appel externe, utiliser `--no-llm` ou Ollama.
- Le service public sans clé est désactivé par défaut. Lors de nos tests (avec des données synthétiques), son API historique répondait par intermittence (HTTP 402/500) : il sert uniquement de dernier recours.

## Interface web

En ligne (https://louisbarbonet.github.io/CorroborAI/) ou en local (`npm run build` puis `uvicorn api.main:app`, http://127.0.0.1:8000). L'interface propose :
- Chargement de nouveaux fichiers (copiés dans un dossier temporaire) et lancement de la corroboration.
- Indicateurs cliquables : anomalies, écarts justifiés, conformes, à valider.
- Synthèse IA par cause racine et encart de calibration de règle.
- Tableau filtrable par verdict, champ, niveau de décision, « à valider » et recherche, trié par priorité.
- Panneau « Pourquoi ce verdict » : valeurs A / attendue / B, justification, cause probable, texte de la règle avec sa ligne Excel, signaux IA, avis du LLM, probabilité ML, historique du poste et preuves JSON.
- **Correction d'un verdict par un expert** (cas ou motif).
- Export Excel et CSV.
- **Assistant IA** (bouton en bas à droite) : questions d'exemple à réponse instantanée, questions libres via le LLM.

API : `POST /api/run`, `GET /api/summary`, `GET /api/findings`, `GET /api/findings/{id}`, `POST|GET|DELETE /api/feedback`,
`POST /api/chat`, `GET /api/health`, `GET /api/llm-status`, `GET /api/export.xlsx`, `GET /api/export.csv`. Documentation interactive : `/docs`.

## Scénario de démonstration (environ 3 min)

1. Ouvrir https://louisbarbonet.github.io/CorroborAI/ (ou l'interface locale) : 16 anomalies, 174 écarts justifiés, 361 conformes, sources intactes.
2. **Cas conforme** : filtre *Conforme*, champ `onboardDate` de 8142123. Le sériel Excel 31291 est égal à `1985-09-01T00:00:00.000Z` (niveau 1).
3. **Écart justifié automatiquement** : 7603160, `statusReasonCode`. Source 807, cible 170 : jointure Motif 807 → Remphor 170 (niveau 2). Montrer aussi `contactEmail` (IA : préfixe d'environnement et pseudonymisation).
4. **Vraie anomalie** : 2762457, `contractTypeCode`. JWN attendu (V, permanent, temps plein), WHX reçu. Diagnostic : WHX correspond à « Occasionnel ». Montrer ensuite 9989151 `assignmentStartDate` avec l'historique du poste.
5. **Cas à valider** : heures de 2911996 (35 h dans RH, 40 h du poste dans Temps).
   - Corriger en « Écart justifié », portée *motif*.
   - Les 6 cas similaires basculent en « Expert — règle apprise ».
6. Exporter le rapport Excel.
7. **Assistant IA** : cliquer une question d'exemple (réponse instantanée), puis poser une question libre (relais → Gemini).

## Hypothèses

- **assignmentStartDate** : interprétation « date la plus récente » (voir calibration). Elle est configurable via `ASSIGN_START_MODE=min`.
- **Situation d'emploi** : le *code de traitement des accès* est `CodeSuspensionAccès` (onglet « Jointure - Motif » du mapping). Le code Remphor provient de `CodeStatutSystèmeExterne`.
- **divisionName** : code sur 5 chiffres, format observé dans B (`00397-UnitAdmin00397`).
- **Appariement** : la cible n'ayant pas de numéro de poste, la clé est *matricule + emploi + type d'affectation*.
- **Écart justifié** : différence de valeur entre A et B expliquée par une règle, une normalisation (encodage) ou une analyse IA. **Conforme** : même valeur, au format près.
- **Heures** : une norme employé différente des heures du poste est considérée comme une anomalie *probable* à valider, car l'objectif du champ `…Override` est de porter la valeur de l'employé.

## Limites

- Le jeu de test est petit (23 affectations). Le modèle ML sert à la priorisation et à une seconde opinion, pas à décider seul.
- Les détecteurs de pseudonymisation sont adaptés aux données anonymisées du défi. En production, avec des données réelles, la règle du courriel serait vérifiée strictement.
- La qualité des justifications LLM dépend du fournisseur. Les petits modèles locaux sont moins précis, d'où la fusion avec l'analyse locale et le marquage « à valider » en cas de désaccord.
- Le stockage des corrections expert est un fichier JSON local (ou le navigateur en ligne), sans gestion multi-utilisateur.
- Version en ligne : le premier recalcul télécharge Pyodide et ses bibliothèques (≈ 30-50 s, puis cache du navigateur) ;
  le chat dépend du quota du relais (100 requêtes/jour, 6/min par IP), mais les questions d'exemple restent toujours disponibles.
  Le contexte du chat décrit les extractions fournies, pas les fichiers téléversés par un visiteur.

## Outils, sources et modèles utilisés

- **Langage et bibliothèques** : Python 3.12, pandas, openpyxl, numpy, **scikit-learn** (LogisticRegression, IsolationForest), ftfy (réparation d'encodage), httpx, FastAPI, Uvicorn, pytest, nbformat/nbclient.
- **Web et hébergement** : Vite + vite-plugin-singlefile, JavaScript, Vitest, **Pyodide** 0.28 (Python dans le navigateur), GitHub Pages et GitHub Actions, **Cloudflare Workers** (KV, Rate Limiting) via Wrangler.
- **LLM** : **Google Gemini** (`gemini-flash-lite-latest`, repli `gemini-flash-latest`) pour la démo, l'instantané, les réponses pré-enregistrées et le relais en ligne. Interchangeables en local : Anthropic Claude (`claude-opus-5-5`, SDK `anthropic`) ; Ollama (Qwen 2.5, Llama) ; Groq (Llama 3.3 70B) ; OpenRouter (modèles gratuits) ; Pollinations.
- **Données** : extractions anonymisées et documents fournis par Loto-Québec (`corroborai-participants/`), non modifiés, publiés avec la démo.
- **Assistance au développement** : Claude Code (Anthropic) a servi à concevoir et écrire le code, y compris la version en ligne et le relais.

## Structure du dépôt

```
api/main.py                 API FastAPI + service de l'interface construite (dist/)
cli.py                      exécution en ligne de commande
corroborai/                 moteur (voir Architecture)
prompts/prompts.json        consignes LLM partagées (serveur Python + relais)
web/                        interface Vite (index.html, style.css, src/ : UI, backends, chat, worker Pyodide)
worker/                     relais Cloudflare (wrangler.toml ; src/ : relais, Gemini, validation, data.generated.json)
shared/                     code JS partagé site ↔ relais (normalisation des questions, repères)
data/                       questions d'exemple et réponses pré-enregistrées du chat
scripts/                    export_snapshot.py, precompute_chat.py, prepare-web.mjs
notebook/exploration.ipynb  exploration, choix d'approche, 3 types de cas, résultats
tests/  tests_js/           30 tests Python + 19 tests JS
.github/workflows/pages.yml build, tests et publication GitHub Pages
.env.example                configuration des fournisseurs LLM (aucune clé)
corroborai-participants/    données fournies (lecture seule)
```
