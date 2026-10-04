# Résultats finaux de la corroboration — CorroborIA

Généré le 2026-10-04T13:01:33 à partir des extractions fournies par Loto-Québec (fichiers sources inchangés : ✓ sha256 conformes). LLM : gemini/gemini-flash-lite-latest.
Fichiers détaillés : [`rapport_corroboration.xlsx`](rapport_corroboration.xlsx) (10 onglets), [`rapport_corroboration.csv`](rapport_corroboration.csv) (tous les constats), [`anomalies.csv`](anomalies.csv).

## Synthèse

| Verdict | Nombre |
|---|---|
| Constats évalués (affectations × champs du mapping) | **551** |
| Anomalies | **57** (dont 6 à valider par un expert) |
| Écarts justifiés automatiquement | **133** |
| Conformes | **361** |

> L'analyse de corroboration entre le Système A et le Système B met en évidence 57 anomalies réparties sur 7 groupes de causes. Les écarts les plus critiques concernent l'absence d'affectation temporaire, des codes de contrat incorrects et des défauts de transmission des heures de référence. Les problèmes de libellés de sites, de construction des courriels et de substitution des libellés de postes complètent ce bilan.

### Causes racines (par ordre d'importance)

| Cause | Cas | Recommandation |
|---|---|---|
| Absence d'affectation temporaire | 1 | Vérifier le flux d'intégration pour s'assurer que les affectations temporaires sont correctement transmises vers le Système B. |
| Code de contrat incorrect ou non mis à jour | 4 | Revoir la logique de dérivation des types d'employés et mettre à jour les statuts dans la source. |
| Non-transmission des heures contractuelles ou journalières modifiées (override) | 6 | À confirmer (un horaire réduit peut être géré autrement) : inspecter le paramétrage des interfaces pour valider la transmission des heures spécifiques. |
| Incohérence entre le code site et le libellé associé | 2 | Corriger la correspondance entre les codes sites et leurs libellés dans le Système B. |
| Non-respect de la règle de construction de l'adresse courriel | 22 | Vérifier le script de génération des courriels pour garantir l'utilisation correcte du matricule (cause confirmée liée à l'anonymisation du jeu de test). |
| Erreur de correspondance des libellés de postes | 22 | Corriger la table de correspondances des libellés de postes en amont pour éliminer la substitution systématique. |

## Anomalies (triées par priorité)

| Priorité | Matricule | Aff. | Champ (B) | Attendu (règle) | Reçu (B) | Règle | À valider | Cause probable |
|---|---|---|---|---|---|---|---|---|
| 91 | 1545850 | A | `(affectation)` | 1 enregistrement | ∅ | R-RECORD |  | L'employé existe dans le Système B (1 affectation(s) transmise(s)) mais son affectation temporaire (poste 45985, emploi 6585, entrée 2025-09-22) est absente. |
| 84 | 2762457 | P | `contractTypeCode` | JWN | WHX | R-CONTRACT |  | Le code reçu WHX correspond à la condition « SI EMPTP_CD="O" (Occasionnel - Surnuméraire) --> Mettre "WHX" », alors que la source indique {'EMPTP_CD': 'V', 'PERM_IND': '1', 'FT_IND': '1'} (→ JWN). Le… |
| 84 | 3712987 | P | `contractTypeCode` | JWN | XFLR | R-CONTRACT |  | Le code reçu XFLR correspond à la condition « SI PERM_IND=1 et FT_IND=0 et EMPTP_CD="V" --> Mettre "XFLR" », alors que la source indique {'EMPTP_CD': 'V', 'PERM_IND': '1', 'FT_IND': '1'} (→ JWN). Le … |
| 84 | 4625374 | P | `contractTypeCode` | WHX | JWN | R-CONTRACT |  | Le code reçu JWN correspond à la condition « SI PERM_IND=1 et FT_IND=1 et EMPTP_CD="V" --> Mettre "JWN" », alors que la source indique {'EMPTP_CD': 'O', 'PERM_IND': '0', 'FT_IND': '0'} (→ WHX). Le ty… |
| 84 | 7254364 | P | `contractTypeCode` | XFLR | JWN | R-CONTRACT |  | Le code reçu JWN correspond à la condition « SI PERM_IND=1 et FT_IND=1 et EMPTP_CD="V" --> Mettre "JWN" », alors que la source indique {'EMPTP_CD': 'V', 'PERM_IND': '1', 'FT_IND': '0'} (→ XFLR). Le t… |
| 73 | 2911996 | P | `weeklyHoursOverride` | 35 | 40 | R-DIRECT | oui | Le Système B conserve les heures contractuelles du poste (40) au lieu de la norme de l'employé (35) : l'override ne semble pas transmis. À confirmer (un horaire réduit peut être géré autrement). |
| 72 | 4402456 | P | `weeklyHoursOverride` | 36 | 40 | R-DIRECT | oui | Le Système B conserve les heures contractuelles du poste (40) au lieu de la norme de l'employé (36) : l'override ne semble pas transmis. À confirmer (un horaire réduit peut être géré autrement). |
| 72 | 7683990 | P | `weeklyHoursOverride` | 36 | 40 | R-DIRECT | oui | Le Système B conserve les heures contractuelles du poste (40) au lieu de la norme de l'employé (36) : l'override ne semble pas transmis. À confirmer (un horaire réduit peut être géré autrement). |
| 70 | 2911996 | P | `dailyHoursOverride` | 7 | 8 | R-DIRECT | oui | Le Système B conserve les heures contractuelles du poste (8) au lieu de la norme de l'employé (7) : l'override ne semble pas transmis. À confirmer (un horaire réduit peut être géré autrement). |
| 70 | 3241002 | P | `siteName` | Emplacement48 | Emplacement35 | R-DIRECT |  | Le libellé reçu « Emplacement35 » correspond au site 35 alors que le code site est 48 (source et cible) : incohérence code/libellé de l'emplacement dans le Système B. |
| 70 | 6035643 | P | `siteName` | Emplacement35 | Emplacement48 | R-DIRECT |  | Le libellé reçu « Emplacement48 » correspond au site 48 alors que le code site est 35 (source et cible) : incohérence code/libellé de l'emplacement dans le Système B. |
| 66 | 4402456 | P | `dailyHoursOverride` | 7.2 | 8 | R-DIRECT | oui | Le Système B conserve les heures contractuelles du poste (8) au lieu de la norme de l'employé (7.2) : l'override ne semble pas transmis. À confirmer (un horaire réduit peut être géré autrement). |
| 66 | 7683990 | P | `dailyHoursOverride` | 7.2 | 8 | R-DIRECT | oui | Le Système B conserve les heures contractuelles du poste (8) au lieu de la norme de l'employé (7.2) : l'override ne semble pas transmis. À confirmer (un horaire réduit peut être géré autrement). |
| 60 | 2911996 | P | `contactEmail` | pnom2911996996@loto-quebec.com | dev-08-v2_PNom10446446@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10446) n'est pas le matricule 2911996 : la règle R-… |
| 59 | 2173396 | P | `positionName` | 6900-Empl6900 | 5123-Empl5123 | R-POSNAME |  | Le libellé reçu « 5123-Empl5123 » ne correspond pas au code emploi 6900 (attendu « 6900-Empl6900 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 58 | 1545850 | P | `contactEmail` | pnom1545850850@loto-quebec.com | dev-08-v2_PNom10370370@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10370) n'est pas le matricule 1545850 : la règle R-… |
| 58 | 6035643 | P | `contactEmail` | pnom6035643643@loto-quebec.com | dev-08-v2_PNom10430430@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10430) n'est pas le matricule 6035643 : la règle R-… |
| 57 | 2762457 | P | `contactEmail` | pnom2762457457@loto-quebec.com | dev-08-v2_PNom10398398@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10398) n'est pas le matricule 2762457 : la règle R-… |
| 56 | 7254364 | P | `contactEmail` | pnom7254364364@loto-quebec.com | dev-08-v2_PNom10466466@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10466) n'est pas le matricule 7254364 : la règle R-… |
| 55 | 2911996 | P | `positionName` | 6051-Empl6051 | 0449-Empl0449 | R-POSNAME |  | Le libellé reçu « 0449-Empl0449 » ne correspond pas au code emploi 6051 (attendu « 6051-Empl6051 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 55 | 4402456 | P | `contactEmail` | pnom4402456456@loto-quebec.com | dev-08-v2_PNom10460460@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10460) n'est pas le matricule 4402456 : la règle R-… |
| 55 | 4402456 | P | `positionName` | 6031-Empl6031 | 0485-Empl0485 | R-POSNAME |  | Le libellé reçu « 0485-Empl0485 » ne correspond pas au code emploi 6031 (attendu « 6031-Empl6031 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 55 | 7683990 | P | `contactEmail` | pnom7683990990@loto-quebec.com | dev-08-v2_PNom10477477@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10477) n'est pas le matricule 7683990 : la règle R-… |
| 55 | 7683990 | S | `contactEmail` | pnom7683990990@loto-quebec.com | dev-08-v2_PNom10477477@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10477) n'est pas le matricule 7683990 : la règle R-… |
| 55 | 7683990 | S | `contactEmail` | pnom7683990990@loto-quebec.com | dev-08-v2_PNom10477477@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10477) n'est pas le matricule 7683990 : la règle R-… |
| 55 | 7683990 | P | `positionName` | 6725-Empl6725 | 4051-Empl4051 | R-POSNAME |  | Le libellé reçu « 4051-Empl4051 » ne correspond pas au code emploi 6725 (attendu « 6725-Empl6725 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 55 | 7683990 | S | `positionName` | 6754-Empl6754 | 0509-Empl0509 | R-POSNAME |  | Le libellé reçu « 0509-Empl0509 » ne correspond pas au code emploi 6754 (attendu « 6754-Empl6754 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 55 | 7683990 | S | `positionName` | 6031-Empl6031 | 0485-Empl0485 | R-POSNAME |  | Le libellé reçu « 0485-Empl0485 » ne correspond pas au code emploi 6031 (attendu « 6031-Empl6031 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 54 | 1545850 | P | `positionName` | 6585-Empl6585 | 3649-Empl3649 | R-POSNAME |  | Le libellé reçu « 3649-Empl3649 » ne correspond pas au code emploi 6585 (attendu « 6585-Empl6585 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 54 | 2762457 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 54 | 3241002 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 54 | 3712987 | P | `contactEmail` | pnom3712987987@loto-quebec.com | dev-08-v2_PNom10465465@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10465) n'est pas le matricule 3712987 : la règle R-… |
| 54 | 3712987 | P | `positionName` | 6031-Empl6031 | 0485-Empl0485 | R-POSNAME |  | Le libellé reçu « 0485-Empl0485 » ne correspond pas au code emploi 6031 (attendu « 6031-Empl6031 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 54 | 4625374 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 54 | 6035643 | P | `positionName` | 6622-Empl6622 | 4368-Empl4368 | R-POSNAME |  | Le libellé reçu « 4368-Empl4368 » ne correspond pas au code emploi 6622 (attendu « 6622-Empl6622 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 54 | 7254364 | P | `positionName` | 6754-Empl6754 | 0509-Empl0509 | R-POSNAME |  | Le libellé reçu « 0509-Empl0509 » ne correspond pas au code emploi 6754 (attendu « 6754-Empl6754 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 53 | 3241002 | P | `contactEmail` | pnom3241002002@loto-quebec.com | dev-08-v2_PNom10434434@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10434) n'est pas le matricule 3241002 : la règle R-… |
| 53 | 4625374 | P | `contactEmail` | pnom4625374374@loto-quebec.com | dev-08-v2_PNom10401401@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10401) n'est pas le matricule 4625374 : la règle R-… |
| 53 | 9989151 | P | `contactEmail` | pnom9989151151@loto-quebec.com | dev-08-v2_PNom10372372@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10372) n'est pas le matricule 9989151 : la règle R-… |
| 52 | 2173396 | P | `contactEmail` | pnom2173396396@loto-quebec.com | dev-08-v2_PNom10437437@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10437) n'est pas le matricule 2173396 : la règle R-… |
| 52 | 2648214 | P | `contactEmail` | pnom2648214214@loto-quebec.com | dev-08-v2_PNom10470470@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10470) n'est pas le matricule 2648214 : la règle R-… |
| 52 | 2648214 | P | `positionName` | 6972-Empl6972 | 5126-Empl5126 | R-POSNAME |  | Le libellé reçu « 5126-Empl5126 » ne correspond pas au code emploi 6972 (attendu « 6972-Empl6972 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 2747515 | P | `contactEmail` | pnom2747515515@loto-quebec.com | dev-08-v2_PNom10402402@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10402) n'est pas le matricule 2747515 : la règle R-… |
| 52 | 2747515 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 4880692 | P | `contactEmail` | pnom4880692692@loto-quebec.com | dev-08-v2_PNom10404404@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10404) n'est pas le matricule 4880692 : la règle R-… |
| 52 | 4880692 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 6783031 | P | `contactEmail` | pnom6783031031@loto-quebec.com | dev-08-v2_PNom10389389@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10389) n'est pas le matricule 6783031 : la règle R-… |
| 52 | 6783031 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 7070325 | P | `contactEmail` | pnom7070325325@loto-quebec.com | dev-08-v2_PNom10428428@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10428) n'est pas le matricule 7070325 : la règle R-… |
| 52 | 7070325 | P | `positionName` | 6622-Empl6622 | 4368-Empl4368 | R-POSNAME |  | Le libellé reçu « 4368-Empl4368 » ne correspond pas au code emploi 6622 (attendu « 6622-Empl6622 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 7603160 | P | `contactEmail` | pnom7603160160@loto-quebec.com | dev-08-v2_PNom10385385@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10385) n'est pas le matricule 7603160 : la règle R-… |
| 52 | 7603160 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 8142123 | P | `contactEmail` | pnom8142123123@loto-quebec.com | dev-08-v2_PNom10380380@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10380) n'est pas le matricule 8142123 : la règle R-… |
| 52 | 8142123 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 8644330 | P | `contactEmail` | pnom8644330330@loto-quebec.com | dev-08-v2_PNom10473473@loto-quebec.com | R-EMAIL |  | L'adresse respecte la structure de la règle (initiale, nom, identifiant + 3 derniers chiffres, domaine, adresse unique) mais l'identifiant utilisé (10473) n'est pas le matricule 8644330 : la règle R-… |
| 52 | 8644330 | P | `positionName` | 6031-Empl6031 | 0485-Empl0485 | R-POSNAME |  | Le libellé reçu « 0485-Empl0485 » ne correspond pas au code emploi 6031 (attendu « 6031-Empl6031 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |
| 52 | 9989151 | P | `positionName` | 6203-Empl6203 | 4367-Empl4367 | R-POSNAME |  | Le libellé reçu « 4367-Empl4367 » ne correspond pas au code emploi 6203 (attendu « 6203-Empl6203 ») : la règle R-POSNAME n'est pas respectée. La substitution est systématique et cohérente sur tout le… |

## Écarts justifiés (regroupés)

| Champ (B) | Règle | Cas | Exemple | Justification |
|---|---|---|---|---|
| `divisionName` | R-DIVNAME | 22 | 1545850 : CodeDirection=397 \| LibelléDirection=UnitAdmin00… → 00397-UnitAdmin00397 | Écart expliqué par la règle R-DIVNAME : Concaténation Unité adm. (397 complété sur 5 chiffres) + « - » + libellé. |
| `isPrimaryAssignment` | R-AFFTYPE | 22 | 1545850 : P → true | Écart expliqué par la règle R-AFFTYPE : TypeAffectation=P → isPrimaryAssignment=true. |
| `isTemporaryAssignment` | R-AFFTYPE | 22 | 1545850 : P → false | Écart expliqué par la règle R-AFFTYPE : TypeAffectation=P → isTemporaryAssignment=false. |
| `statusReasonCode` | R-STATUS-CAD | 22 | 1545850 : 697 → ∅ | Écart expliqué par la règle R-STATUS-CAD : Situation « Actif » (code 1) → cf_CAD = null. |
| `detailedStatus` | R-STATUS | 20 | 1545850 : 1 → Actif | Écart expliqué par la règle R-STATUS : Code de traitement des accès 1 → cf_specificStatus « Actif ». |
| `contractTypeCode` | R-CONTRACT | 18 | 1545850 : CatégorieEmploi=V \| EstPermanent=Oui \| EstTemps… → JWN | Écart expliqué par la règle R-CONTRACT : SI PERM_IND=1 et FT_IND=1 et EMPTP_CD="V" --> Mettre "JWN" |
| `assignmentStartDate` | R-ASSIGN-START | 3 | 3241002 : 2009-03-30 → 2022-10-05 | Écart expliqué par la règle R-ASSIGN-START : Règle transformée (précisée par Loto-Québec) : date la plus récente entre la date d'effet du poste (DateEntréePoste 2009-03-30) et la date d'effet du déta… |
| `detailedStatus` | R-NORMALISATION | 2 | 2911996 : 2 → Absence complÃ¨te | Valeur identique après correction de l'encodage : « Absence complÃ¨te » (UTF-8 lu comme Latin-1) = « Absence complète ». Code de traitement des accès 2 → cf_specificStatus « Absence complète ». |
| `dailyHoursOverride` | R-DIRECT | 1 | 3712987 : ∅ → 8 | La valeur du Système A est null tandis que le Système B applique la valeur par défaut du poste (8), ce qui constitue un comportement standard. |
| `weeklyHoursOverride` | R-DIRECT | 1 | 3712987 : ∅ → 40 | Le Système A ne contient aucune valeur pour l'employé (null), et le Système B applique logiquement les heures contractuelles du poste (40) par défaut. Cet écart est donc pleinement justifié. |

## Calibration de règle

- **R-ASSIGN-START** — « Date la plus ancienne entre la date calculée du changement d'unité administrative et la date d'effet poste » : littérale (plus ancienne, unité adm.) **0/22**, plus récente (unité adm.) **19/22**, règle transformée (plus récente, détail de poste courant) **22/22**. Interprétation retenue : règle transformée (plus récente, détail de poste courant) (22/22). Loto-Québec a confirmé que la source ne porte que la date d'effet du poste et que la destination applique la règle transformée (paramètre ASSIGN_START_MODE).

## Précisions obtenues de Loto-Québec et prises en compte

- **Courriel** : le « code » est le matricule ; le préfixe d'environnement (`dev-08-v2_`) est optionnel côté destination et accepté. Les adresses utilisant un autre identifiant sont une erreur d'anonymisation du jeu de test, conservée dans la détection à leur demande (faible priorité).
- **Libellé de rôle** : un préfixe différent du code emploi est une erreur, signalée comme écart (faible priorité).
- **Date d'effet de l'affectation** : la destination applique la règle transformée ; les écarts correspondants sont justifiés.

## Méthode (rappel)

Niveau 1 : comparaison normalisée · Niveau 2 : règles métier du `Mapping.xlsx` (jointures Motif et Détail du poste) · Niveau 3 : IA pour les cas ambigus (détecteurs de motifs, scikit-learn, Gemini) · Expert : corrections apprises. Détails : [README](../README.md) · démo en ligne : https://louisbarbonet.github.io/CorroborAI/
