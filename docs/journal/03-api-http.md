# L'API HTTP (`api/`)

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

## L'API HTTP (`api/`) — ce qui doit rester vrai

> **Depuis le 2026-08-23, plus aucune page du site n'appelle cette API par HTTP.**
> Prévision & Scénarios lisait `api/routes.py` en direct depuis le navigateur ; elle lit
> maintenant `previsions.json`, un septième export produit par `web_export.py` qui
> appelle `api.engine` **en important le module Python**, au build, pas au runtime (voir
> `build_previsions`). Données & Sources, qui appelait `/market/transactions-run-rate`,
> `/market/housing-types` et `/market/permits-run-rate`, dérive maintenant les mêmes
> séries de `ancien.json`/`neuf.json`, déjà publiés pour d'autres pages — aucun nouvel
> export n'était nécessaire pour celles-là. Le panneau de scénarios (quatre curseurs
> continus, un espace d'hypothèses qui ne s'énumère pas) reste un calcul CLIENT, mais en
> JS pur (`computeScenario`, `src/components/api.js`, port de `forecast.scenario`,
> vérifié par `tests/test_web_js_parity.py`) — plus un POST réseau pour huit
> multiplications.
>
> `api/routes.py`, `api/engine.py` et `tests/test_api_contract.py` restent intacts et
> testés : ce n'est pas un retrait de l'API, seulement de son appel HTTP depuis ces deux
> pages. `python -m api` reste une façon légitime d'explorer les mêmes routes en local.
> `src/components/api.js`, en revanche, a perdu tout son client HTTP (`request`,
> `apiBase`, `ApiError`, l'objet `api`, `apiOfflineNotice`) — plus rien ne l'appelait,
> et il ne porte plus que des ports JS de calculs Python (`ols1`, `shiftMonths`,
> `bestLagFit`, `computeScenario`).
>
> **Le benchmark de CA entreprise a été SUPPRIMÉ le 2026-08-24 — dataset compris.** La
> section « → Propagation au chiffre d'affaires benchmark » propageait le choc de
> transactions du panneau de scénarios vers le CA d'Hexaom et de Kingfisher France : une
> élasticité indicative estimée sur des séries d'entreprise courtes (32 et 8 trimestres),
> que personne n'utilisait. Le besoin réel est l'autre module, celui qui compare un CSV
> **importé par le visiteur** aux modèles — `bestLagFit` sur « Données & Sources », calcul
> client, le CSV ne quitte jamais le navigateur. Ne pas confondre les deux : le dataset
> `company_sales` (ventes société importées, mensuel) reste, `revenue` (CA trimestriel
> publié, versionné) est parti.
>
> Sont partis avec lui : `data/revenue.csv`, les trois fichiers `data_manual_input/ca-*`,
> `DataManager.build_revenue_from_manual_inputs`/`ensure_revenue` et l'entrée `revenue` du
> registre de chemins, le contrat pandera `REVENUE` (donc la vue SQL du même nom),
> `forecast.fit_tx_to_ca`/`best_tx_to_ca`, `simulation.resample_quarterly`/
> `find_optimal_lag_quarterly` (écrites pour cette seule série trimestrielle),
> `engine.revenue_benchmarks()` et sa route HTTP, plus la section de la page web et celle
> d'`app.py`. **`read_frames()` et `load_or_generate_all()` rendent désormais SIX frames,
> pas sept** — l'index 4 est `ecln`, plus `revenue` ; tout code qui déballe ce tuple par
> position doit être relu, c'est le seul piège de ce retrait.

Trois couches, chacune ne connaissant que la suivante :

```
web_export.py ──appel Python──► api/engine.py ──► queries.py / forecast.py
                                       ▲
                    (optionnel, local) │
                         navigateur ───┘ fetch() ──► api/routes.py
```

**`api/engine.py` n'importe pas Flask, et ne doit jamais l'importer.** C'est l'invariant
central : le moteur reste exécutable et testable serveur éteint
(`python -c "from api import engine; print(engine.rate_model()['r2'])"`) — c'est cet
invariant qui permet à `web_export.py` de l'appeler directement, en import Python, sans
passer par HTTP. Seul `api/routes.py` connaît HTTP. Un calcul qui se met à importer Flask
est un calcul rangé au mauvais endroit.

**Aucune logique métier dans `routes.py`.** Une route lit des paramètres, appelle le
moteur, sérialise. Rien d'autre.

**Une route = une question métier, pas une table.** `/api/forecast/projection` est bon ;
`/api/table/macro?filter=…` réinventerait SQL par-dessus HTTP et déplacerait la logique
dans le front.

**Le format des dates est figé à `YYYY-MM-DD`**, produit par `engine._iso` et verrouillé
par `tests/test_api_contract.py`. Une divergence (`2025-03` d'un côté, `2025-03-01` de
l'autre) ne lève pas : la requête réussit et la jointure renvoie zéro ligne.

**Pas de `NaN` dans les réponses.** `json.dumps` en produit par défaut, ce n'est pas du
JSON valide et `JSON.parse` lève côté navigateur — une seule valeur manquante casserait
la page entière sans erreur serveur. `engine._num` convertit en `null` ; un test le vérifie
sur toutes les routes.

**La concurrence est déjà traitée mais reste fragile.** Un serveur HTTP sert plusieurs
requêtes en parallèle : la règle « une requête = un curseur » de `queries.py` (voir plus
haut) est ce qui empêche deux appels simultanés de se voler leur jeu de résultats.
`tests/test_api_contract.py::test_concurrent_requests_do_not_swap_payloads` rejoue la
course sur un vrai serveur.

**Flask est optionnel.** Ni `app.py`, ni `report.py`, ni `web_export.py` n'en dépendent —
ce dernier importe `api.engine`, pas `api.routes`. Le site statique n'appelle plus l'API
du tout (voir l'encart en tête de section) ; l'encart `.hm-api-offline` qui subsiste sur
Prévision et Données ne se déclenche plus que si le modèle n'a pas pu être calibré à la
dernière publication (macro incomplète), pas si un serveur est injoignable.

**Les ventes société ne passent PAS par l'API.** Décision produit : le CSV est lu dans le
navigateur et n'est jamais téléversé. Conséquence directe — la régression qui en dépend
existe en double, en Python (`forecast.best_tx_to_monthly`) et en JS (`bestLagFit` dans
`web/observable/src/components/api.js`). `tests/test_web_js_parity.py` compare les deux sur
les mêmes données : même décalage retenu, même R². Ne pas laisser diverger.

**Les pages du front n'importent jamais `npm:` directement** : elles passent par
`src/components/hm.js`, qui réexporte `Plot`, `d3` et `csvParse`. Une seule façon de
charger une bibliothèque.

**Toute vignette de survol prend `TIP` de `hm.js`** — `Plot.tip(…, {…TIP})`, ou
`tip: {…TIP}` sur une marque. Plot dessine ses vignettes en 10 px ; sur ce site elles
portent les SEULS chiffres exacts (pas de quadrillage fin, pas d'étiquette intermédiaire),
donc la taille est remontée à 13 px. **En option de marque, jamais en CSS** : Plot mesure
le texte avec cette valeur pour dimensionner le cadre, si bien qu'un `font-size` posé en
feuille de style grossirait le texte dans une boîte restée petite, et le rognerait. Six
pages plus `hm.js` la déclarent — un nouveau graphique qui l'oublie se voit à sa vignette
deux fois plus petite que ses voisines.

**Une légende n'est pas une option de l'appelant : `multiLine` en pose une (2026-09-03).**
Le helper n'en posait aucune et il fallait que chaque appelant y pense. Sur une vingtaine
d'appels, **treize traçaient deux ou trois courbes sans que rien ne les nomme hors survol** :
prix Ensemble/Appartements/Maisons (×2 sur « Marché de l'ancien »), capacité d'emprunt vs
prix, neuf vs ancien (×2), encours vs mises en vente sur « Marché du neuf », production de
crédits cumulée, demande BLS et activité rénovation sur « Environnement & Financement »,
département vs France sur les 101 pages départementales, et le graphique d'alignement de
« Prévision & Scénarios ». Le survol donnait le nom d'une courbe à la fois — donc à
personne qui regarde la page sans la toucher, et à personne sur un imprimé.

`multiLine` prend désormais `legend = "auto"` : légende statique dès **deux séries**, sauf
si l'appelant passe `active` (il pilote alors sa propre `legend()` cliquable, et une
seconde légende inerte à côté serait absurde). `legend: false` reste pour un appelant qui
pose la sienne autrement. **Le correctif est dans le helper et non aux appels, exprès** :
un défaut qu'on ne corrige qu'au cas par cas se réintroduit au graphique suivant, et c'est
exactement ce qui s'est passé entre le 2026-08-29 (un seul graphique traité) et cette date.

Deux copies redondantes sont tombées avec : la légende manuscrite de l'accueil et le
`display(legendStatic(META_BT))` de la page de prévision.

**Un graphique à UNE série n'en reçoit pas**, et c'est voulu : le titre du panneau et
l'étiquette d'axe le nomment déjà, une légende à une entrée n'ajoute rien. Même chose pour
une droite de référence, qui porte son étiquette **dans** le graphique (« ≈ 2 ans »,
« moyenne 84,8 % ») — mieux placée là qu'en légende.

**`legendStatic()` oubliait `hm-legend--static`, et l'accueil ne l'oubliait pas.** Le
modificateur (`cursor: default`) était appliqué sur la copie manuscrite de l'accueil et
absent du helper partagé : les légendes statiques de « Prévision & Scénarios » affichaient
donc un curseur en main, promettant un clic inexistant — ce que le commentaire de ce
sélecteur dit précisément vouloir éviter. C'est le mode de panne ordinaire d'un composant
recopié : **la copie est juste, le partagé ne l'est pas, et rien ne les confronte.**
`tests/test_web_structure.py` vérifie maintenant les deux bouts du contrat (hm.js pose la
classe, le thème la déclare) — un test de nom de classe entre JS et CSS, parce qu'une
classe absente n'est pas une erreur de build, juste un style qui ne s'applique pas.

⚠️ **Rien ne teste le RENDU.** Les graphiques sont construits dans le navigateur, donc le
HTML livré ne les contient pas : aucun test Python ne peut compter les courbes d'un
graphique. Les deux tests ajoutés protègent le défaut du paramètre et le nom de la classe,
pas le résultat à l'écran. La vérification reste l'ouverture des pages dans un navigateur,
sur le site CONSTRUIT — c'est ainsi que les treize graphiques ont été recensés, puis
recomptés après correction.
