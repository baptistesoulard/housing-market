# Le site public : pages, Synthèse, marchés, référencement

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

## Le site public — ce qui doit rester vrai

Le front est passé de tableau de bord déployé à **site destiné à être partagé** (LinkedIn
et consorts). Dix pages : `/` est désormais une page d'accueil RÉDIGÉE, la Synthèse a
glissé à `/synthese`, `/a-propos` porte méthode, sources et limites, et
`/previsions-passees` publie l'archive des prévisions (voir la section suivante).

**`site.config.js` est la source unique d'identité.** Adresse publique, titre et
description de chaque page, ordre de la navigation, logo. Il est lu par le `<head>`
(`observablehq.config.js`), par `scripts/postbuild.mjs` et par `tests/test_web_seo.py` :
ajouter une page là la fait apparaître d'un coup dans la barre latérale, dans le sitemap et
dans les tests. `observablehq.config.js` ne porte plus que le RENDU — ne pas y redéclarer
de navigation.

**L'accueil et À propos doivent rester en HTML rendu au build.** C'est leur seule raison
d'être : les sept pages de données construisent leur contenu dans le navigateur à partir
des JSON, et **aucun aperçu de partage n'exécute de JavaScript** (LinkedIn, Slack et
WhatsApp récupèrent la page depuis leurs serveurs). Ces deux pages sont donc le seul texte
du site que ces robots lisent. Le bloc dynamique de l'accueil (pastilles, fraîcheur) est un
aperçu : s'il ne s'affiche pas, la page doit encore dire ce qu'elle a à dire. Déplacer son
propos dans un bloc ```js le rendrait invisible là où il compte.

**Le chapeau des pages de données est STATIQUE — titre compris.** Les huit pages de
données montent leur contenu dans le navigateur à partir des JSON ; le titre valait
`# ${neuf.title}`, ce qui livrait littéralement `<h1></h1>` dans le HTML construit. Toutes
les pages du site sauf l'accueil et À propos étaient donc, pour un moteur de recherche ou
un aperçu de partage, des pages **sans titre** — et l'accroche située juste dessous,
`<div class="hm-caption">${neuf.caption}</div>`, était vide pour les mêmes raisons. Chaque
page porte désormais un titre écrit en clair, suivi de deux paragraphes rendus au build,
avant la première section.

Trois conséquences à tenir :

- **Le chapeau doit rester PÉRENNE : aucun chiffre.** Rien ne le régénère — ni
  `web_export.py`, ni le workflow hebdo. Un nombre écrit là se figerait au jour où il a
  été tapé, et vieillirait en silence sur la seule partie de la page que les robots
  lisent. C'est l'inverse du tableau des sources d'À propos, qui porte des dates
  précisément parce qu'une chaîne Python les y réécrit.
- **Les champs `title` et `caption` des JSON du front ne sont plus lus par le site.** Ils
  restent produits par `web_export.py` : les retirer ferait diffuser un diff sur les sept
  fichiers, alors que le compteur « n/7 fichier(s) modifié(s) » ne vaut que par son
  pouvoir d'alerte. À nettoyer dans une passe qui régénère les JSON délibérément, pas au
  détour d'une édition de texte. `how_to_read` reste, lui, bel et bien consommé — il
  remplit le repli « Comment lire cette page », qui reste dynamique.
- **Ne jamais reconvertir un titre ou un chapeau en interpolation.**
  `tests/test_web_structure.py` refuse un `# ${…}` et exige au moins quarante mots de
  texte réellement statique avant la première section (les `${…}` sont retirés du compte,
  puisqu'ils sont vides dans le HTML livré). Le seuil est bas exprès : il attrape la page
  muette, pas la page brève.

**La bande de chiffres de l'accueil est écrite en dur, et c'est le corollaire du point
précédent.** Les quatre nombres du bandeau (`<ul class="hm-stats">` dans `index.md`) sont
l'équivalent honnête des « logos clients » d'un site commercial : ils doivent rassurer en
deux secondes, donc être lus par les robots de partage, donc rester statiques. Trois sont
des constantes de fait ; le quatrième — l'erreur moyenne à 6 mois — bouge à chaque
publication et est **verrouillé par `tests/test_web_links.py`**, qui le compare au KPI
d'`archive.json` et échoue s'il dérive. Le même test exige que l'erreur naïve soit citée à
côté : publier le chiffre du modèle seul laisserait croire qu'il bat la référence à tous
les horizons, ce qu'il ne fait pas en deçà de 4 mois.

**Le tableau des sources d'À propos est ÉCRIT dans le Markdown par Python.** Même
contrainte que la bande de chiffres, résolue dans l'autre sens. La page doit rester
statique, mais ses treize lignes portent le dernier point publié de chaque série, qui bouge
à chaque rafraîchissement — trop souvent pour être reporté à la main, et invisible aux
robots s'il était rempli par un bloc ```js. `web/export/sources_table.py` déclare les
sources (intitulé, page du producteur, voie d'accès, dataset, colonnes, périodicité) et
réécrit les `<tr>` entre les marqueurs `hm:sources` d'`a-propos.md` ; `web_export.py`
l'appelle en fin de `main()`, **hors du compteur « n/7 »** (ce n'est pas un JSON du front,
et le compteur vaut par son pouvoir d'alerte). Trois conséquences : ne jamais éditer ces
lignes à la main ; `a-propos.md` figure dans le `git add` du workflow hebdo, sans quoi la
page de provenance figerait ses dates à la dernière publication manuelle ;
`tests/test_web_sources.py` échoue si les dates dérivent, si un lien ne suit plus `SOURCES`
ou si une colonne renommée fait afficher « — » — le mode de panne silencieux de ce tableau.

Une ligne = **une page source et une périodicité**. C'est ce qui a fait éclater les lignes
groupées d'origine : « confiance, intentions d'achat, chômage BIT » n'a ni un lien (trois
pages INSEE) ni une date (les deux premières sont mensuelles, le chômage BIT trimestriel).
Quand une ligne garde plusieurs colonnes, la date affichée est la **plus ancienne** des
dernières observations : c'est la borne jusqu'à laquelle la ligne est vraiment complète.

**Le bandeau ne déborde PAS de la colonne, volontairement.** Un vrai bord-à-bord
supposerait des marges négatives calculées sur les marges « auto » de
`#observablehq-main`, qui varient avec la largeur de fenêtre et avec la barre latérale :
le premier écran étroit ferait glisser la page latéralement. Le fond plein suffit à
produire la rupture. Ses couleurs sont DÉRIVÉES des jetons (`color-mix` sur `--hm-ink` et
`--hm-brick`) — aucune valeur hexadécimale n'entre dans `observablehq.config.js`. Le
bouton principal du bandeau est BLANC et non brick : blanc sur brick plafonne à 3,9:1,
sous le seuil de 4,5:1.

**Le CSS du thème vit dans un littéral gabarit JS.** Un accent grave dans un commentaire
CSS referme la chaîne et fait échouer le build sur une erreur de syntaxe sans rapport
apparent (`Unexpected token ':'`, pointant une ligne de prose). Ne jamais citer un
sélecteur entre accents graves dans ce fichier.

**Le `<head>` porte une garde de rechargement (`RELOAD_GUARD`, 2026-09-19).** Le runtime
d'Observable attrape LUI-MÊME l'échec d'un `import()` de module (`client/main.js` :
`reject` → `inspectError`) : aucune `unhandledrejection` ne sort, l'erreur est écrite
dans le DOM en `.observablehq--error` à la place du graphique. La garde est donc un
`MutationObserver` sur ces nœuds, pas un écouteur de promesse — la première version
envisagée n'aurait jamais tiré. Elle recharge la page **une fois** par onglet et par
chemin (`sessionStorage`, fenêtre de dix minutes) quand le texte est « Failed to fetch
dynamically imported module » ou ses variantes Firefox/Safari : le HTML revient avec les
noms de modules du jour. Vérifié sur une page volontairement cassée servie en local :
deux requêtes exactement (charge + un rechargement), puis 20 s sans nouvelle navigation
alors que l'erreur persiste — pas de boucle. **Elle n'aide pas Google**, qui ne recharge
jamais : elle protège un visiteur dont le navigateur tient un HTML d'avant un déploiement.
Côté indexation, la réponse est le chapeau chiffré de `postbuild.mjs` (voir les pages
départementales). Le script est du JS sans accent grave, pour la raison du paragraphe
précédent ; `test_chaque_page_porte_la_garde_de_rechargement` le vérifie sur chaque page.

**Aucune URL d'hébergement en dur.** Les balises Open Graph et l'URL canonique exigent des
adresses ABSOLUES ; elles viennent de `HM_SITE_URL` (variable d'environnement Cloudflare
Pages), avec pour repli le domaine de production lui-même. Un test injecte une
adresse différente du repli et vérifie que tout suit — c'est ce qui empêche une URL de se
figer dans le code. Une adresse fausse ne casse aucune page : elle casse silencieusement
l'aperçu au partage et le référencement.

**La page `/mentions-legales` existe depuis le 2026-09-03, et elle est hors barre
latérale.** `nav: false` dans `site.config.js` : servie, indexée, présente au sitemap, mais
absente de la navigation de contenu — on cherche des mentions légales en pied de page, et
`FOOTER` (dans `observablehq.config.js`) porte le lien. Comme l'accueil et À propos, elle
est **entièrement statique** : une page qui engage l'éditeur ne doit pas dépendre d'un
runtime pour exister.

Ce qu'elle a corrigé au passage, et qui comptait plus que la page elle-même :

* **L'encart du formulaire affirmait que les messages n'étaient « ni transmis à qui que ce
  soit ».** Faux : ils transitent par Cloudflare (qui exécute la fonction) et par Resend
  (qui achemine le courriel), tous deux aux États-Unis. Sur un site dont tout l'argument est
  « je dis exactement ce que je fais », c'était la phrase la plus coûteuse du dépôt. Les
  deux sous-traitants sont désormais nommés, sur la page ET sous le formulaire.
* **Toutes les sources n'étaient pas sous Licence ouverte / Etalab.** Les séries de la BCE
  relèvent de ses propres conditions. Corrigé dans le pied de page, sur À propos et sur la
  page de mentions légales.
* **Le chapeau de « Données & Sources » promettait un état de fraîcheur série par série que
  la page n'a jamais porté** — le tableau vit sur À propos, où `sources_table.py` réécrit
  ses dates. Le chapeau y renvoie maintenant. On ne duplique PAS le tableau : deux tableaux
  de fraîcheur finiraient par ne plus dire la même date.

⚠️ **Les coordonnées de l'hébergeur sont la seule information de ce dépôt que rien ne peut
vérifier automatiquement.** Elles sont recopiées à la main depuis Cloudflare et signalées
comme telles par un commentaire en tête de la page. À revérifier si Cloudflare déménage.

**Pas de `seoTitle` sur cette page, et c'est mesuré :** le gabarit ajoute déjà
« | Baromètre du Logement » à `og:title`, si bien qu'un `seoTitle` reprenant le nom du site
le sortait DEUX FOIS. Un `seoTitle` ne se justifie que quand le libellé de navigation est
muet hors contexte — c'est le cas d'« À propos », pas de « Mentions légales ».

**Le dépôt porte un `LICENSE` MIT depuis le 2026-09-03.** Il n'en avait aucun, alors que la
vignette de partage et la description de l'auteur annonçaient « code ouvert » : un dépôt
public sans licence est juridiquement « tous droits réservés », donc la mention était
inexacte sur la surface vue par le plus de monde. La licence couvre le **code** ; les
données restent sous les conditions de leurs producteurs, et les textes rédigés du site
restent à leur auteur — la page de mentions légales le dit explicitement.

**Le formulaire de contact est le SEUL code serveur du site.**
`web/observable/functions/api/contact.js` est une Cloudflare Pages Function, exécutée
parce qu'elle est dans `functions/` à la racine du projet Pages — tout le reste de `dist/`
est servi par un CDN, sans processus derrière. Ce n'est pas l'API Flask de `api/` (qui
expose des calculs et n'est pas hébergée) : cette fonction ne calcule rien, elle valide
quatre champs et relaie vers Resend. Ne pas fusionner les deux.

**L'adresse de destination ne doit JAMAIS entrer dans le dépôt.** Il est public : une
adresse personnelle dans un fichier versionné est moissonnée exactement comme un
`mailto:`. Elle vient de `CONTACT_TO` (variable d'environnement Cloudflare), avec
`RESEND_API_KEY` ; sans l'une des deux la route répond **503** et la page le dit, plutôt
que de remercier sans rien envoyer. C'est aussi pourquoi la page porte un formulaire et
non un lien courriel. Les trois variables sont documentées dans `web/README.md`.

**Le formulaire est du HTML statique, le bloc ```js ne fait que le brancher.** Même
raison que pour le reste de la page — les robots d'aperçu ne l'exécutent pas — mais
surtout : si ce script échoue, le visiteur voit encore les champs et la mention
`<noscript>` au lieu d'un trou. La route n'existe pas sous `npm run dev` (les Pages
Functions ne tournent que chez Cloudflare ou sous `wrangler pages dev`), donc un envoi
depuis la préversion affiche « l'envoi a échoué en route » : c'est attendu.

**L'anti-spam est un pot de miel plus un délai, sans service tiers ni énigme imposée** (un
test que l'humain doit résoudre écarte aussi des humains). Le champ caché l'est **hors
écran**, jamais par `display:none` que les robots savent sauter ; et la page transmet la
**durée** écoulée depuis son chargement, pas l'heure de celui-ci — confronter l'horloge du
visiteur à celle du serveur jetterait en silence les messages de toute machine mal réglée.

**`scripts/postbuild.mjs` pose ce qu'`observable build` ne pose pas** : `lang="fr"` sur un
`<html>` que le framework écrit NU (WCAG 3.1.1, aucun réglage offert), un lien d'évitement,
`favicon.svg`, `sitemap.xml` et `robots.txt`. Il est **idempotent** et prend son répertoire
de sortie en argument (les tests le lancent sur un `dist/` jetable). Réécrire du HTML après
coup n'est pas élégant : c'est la seule prise disponible tant que le framework n'expose pas
ces réglages.

**La vignette `assets/og-image.png` est committée, pas construite.** Cloudflare ne
construit que du Node et la produire demande un navigateur ; `npm run og-image` la
régénère à la main (Playwright, hors dépendances du site). Elle vit hors de `src/` parce
que les fichiers que le framework copie reçoivent un nom haché, incompatible avec l'URL
absolue qu'annonce `og:image`.

**La fenêtre du momentum dépend de la SÉRIE, pas du goût (2026-08-26).** La Synthèse
publiait pour ses trois séries le même « X % sur les 3 derniers mois vs les mêmes mois
n-1 ». C'est le bon outil sur une série brute et le mauvais sur les deux autres.

SIT@DEL est chargée en `NAT_SERIES == "CVS-CJO"` ([data_manager.py:289](data_manager.py:289)) :
elle est DÉJÀ corrigée des variations saisonnières et des jours ouvrables. Or comparer aux
mêmes mois de l'an dernier n'a qu'une raison d'être — neutraliser la saisonnalité. Sur une
série déjà corrigée, la comparaison ne neutralise rien et importe gratuitement une base
vieille de douze mois, dont le bruit devient tout le signal. Mesuré sur les mises en
chantier à juin 2026 : l'indicateur affichait **+28,4 %** (dont ~8 points dus au seul creux
d'avril-juin 2025, base 6 % sous la moyenne de l'année) et venait de perdre **13,8 points
en un mois** — la sortie du pic de mars 2026 de la fenêtre — pendant que la tendance
12 mois bougeait de 0,3 point. La même série lue **séquentiellement** disait **−2,0 %** :
le rythme avait cessé de monter. La page publiait un gros chiffre vert au moment exact où
la dynamique se retournait.

L'IGEDD est l'inverse : reconstruite en différenciant un cumul 12 mois, ses flux mensuels
sont très bruités — le séquentiel y saute de **10 points par mois** en moyenne (contre 1,6
pour le cumul 12 mois). Sa lecture honnête reste le niveau 12 mois, complété par
`ana.plateau_months`, qui dit depuis quand ce niveau ne bouge plus : « +5,2 % sur un an »
décrivait une croissance **arrêtée depuis décembre 2025**, ce qu'un taux annuel à base
basse ne peut pas dire.

D'où deux régimes, portés par `ana.ADJUSTED_SEQUENTIAL` / `ana.RAW_TWELVE_MONTHS` et
`ana.headline_momentum`. **Le choix vit dans `analysis.py` et non dans les surfaces**,
précisément pour qu'`app.py` et `web_export.py` ne puissent pas en retenir un chacune.
`momentum_metrics` renvoie désormais aussi `last3_seq` ; `last3_yoy` reste calculée (les
onglets Neuf/Ancien l'affichent encore dans `_yoy_kpi`) mais n'est plus publiée par la
Synthèse. Chaque carte porte les DEUX horizons — momentum, puis tendance 12 mois : publier
l'un sans l'autre laisse croire qu'un retournement de trimestre efface une année.

**Le pilier « Neuf » ne moyenne plus ses deux étages, et c'est le point porteur.** La règle
précédente faisait `(permis + chantiers) / 2` sur deux taux de croissance de séries
d'ampleurs différentes. Au-delà de l'objection arithmétique, elle DÉTRUISAIT l'information
utile : les permis sont l'amont (ce qui alimente les chantiers 12 à 18 mois plus tard), les
mises en chantier l'aval (ce qui consomme des matériaux aujourd'hui). En juin 2026 la
moyenne rendait « +9,7 % → 🟢 en reprise » là où les permis reculaient de 9,8 % et les
chantiers de 2,0 %. `ana.pillar_neuf` nomme la divergence (« amont en repli ») et la
`kind` alimente la puce « à retenir », seul endroit où le mécanisme — l'aval tourne sur le
stock d'autorisations déjà délivrées — peut être écrit en toutes lettres. Corollaire tenu
dans la foulée : la puce « Demande second œuvre » lit l'**amont** pour son horizon 12-18
mois, plus le statut agrégé — sinon l'aval, qui décrit le présent, masque le signal du
futur.

`ana.SEQ_TOL = 2.0` est plus large que le ±1 des taux annuels, et pour une raison mesurée :
le 3 mois séquentiel saute de 5,2 pt par mois sur les permis et de 3,5 pt sur les chantiers.
À ±1 la pastille changerait de couleur au bruit. Cinq tests de `tests/test_logic.py`
verrouillent l'ensemble, dont une **contre-épreuve** explicite : amont −10, aval +30 (la
moyenne dirait « up ») doit rendre `amont_repli` et jamais `up`.

**Le chapeau statique de la Synthèse porte la méthode, donc il devait bouger aussi.** Il
annonçait « les trois derniers mois comparés à la même période un an plus tôt » — devenu
faux. Comme tout chapeau du site il reste sans aucun chiffre (rien ne le régénère) ; il
décrit les deux horizons, les deux régimes et le refus de moyenner, en toutes lettres.

**Une carte porte le momentum ET l'altitude, sur deux lignes séparées (2026-08-26).**
Corriger la fenêtre du momentum a rendu la pente juste et laissé le niveau muet — or les
deux mènent à des décisions différentes. `ana.level_context` situe le cumul 12 mois par
rapport à une décennie de marché ordinaire et par rapport à toute son histoire. Mesuré :
les mises en chantier sont **23 % sous la normale 2010-19** et **plus basses que 91 % des
mois depuis 2000** (9ᵉ percentile — 29 mois sur 307 seulement ont fait moins bien ;
annualisé, ce serait la 3ᵉ pire année sur 26). La même carte annonce « tendance 12 mois
+16,7 % ». Les deux sont vrais : c'est un rebond de creux, pas une reprise, et seul le
second fait dimensionne un outil industriel. À l'inverse, les ventes anciennes sont **17 %
AU-DESSUS** de cette normale alors que leur pastille est orange — le code couleur porte le
momentum, la seconde ligne porte le niveau, et il fallait les deux.

`ana.LEVEL_REF_YEARS = ("2010", "2019")` est **choisi, pas trouvé** : exclut 2004-2007 (la
bulle de crédit, dont le pic mettrait une barre que le marché n'a jamais retrouvée) et
l'après-2020 (Covid puis choc de taux, c'est-à-dire l'anomalie qu'on veut mesurer). Les
deux lignes restent SÉPARÉES à l'affichage (`sub` et `level` dans le JSON, deux
`.hm-card-sub` sur le front, deux `st.caption` dans `app.py`) : les fondre les mettrait
sur le même plan alors qu'elles répondent à deux questions.

**Le bloc « Perspective » publie la prévision DU SITE, plus la cible d'un tiers.** Il
affichait « ventes 12 m vs cible BPCE 2026 » : le même 954 k que la carte d'activité, en
**vert** parce qu'il dépasse la cible d'une banque, à un écran de la même valeur en
**orange**. Un seul nombre, deux jugements. Et « infléchissement attendu » était une chaîne
codée en dur, déclenchée par le simple dépassement du seuil, adossée à aucune prévision —
elle coïncidait avec le modèle par hasard. La carte porte désormais la projection à six
mois, sa fourchette et son taux de bon sens mesuré ; le titre du bloc est construit depuis
les CHAMPS du verdict, jamais par découpe de sa phrase (`sentence` est faite pour être lue,
sa forme peut changer). Repli sur la comparaison BPCE si le modèle n'est pas calibrable :
le bloc ne reste jamais vide.

`_shared_verdict` mémoïse `_verdict` pour la durée du process, parce que **deux pages en
ont maintenant besoin** — la Synthèse et « Prévision & Scénarios ». Le recalculer de chaque
côté rejouerait l'ajustement complet pour aboutir au même nombre, et surtout rien ne
garantirait qu'il le reste. Preuve que la mémoïsation est neutre : `previsions.json` est
resté **inchangé** au passage de `_verdict(payload["projection"], con)` à
`_shared_verdict(con)`.

**L'ECLN aussi est CVS-CJO, et elle a suivi.** Le premier correctif n'avait traité que
SIT@DEL et laissé la carte ECLN en « vs même trimestre un an plus tôt » — le défaut exact
qu'on venait de retirer, sur une série de même nature. Elle se lit maintenant d'un
trimestre au précédent (−4,8 % contre −2,1 % publié), avec la tendance sur quatre
trimestres dans le rôle du cumul 12 mois. **Trois séries corrigées des variations
saisonnières sur le site : permis, mises en chantier, ECLN. Aucune ne doit être comparée à
n-1.**

**Ce qui n'a délibérément PAS été mirroré dans `app.py` : le verdict du modèle.** Les
points « niveau » et « ECLN » y sont (helpers purs, aucun risque) ; la carte de projection
non, et la Synthèse d'`app.py` garde sa carte BPCE. Raison : `app.py` n'importe pas
`api.engine`, et l'y importer ajouterait un second moteur de prévision dans un process
Streamlit multi-sessions — exactement la surface de concurrence que l'invariant « une
requête = un curseur » documente comme ayant déjà produit un bug de production. **Défaut
préexistant découvert au passage, à traiter à part** : l'onglet Prévision d'`app.py` appelle
`fc.forecast_path(...)` **sans `anchor` ni `band`**, là où `api.engine.projection()` passe
les deux. `app.py` publie donc déjà une projection non recalée et à bande constante, c'est-
à-dire des chiffres différents de ceux du site. Ce n'est pas une régression introduite ici,
mais c'est la vraie raison pour laquelle brancher le verdict sur `app.py` demande une passe
dédiée : il faudrait d'abord aligner son moteur.

**Les blocs de la Synthèse sont rangés par HORIZON, plus par source (2026-08-26).**
« Activité / Financement / Perspective » regroupait ce qui vient du même fichier — le plan
mental du producteur. Un lecteur qui décide va du présent vers l'avenir, d'où quatre blocs
dans cet ordre, sur les deux surfaces :

| Bloc | Ce qu'il répond | Cartes |
|---|---|---|
| Aujourd'hui — ce qui se construit et se vend | ce qui consomme des matériaux maintenant | chantiers, ventes anciennes, **stock neuf à vendre** |
| Le carnet — ce qui est déjà autorisé, 12-18 mois | ce qui est engagé | permis, **taux de transformation**, réservations ECLN |
| Ce qui pilote la suite | les entrées du modèle | taux, demande de crédit, accessibilité |
| Où va le marché | la sortie du modèle | projection, rénovation, échéance aides |

Les conditions de financement passent **juste avant** la projection : ce sont ses entrées,
on lit les causes avant le résultat.

**Les deux cartes ajoutées sont les deux ponts qui manquaient**, et toutes deux existaient
déjà ailleurs sur le site :

* **Taux de transformation permis → chantiers**, 78,0 % contre 84,8 % de moyenne depuis
  2000. Sans lui, « 376 k permis » se lit comme 376 k chantiers à venir. À taux habituel
  les permis des douze derniers mois donneraient **319 k chantiers, soit 25 794 logements
  de plus qu'aujourd'hui**. Il ne prévoit rien (voir `NEUF_GATE` : permis → chantiers a été
  mesuré puis réfuté), il décrit ce que les promoteurs font de leurs autorisations.
  `_taux_transformation` est **partagée** par `build_synthese` et `_transformation` : deux
  calculs séparés du même pont finiraient par ne plus tomber sur la même valeur.
* **Stock de logements neufs à vendre**, 124 027, et surtout **22 mois pour l'écouler
  contre 15 en moyenne — 53 % de temps de plus**. ⚠️ `DelaiEcoulement` est publié en
  **TRIMESTRES** : 7,5 se lit 22 mois, pas 7,5. J'ai fait l'erreur en cours de session et
  elle change tout le diagnostic (sept mois de stock est sain, vingt-deux ne l'est pas) —
  les deux surfaces multiplient donc explicitement par 3, avec le commentaire qui le dit.
  Cette carte se lit **à l'envers des autres** : un stock qui s'écoule lentement est ce qui
  FAIT reculer les mises en vente, donc les chantiers de demain. Son statut vient du délai
  comparé à sa moyenne longue, jamais de la variation du stock.

**Le chapeau de la Synthèse est passé de ~350 à ~95 mots.** Il avait absorbé, correctif
après correctif, toute la justification méthodologique — deux régimes de momentum, le refus
de moyenner, le niveau, la projection. C'est le bon contenu au mauvais endroit : un
dirigeant ne lit pas quatre paragraphes de méthode avant de voir un chiffre. Tout est
conservé dans `how_to_read`, derrière le repli « Comment lire cette page ». Le seuil de
`test_web_structure.py` (≥ 40 mots statiques) reste largement tenu. Conséquence à ne pas
oublier : `how_to_read` est une interpolation depuis le JSON, donc **invisible aux robots**
— raccourcir le chapeau réduit réellement le texte indexé, et c'est un arbitrage assumé en
faveur du lecteur.

**Les puces « à retenir » sont le niveau de lecture le plus CHER de la page, et elles
avaient pris du retard.** Trois pastilles pour un coup d'œil, quatre puces pour trente
secondes, douze cartes pour le détail : un dirigeant lit les deux premiers niveaux et ne
descend au troisième que si quelque chose l'accroche. Or le générateur de puces ne lisait
que neuf variables, toutes antérieures aux correctifs — **quatre familles de faits
n'atteignaient pas le niveau 2** : le stock (22 mois), le taux de transformation
(25 794 chantiers manquants), les niveaux (23 % sous la normale) et la projection (−4 %).
La puce vedette disait « la maison individuelle pure : +8,3 % », vrai mais secondaire, et
taisait les deux ans de stock invendu.

Les puces suivent désormais les quatre blocs. Deux points de méthode à tenir :

* **La puce 1 sépare l'ancien du neuf** au lieu de les fondre : ils n'alimentent pas les
  mêmes lignes de produits, et ils ne disent pas la même chose — l'ancien est haut mais
  figé, le neuf est bas et sous stock. Son statut vient des deux VOLUMES du présent, pas
  du stock : celui-ci est un avertissement à l'intérieur de la puce, pas de quoi peindre
  tout le présent en rouge.
* **Chaque moitié tient en une phrase.** Les puces sont passées de 133 à 169 mots pour
  quatre familles de faits en plus ; une première version en faisait 209 et annulait la
  marche entre le résumé et le détail. Ce qui reste sur les cartes : le taux annuel, le
  percentile, l'explication du plateau, la fourchette de la projection.

**Un chiffre juste peut dire l'inverse de ce qu'il veut dire.** La carte du taux de
transformation annonçait « les permis donneraient 319 k chantiers, soit 25 794 logements
**de plus** qu'aujourd'hui ». Arithmétiquement exact, et lu comme une bonne nouvelle :
l'œil accroche « de plus » et comprend croissance, alors que le fait est un MANQUE causé
par un taux de conversion dégradé. Elle énonce maintenant le déficit dans le bon ordre —
« au taux habituel, les permis auraient donné 319 k chantiers **au lieu de** 293 k :
25 794 manquent à l'appel ». À vérifier sur tout écart publié : le signe arithmétique et
le signe ressenti doivent pointer dans le même sens.

**Un contrefactuel n'a pas sa place dans une puce, et la référence du taux de conversion
était contaminée (2026-08-26).** La puce 2 portait « 25 794 manquent à l'appel ». Trois
défauts, à ce niveau de lecture :

1. c'est **la seule quantité des puces qui ne s'est jamais produite** — tout le reste est
   observé, et le lecteur ne fait pas la différence à la vitesse d'une puce ;
2. **précision fantaisiste** : l'écart-type du taux de conversion vaut 4,9 points, ce qui
   déplace l'écart de **±18 328 logements**. Cinq chiffres significatifs sur une grandeur
   connue au millier près ;
3. **le nombre dépend de la fenêtre de référence** — 25 794 / 27 684 / 29 963 selon
   qu'on prend 2000-2026, 2010-19 ou 2001-2022 — et ça ne se voit pas.

La puce ne porte donc plus que **les deux taux** (« seulement 78 % des permis deviennent
des chantiers, contre 85 % dans les années 2010 »). C'est la RUPTURE qui parle, et elle
est franche : le taux tenait entre **85,0 et 87,7 %** sur les quatre sous-périodes de 2001
à 2022, crise de 2008 comprise, avant de tomber à **77,8 %** sur 2023-2026. Le contrefactuel
reste sur la CARTE, où un lecteur descendu jusque-là a le temps de le lire comme tel —
arrondi au millier (`_arrondi_millier`) et avec sa fenêtre nommée.

**Correctif de fond dans la foulée : la référence du taux de conversion est passée de
« moyenne depuis 2000 » (84,8 %) à `ana.LEVEL_REF_YEARS` (85,3 %).** L'ancienne englobait
la rupture de 2023-2026 qu'on cherche précisément à mesurer : **l'anomalie diluait sa
propre référence** et se faisait paraître plus petite. C'est exactement la faute que
`LEVEL_REF_YEARS` a été écrite pour éviter côté niveaux. J'avais d'abord classé cette
double convention « cosmétique, 0,5 point » — vrai sur le nombre, faux sur la méthode.

⚠️ La page « Marché du neuf » garde, elle, `TR.moyenne` = moyenne sur tout l'historique :
c'est légitime là-bas (une ligne de moyenne tracée sur le graphique de toute la série,
labellisée comme telle) et ce n'est pas la même question qu'un contrefactuel. **Les deux
chiffres coexistent donc, mais chacun NOMME sa fenêtre** — « en moyenne sur 2010-19 » d'un
côté, « moyenne de long terme » de l'autre. Ne jamais publier l'un des deux sans sa
fenêtre : c'est ce qui rend la coexistence honnête plutôt qu'incohérente.

**Règle générale sortie de là : le signe arithmétique et le signe RESSENTI doivent pointer
dans le même sens.** Aucun test ne l'attrape. Et sa contrepartie : ne pas retourner une
formulation juste pour frapper plus fort — dire « 22 % des permis ne sortent pas de terre
contre 14 % avant » (+57 % en relatif) plutôt que « 78 % contre 85 % » (−9 %) décrit le
même fait et double l'impression. C'est un choix rhétorique, il revient à l'auteur du
site, pas au générateur.

**Divergence assumée sur la puce 4.** Le site y publie la projection (« ventes anciennes
projetées en recul d'environ 4 % d'ici décembre 2026 ») ; `app.py` retombe sur l'état des
transactions, faute de verdict — même raison que pour sa carte de Perspective, documentée
plus haut. Le code a **une seule forme** (le second membre prend le verdict s'il existe,
sinon le repli), c'est la donnée qui manque d'un côté, pas la logique.

**La SURFACE est dans l'entrepôt depuis le 2026-08-31, pas encore publiée (lot A).**
`data_manager.py` ne parsait que `LOG_AUT` / `LOG_COM` ; il rend désormais aussi
`SurfacePermis` / `SurfaceChantiers` (ex-`SDP_AUT` / `SDP_COM`, surface de plancher en m²).
Or les matériaux suivent les m², pas le nombre de logements : à juin 2026, 293 412 logements
commencés pour **22,3 M m²**, soit **−31 % vs la moyenne 2010-19 en surface contre −23 % en
logements**.

**L'explication écrite ici était FAUSSE, et la mesure l'a corrigée.** Ce fichier attribuait
les huit points d'écart au logement moyen qui rétrécit (85,2 → 76,1 m²). C'est marginal.
Décomposition de la baisse des surfaces commencées : **−23,3 pt de VOLUME, −5,5 pt de MIX,
−2,8 pt de TAILLE**. Les deux tiers de l'écart invisible sont un effet de COMPOSITION —
l'individuel pur (121 m²/logt) est passé de 33,1 % à 25,0 % des chantiers pendant que les
résidences (47 m²/logt) passaient de 6,7 % à 14,7 %. La preuve tient en un contraste : à
type figé l'écart m²/logements ne dépasse jamais 3,8 pt (individuel pur −42,2 % en logements
contre −45,7 % en m²), alors qu'agrégé il atteint 7,9 pt. **Un écart agrégé plus grand que
tous ses écarts par composante EST la signature d'un effet de mix** — le vérifier coûte une
ligne et évite d'écrire la mauvaise cause.

⚠️ **Les séries CVS-CJO de surface ne sont PAS additives ; celles de compte le sont.** Sur
les 318 mois communs, la somme des 4 types reproduit exactement le « Tous Logements » publié
pour `LOG_AUT`/`LOG_COM` (0,00 %), mais s'en écarte de −0,16 % (`SDP_AUT`) et **−0,81 %**
(`SDP_COM`) en cumul 12 mois, et jusqu'à **11 % sur un mois isolé** : le SDES désaisonnalise
l'agrégat de surface indépendamment de ses composantes. L'entrepôt garde la SOMME DES 4
TYPES, comme pour les comptes — c'est ce qui rend le total cohérent avec les ventilations
individuel/collectif publiées à côté. Conséquence : nos m² sont ~0,8 % sous le chiffre que le
SDES affiche pour la France entière, et ce n'est pas un bug. Documenté au point de parse.

**Ce que le lot A n'a PAS coûté, et pourquoi.** `queries.py` n'a pas bougé d'une ligne :
`q.monthly()` prend des colonnes arbitraires, donc `q.monthly(con, "sitadel",
["SurfaceChantiers"], (12,))` a marché dès que le Parquet a porté la colonne. `read_frames()`
rend toujours SIX frames — aucun déballage positionnel touché. Les seuls fichiers modifiés
sont le parse, le contrat pandera, `analysis.aggregate_sitadel` (qui somme désormais les
colonnes PRÉSENTES et non une liste figée, puisqu'elle est l'implémentation de référence des
tests de parité), et deux fixtures de test — dont `tests/test_housing_data.py`, qui casse dès
qu'une colonne déclarée manque, ce qui est précisément le rôle du contrat.

**Preuve que le lot est inerte côté publication** : `python web/export/web_export.py` annonce
toujours `0/7` et `0/102`. Aucune surface ne lit encore les m² — les publier est le lot B, qui
doit porter l'effet de mix et non le seul total de m².

**Reste au backlog : le TERTIAIRE (lot C).** `Données mensuelles nationales - Locaux` (DiDo
`375988c5-9886-4cdc-9c09-1594d4ec27c4`, licence ouverte, **CVS-CJO**, 2013-01 → 2026-07) est
le jumeau exact du fichier logements, même API que `build_sitadel`. Il n'est pas marginal :
**20,98 M m² commencés sur 12 mois contre 22,50 pour les logements — 51 % de la surface
adressable, que le site ne voit pas**. Il ne bouge pas comme le logement (−15,5 % vs 2013-19
contre −31 %) et il se scinde : entrepôt **+12,0 %**, bureau **−33,1 %**, industrie −13,3 %
en chantiers mais **+34,5 % en autorisations**. Deux pièges : ne PAS l'ajouter au tuple de
`read_frames()` (le piège du retrait de `revenue` — `web_export.py` déballe par position,
`forecast_archive.py` lit l'index `[2]`), le lire par SQL uniquement ; et la série démarre en
**2013**, donc `ana.LEVEL_REF_YEARS = ("2010","2019")` ne s'y applique pas — chaque chiffre
doit nommer sa fenêtre, comme le taux de transformation le fait déjà.

**Les correctifs de la Synthèse ont été propagés aux deux pages de marché (2026-08-27).**
Ils y étaient restés absents, et c'était le pire endroit pour ça : le **+28,4 %** qui a
motivé toute la révision de la Synthèse était **toujours publié en carte de tête de
« Marché du neuf »**, c'est-à-dire sur la page qu'on ouvre pour zoomer. Trois choses ont
changé sur les deux pages, via `_yoy_kpi` :

* **momentum selon le régime** (`ana.headline_momentum`) — séquentiel sur SIT@DEL et ECLN,
  12 mois sur l'IGEDD, complété par le plateau ;
* **le sous-titre « Mensuel : X (Y % YoY) » perd son YoY.** Sur ces séries CVS il saute de
  **11,2 points par mois** sur les permis et **9,0** sur les chantiers — six dernières
  valeurs des chantiers : `+21 +19 +49 +32 +46 +12`. Du bruit en carte de tête. Le NIVEAU
  du dernier mois reste, c'est un fait ;
* **une ligne de NIVEAU** sur chaque KPI, y compris les 15 sous-ensembles de
  `kpis_by_type`.

**La section « Individuel vs Collectif » est celle où la correction change le plus une
décision.** Son chapeau désigne l'individuel comme « le driver de volume le plus direct »
d'un fabricant de second œuvre, et la page l'affichait à **+40,0 %**. Les deux lectures
s'inversent :

| Mises en chantier | ancien affichage (3 m vs n-1) | séquentiel | niveau vs 2010-19 |
|---|---|---|---|
| Maison individuelle pure | +40,0 % | +8,3 % | **−42 % · 7ᵉ centile** |
| Individuel total | +32,9 % | +7,1 % | −37 % · 8ᵉ centile |
| Collectif | +25,8 % | **−6,9 %** | −12 % · 36ᵉ centile |

La croissance la plus forte est sur le segment le plus effondré (rebond de plancher), et
le segment le moins dégradé est celui qui vient de se retourner. Chaque carte porte donc
ses deux lignes, et le chapeau de la section dit que c'est l'écart entre elles qui décide
d'un arbitrage de lignes de produits.

**« 📅 Comparaison Mensuelle par Année » a quitté le socle des jumelles et la page du
neuf.** Elle ne voulait pas dire la même chose des deux côtés — mesuré sur 2015-2026 :

| série | amplitude saisonnière résiduelle |
|---|---|
| Permis (CVS-CJO) | 6,9 % |
| Chantiers (CVS-CJO) | 7,8 % |
| Ventes anciennes (brut) | **38,6 %** |

Sur l'ancien, comparer juin à juin neutralise une vraie saisonnalité : le graphique fait
son travail. Sur le neuf, il comparait des mois **déjà désaisonnalisés** — donc du bruit,
en invitant à lire une saisonnalité que la source a déjà retirée. `SOCLE` dans
`tests/test_web_structure.py` passe donc à **deux** sections, le renvoi jumeau
correspondant disparaît des deux côtés, et le chapeau de la section côté ancien explique
pourquoi elle n'a pas de jumelle. **Le socle garantit la symétrie de FORME, pas celle du
sens : quand les deux divergent, c'est le sens qui gagne.** Le payload `monthly` de
`neuf.json` est parti avec la section (318 lignes de données mortes), ainsi que les
imports `monthlyByYear` / `MONTHS_FULL` / `MONTHS_SHORT` de `neuf.md`.

**La page de DÉTAIL ne doit jamais en dire moins que la page de survol.** Le délai
d'écoulement ECLN était affiché « 22 mois » tout court sur « Marché du neuf » pendant que
la Synthèse disait déjà « 22 mois · 15 en moyenne — 53 % de temps de plus ». Les quatre
KPI ECLN portent désormais leur momentum séquentiel, et le délai sa référence longue.

**`kpiCard` (`components/hm.js`) rend ses sous-lignes en `<ul>` dès qu'il y en a DEUX**,
comme les cartes de la Synthèse — empilées en `<div>` nues, deux phrases longues qui
wrappent toutes les deux deviennent indiscernables. Une seule sous-ligne reste une `<div>` :
une puce isolée ne sépare rien.

**Ce que l'ancien reste incapable de dire, et c'est structurel.** Pour un industriel des
matériaux, le marché de l'ancien n'est pas un débouché : c'est censé être le signal amont
de la **rénovation**, qui n'a pas de page (elle est un bloc de « Environnement &
Financement »). Or le pont a été mesuré le 2026-08-27 et il ne tient pas : la corrélation
entre la croissance 12 mois des transactions et le solde d'opinion rénovation monte de
+0,16 à +0,25 entre 0 et 18 mois de décalage puis redescend — **plate, faible, sans pic**,
le profil même qui a fait réfuter permis → chantiers. ⚠️ Caveat qui interdit d'en faire une
réfutation publiée : la série rénovation est un **solde d'opinion**, pas un volume, donc le
test est faible par construction. Il ne montre pas que le lien n'existe pas, il montre
qu'on ne sait pas le voir avec ce qu'on a.

**Le texte statique ne doit porter ni chiffre NI ÉTAT (2026-08-27).** La règle « aucun
chiffre dans un chapeau » était connue ; il lui manquait sa moitié. Un chapeau peut geler
le présent **sans écrire un seul nombre** — et c'est plus difficile à repérer, puisqu'il n'y
a rien à `grep`. Deux cas trouvés en auditant les trois onglets, tous deux sur `neuf.md` :

* le chapeau de « Individuel vs Collectif » disait « l'individuel pur remonte vite depuis un
  plancher historique ; le collectif [...] son rythme des trois derniers mois s'est
  retourné ». Vrai en août 2026, faux dès que le collectif repart — et la page aurait alors
  affirmé le contraire de ses propres cartes, qui sont régénérées ;
* le chapeau ECLN disait « le délai d'écoulement — **proche de deux ans** — » : un chiffre
  écrit en toutes lettres, donc figé au jour où il a été tapé.

Les deux énoncent désormais le **mécanisme** (« une croissance forte sur douze mois décrit
parfois un rebond depuis un plancher », « le temps qu'il faudrait pour vendre le stock au
rythme actuel ») et laissent la valeur aux cartes. **Test à faire avant d'écrire une phrase
statique : serait-elle encore vraie dans un an ?** Si la réponse dépend des données, la
phrase appartient au générateur, pas au Markdown.

**Ce qui est régénéré, et ce qui ne l'est pas.** Le workflow hebdo enchaîne
`fetch_new_sources.py` → `forecast_archive.py --record` → `web_export.py` → commit. Donc :

| | régénéré chaque semaine | à maintenir à la main |
|---|---|---|
| Valeurs, momentum, niveaux, plateau, pastilles, puces « à retenir », titres de blocs (verdict compris), cartes ECLN, taux de transformation, graphiques | ✅ | |
| Chapeaux de page et de section, `how_to_read` (chaînes littérales dans `web_export.py`) | | ⚠️ |
| `NEUF_GATE`, `REFUTATIONS`, `BENCHMARK_FNAIM`, `BENCHMARK_TAUX`, `BPCE_*`, `actualites.NEWS_ITEMS` + `MAJ` | | ⚠️ **datés exprès** |

La troisième ligne est un choix documenté (résultats de méthode, relevés externes), pas un
oubli — mais elle vieillit : `actualites.MAJ` avait **six semaines de retard** au moment de
cet audit, et sept au 2026-09-02. La deuxième ligne, elle, n'a toujours aucune garde.

**La troisième en a une depuis le 2026-09-03**, dans `tests/test_actualites.py` :
`test_la_veille_n_est_pas_perimee` échoue au-delà de `MAJ_MAX_JOURS = 120`, et
`test_il_reste_une_echeance_a_venir` refuse une veille dont tous les jalons sont passés.
Ces deux tests échouent **par le seul passage du temps** — inhabituel, et assumé : c'est
précisément le mode de panne qu'on veut attraper, et rien d'autre ne peut le signaler. Le
second est la contrepartie du correctif du filtre : depuis qu'il se compare au jour courant,
une veille entièrement échue ne produit plus de carte du tout, sans erreur ni trou visible.

**`MAJ` n'est plus l'horloge des échéances (corrigé le 2026-09-02).** Le filtre des jalons
comparait à `actu.MAJ` — la date de dernière RELECTURE de la veille — et non au jour de la
publication. Conséquence mécanique : toute échéance tombant entre les deux restait annoncée
comme « prochaine » alors qu'elle était passée. Constaté en publiant le 2026-09-02, avec
« Prochaine échéance : 09/2026 — suppression des forfaits monogestes », datée du 1ᵉʳ. Le
site publiait donc du passé au futur, sur la seule carte de la Synthèse qui regarde devant.

`web_export._jalons_a_venir` porte désormais le filtre pour les deux surfaces qu'il
alimente (Synthèse et Actualités), et `app.py` a le même dans `_AUJOURDHUI` — les deux
doivent dire la même date, c'est la règle habituelle des surfaces jumelles. **`MAJ` reste
inchangée et reste affichée** : elle dit quand un humain a relu la veille, ce qui est une
information réelle et distincte ; elle n'avait simplement pas à servir d'horloge. Dans la
foulée, le chronogramme d'`app.py` traçait sa ligne sur `MAJ` en l'annotant
« Aujourd'hui », pendant que sa propre légende disait « date de la dernière revue » — la
ligne reste où elle est, l'annotation dit maintenant « Dernière revue ».

**Neuf et ancien sont des pages JUMELLES : trois sections communes, même intitulé, même
ordre.** « 🔑 Chiffres Clés », « 📊 Courbes d'évolution du marché », « 📅 Comparaison
Mensuelle par Année » ouvrent les deux pages ; chacune ajoute ensuite ce qui lui est propre
(individuel/collectif et ECLN d'un côté, prix et accessibilité de l'autre). C'est ce socle
qui permet d'apprendre la page une fois et de la relire de l'autre côté — « Dynamique
Individuel vs Collectif » s'intercalait au milieu et a été déplacé APRÈS pour le rétablir.
Chaque section du socle porte un renvoi vers sa jumelle (`.hm-shortcuts--twin`), et les
deux ancres coïncident parce que les deux titres coïncident.

Rien dans le build ne protège cette symétrie : renommer une section d'un seul côté casse
l'ancre visée d'en face **sans faire échouer le build** — la validation de liens
d'Observable Framework ne regarde pas les fragments. D'où `tests/test_web_structure.py`,
qui vérifie le socle, son ordre, les renvois et l'existence des ancres visées, en pur
Python (ni Node ni build requis).

**Le sommaire de page (`toc`) est construit AU BUILD à partir des `<h2>` du Markdown.** Un
titre posé par ``display(html`<h2>…`)`` n'y figure JAMAIS : c'est pourquoi les sections
conditionnelles de `macro.md` portent un titre Markdown statique et affichent un encart
« série absente » plutôt que rien — un titre suivi de vide se lit comme une panne. Le
défaut reste `toc: false` dans la config, chaque page l'active dans son front-matter, et
l'accueil s'en abstient délibérément (page d'atterrissage, dont « Les huit pages » EST déjà
la navigation). Un test refuse qu'une page ait des sections sans sommaire, ou l'inverse.

**Le sommaire ne s'affiche qu'à partir de 1320 px, et c'est un correctif, pas un réglage.**
Le framework le montre dès 1216 px en réservant 208 px de gouttière sur `main` : mesuré à
1250 px, la colonne de contenu tombait de 817 à 659 px et les `.hm-panels` (minmax 340 px)
passaient de deux colonnes à une. Or ces panneaux sont **appariés pour être comparés**
(encours vs délai d'écoulement, capacité d'emprunt vs accessibilité) — et 1280×800 comme
1366×768 tombent en plein dans cette bande. Deux règles sont donc à défaire, pas une : le
sommaire ET sa gouttière (`#observablehq-toc ~ #observablehq-main`), faute de quoi la
colonne reste étroite pour rien. En dessous du seuil, ce sont les renvois entre jumelles
qui assurent la navigation par section.

**Une légende cliquable est un `<button aria-pressed>`, jamais un `<span onclick>`.** Le
barré et l'opacité ne disent l'état qu'à ceux qui les voient ; un `span` n'est atteignable
ni au clavier ni au lecteur d'écran. Les deux légendes du site (`components/hm.js` et
`synthese.md`) sont des boutons dont le CSS neutralise l'apparence — le rendu n'a pas
changé.

**L'encart `.hm-api-offline` a changé de sens le 2026-08-23.** Prévision et Données ne
dépendent plus d'un serveur HTTP (voir « L'API HTTP » plus haut) : un visiteur externe
les voit désormais fonctionner, comme les six autres pages. L'encart subsiste, mais pour
un cas bien plus rare — `available: false` dans `previsions.json`, c'est-à-dire un
modèle non calibrable à la dernière publication hebdomadaire (macro incomplète), pas un
serveur injoignable. `python -m api` reste utile pour explorer les mêmes routes en
local, mais plus aucune page n'en a besoin pour s'afficher.

**« À qui ça sert » met le particulier AVANT le professionnel, depuis le 2026-08-23.**
L'ordre inverse — « il s'adresse à qui doit anticiper une activité liée au logement »
en premier, « et à qui veut simplement suivre le marché » en second — était un cadrage
B2B pour un site dont la bande de chiffres, la courbe d'accroche et depuis le retour des
pages départementales le sélecteur « Et chez vous ? » parlent tous à un particulier.
Le paragraphe professionnel n'a pas été supprimé, seulement rétrogradé en second. Le
même changement a retiré l'encart « Deux pages ont besoin d'un serveur » : il décrivait
une limite que le passage de Prévision/Données au statique (voir « L'API HTTP ») a fait
disparaître — le laisser aurait été une régression documentaire, pas juste une
imprécision.

**Un sigle porte un `<abbr title>` sur sa PREMIÈRE occurrence par page, jamais toutes.**
`SIT@DEL`, `ECLN`, `IGEDD`, `DVF`, `OAT`, `Euribor`, `BLS`, `BIT`, `backtest` sont ainsi
annotés dans le chapeau statique de chaque page où ils apparaissent en premier — un
soulignement pointillé (`abbr[title]` dans `observablehq.config.js`), pas un composant
JS : les chapeaux sont du texte statique (voir plus bas), et `<abbr>` est du HTML brut,
valide directement dans le markdown. Annoter CHAQUE occurrence aurait criblé le texte de
pointillés pour un gain marginal — la définition complète, plus longue, vit dans le
repli « Le vocabulaire » d'À propos, entre « D'où viennent les données » et « Comment le
site est fabriqué ». Un terme qui apparaît seulement dans du contenu JS-rendu (les
libellés de cartes KPI, par exemple `R²`) n'est PAS annoté : le composant `dfn()`
envisagé au départ a été abandonné une fois vérifié que la quasi-totalité du jargon vit
dans des chapeaux statiques, où un `<abbr>` brut suffit sans dépendance JS.

## Les m² — logements (lot B) et locaux non résidentiels (lot C), 2026-09-26

**Pourquoi.** Un des publics du site fabrique des matériaux : il vend au m², pas au
logement ni à la transaction. Demande de l'auteur, avec le tertiaire en priorité. Deux lots
restés au backlog depuis le 2026-08-31 (plus haut) ont donc été livrés ensemble. Chiffres
ci-dessous : données SIT@DEL à juillet 2026, millésime DiDo 2026-08.

**Ce qui a été écarté d'abord : les m² dans l'ancien.** Mesuré sur DVF (surface
approchée par prix médian ÷ prix médian au m², pondérée par les ventes, par type) : la
surface moyenne d'une vente reste entre 70,3 et 73,5 m² de 2014 à 2025. Des « m² vendus »
vaudraient donc les ventes × ~72 à ±2 % près — une courbe qui recopierait celle des
ventes. Et des m² VENDUS ne sont pas des m² RÉNOVÉS : le signal rénovation du site reste
l'enquête INSEE second œuvre (page Environnement). Pas de m² sur la page de l'ancien.

**Lot B — les m² de logements, section « En m² : ce que voient les matériaux » du neuf.**
Sur 12 mois contre 2010-19 : −30,7 % en m² commencés contre −22,8 % en logements ; en
permis −27,7 % contre −18,0 %. `mesures.decomposition_surface` factorise EXACTEMENT
M1/M0 = volume × mix × taille, convertis en points enchaînés : chantiers −22,8 / −5,3 /
−2,6 pt, permis −18,0 / −4,1 / −5,5 pt. Deux lectures à retenir : sur les chantiers,
l'écart invisible (≈ 8 pt) est aux deux tiers un effet de MIX — l'individuel pur passe de
32,9 % à 25,1 % des logements commencés, les résidences de 6,8 % à 14,6 % — ce qui
confirme la correction du 2026-08-31 ; sur les PERMIS, en revanche, la TAILLE domine
(l'individuel pur autorisé passe de 121 à 106 m² par logement). La phrase publiée est
rédigée par l'export, dans le sens de la donnée : « recule de 30,7 % » et non « recule
de -30,7 % » (double négation relevée au premier rendu), la glose sur la maison
individuelle n'est dite que si ce type porte la contribution la plus négative au mix
(vérifié, pas supposé), et les libellés des barres sont neutres (« Mix — répartition
entre les types ») pour ne pas mentir le jour où un effet change de signe. La section
ignore le sélecteur de types, exprès : elle mesure leur mélange. Les indices (base 100 =
2015) sont exportés en colonnes : une ligne par point faisait passer neuf.json de 602 à
766 Ko, 639 Ko en colonnes.

**Lot C — les locaux, page dédiée « Construction non résidentielle » (`/non-residentiel`).**
Page et non section du neuf : le neuf parle du logement, et ni son taux de transformation
ni l'ECLN ne s'appliquent aux locaux. Source : DiDo `375988c5-…`, même API que les
logements (`fetch_new_sources.build_locaux`), dataset `locaux`, SQL seulement, hors du
tuple de `read_frames()`. Ce qu'elle dit à juillet 2026 : 21,0 M m² de locaux commencés
sur 12 mois contre 22,6 pour les logements, soit **48 % de la surface neuve** (45 % en
moyenne 2013-19) ; −16 % sous la normale 2013-19 ; entrepôts **+12 %**, bureaux −33 %,
agricole −33 %, industrie −13 % en chantiers mais **+34,5 % en autorisations**.

Les choix, tous mesurés sur la source avant d'écrire une ligne :

* **Date de prise en compte**, pas date réelle estimée (description DiDo). La note
  méthodologique Sitadel : les déclarations d'ouverture de chantier remontent « généralement
  dans les dix-huit mois ». Les m² commencés d'un mois sont donc des chantiers de l'année
  écoulée, un signal en retard et lissé ; les m² autorisés sont le signal frais. La page
  compare logements et locaux en cumul 12 mois seulement, et le dit.
* **Régime 12 mois contre 12 précédents**, pas le séquentiel des pages logement : écart-type
  mensuel des m² commencés 19,2 % (8,5 % pour les m² de logements), séquentiel à 3 mois
  ±12,5 pt. `ana.RAW_TWELVE_MONTHS` réutilisé, son commentaire élargi aux séries CVS trop
  bruitées.
* **Référence 2013-19** (`page_locaux.REF_LOCAUX`) : la série démarre en 2013.
* **Additivité — l'inverse des logements.** La somme des 4 destinations reproduit
  l'ensemble publié à 0,00 %, CVS-CJO compris (vérifié à chaque parse : un écart > 0,1 %
  casse la reconstruction et garde l'ancien dérivé). Les sous-destinations, elles, ne
  s'additionnent pas exactement à leur destination en CVS-CJO (jusqu'à 5 % sur un mois,
  0,7 % en cumul 12 mois) : zoom seulement. Le dataset porte `Niveau` ; un total se lit sur
  `Niveau = 'Destination'`, jamais en sommant toutes les lignes (tests/test_locaux.py).
* **Pas de taux de transformation** : m² commencés / m² autorisés = 66 % en 2013-19 pour
  les locaux, contre 87 % pour les m² de logements. Projets abandonnés ou ouvertures jamais
  déclarées : ces données ne séparent pas les deux. Non publié, et la page dit pourquoi.
* **Pas de prévision.** Corrélation des taux de croissance 12 mois, chantiers(t) ~
  autorisations(t−k) : pic à k = 0-3 mois sur l'ensemble (0,66), 6 mois sur les
  entrepôts (0,53), 9 mois sur l'agricole (0,53). Suggestif, sur ~12 années
  indépendantes, et JAMAIS passé par la porte d'entrée (erreur évitée hors échantillon) :
  une piste, pas un résultat. À mesurer avant toute phrase qui parle d'avance.

**Deux modes de panne rencontrés au rendu, tous deux silencieux au build :**

1. Une entrée réactive (`Generators.input`, `view`) lue dans la cellule qui la définit y
   vaut le GÉNÉRATEUR : `filterYears(rows, rangeL)` comparait des années à NaN, deux
   graphiques sur trois sortaient sans une courbe. Garde ajoutée :
   `test_une_entree_reactive_n_est_pas_lue_dans_sa_propre_cellule`.
2. Le framework RETIRE « ² » des ancres (« En m² » → `en-m-…`), là où le `_ancre` des
   tests, en NFKD, écrivait `en-m2`. Et contrairement à ce que ce fichier et le README
   disaient, le build VALIDE les fragments des liens internes — par un simple
   avertissement (« 1 broken link »), sans échouer. `_ancre` passe en NFD, la valeur
   observée est figée dans `test_l_ancre_reproduit_le_build`.

**Compteur.** Neuf JSON nationaux désormais : l'export doit annoncer `0/9`. La première
régénération a touché `previsions.json` — attendu : il porte la liste des datasets de
l'entrepôt (diagnostic), où `locaux` est apparu.
