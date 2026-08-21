---
title: À propos
toc: false
---

<!--
  Page ÉCRITE, comme l'accueil : aucun JSON lu dans le navigateur, aucun calcul à
  l'affichage. C'est la page qu'un visiteur ouvre pour décider s'il peut citer un
  graphique d'ici — elle doit donc répondre sans dépendre de rien, et rester lisible même
  si l'export Python n'a pas tourné.

  UNE exception, et elle va dans l'autre sens : les lignes du tableau des sources sont
  ÉCRITES ICI par web/export/sources_table.py, entre les marqueurs « hm:sources ». Le
  fichier reste donc du HTML statique — c'est ce que lisent les robots d'aperçu de
  partage, qui n'exécutent aucun JavaScript — tout en portant des dates à jour. Ne pas
  modifier ces lignes à la main : le prochain export les remplacerait. Pour changer un
  libellé, une adresse ou une périodicité, éditer SOURCES dans sources_table.py.
-->

# À propos

<div class="hm-lead">

HousingMarket est un baromètre indépendant du marché du logement français : il rassemble
les séries publiques qui décrivent la construction neuve, les ventes dans l'ancien, les
prix et le crédit, les met à la même échelle de temps, et en tire une prévision des
transactions à 12-18 mois.

</div>

## Pourquoi ce site

Suivre le marché du logement suppose de lire une dizaine de séries qui ne sont ni publiées
au même endroit, ni au même rythme, ni dans le même format : les permis de construire
viennent du SDES, les ventes dans l'ancien de l'IGEDD, les prix de l'INSEE, les taux de la
Banque de France et de la BCE. Chacune est disponible ; l'assemblage, lui, est à refaire à
chaque fois.

Ce site fait cet assemblage une bonne fois, publiquement, avec des conventions de calcul
identiques d'une page à l'autre — puis va jusqu'au bout de l'exercice : plutôt qu'un
commentaire de conjoncture, il publie une prévision datée, avec son score et son
incertitude, que le temps qui passe suffit à contredire.

## La méthode, en bref

**La prévision est estimée en deux étages.** Le premier explique le taux de crédit
immobilier par les taux de marché (OAT 10 ans, Euribor 3 mois). Le second explique les
transactions de logements par ce taux de crédit, les intentions d'achat des ménages et le
chômage — chacun pris avec un décalage, parce qu'une décision d'achat ne se lit dans les
volumes que plusieurs mois plus tard.

**Les décalages sont cherchés sur la seule fenêtre d'entraînement.** C'est le point qui
décide de la valeur du reste : chercher le meilleur décalage sur l'historique complet
reviendrait à choisir ses paramètres en regardant les réponses, puis à s'auto-évaluer sur
la même copie. La recherche en grille s'arrête donc à la date de coupure, et la période
qui suit ne sert qu'à noter le résultat.

**Le score est affiché, pas résumé.** La page Prévision montre le backtest hors
échantillon, le R² du modèle et une bande d'incertitude autour de la projection. Un
expander permet de déplacer un décalage à la main et de voir le R² bouger : la recherche
automatique reste auditable.

**Ce qui est projeté est distingué de ce qui est observé.** Tant que les indicateurs
décalés qui alimentent le modèle sont déjà publiés, la projection n'a besoin d'aucune
hypothèse ; au-delà, elle prolonge ces indicateurs et le graphique le signale. Le panneau
de scénarios sert à explorer l'après, pas à le prédire.

## D'où viennent les données

Toutes les séries sont publiques et officielles. Elles sont récupérées par un script
versionné qui interroge les API d'origine, ne réécrit un fichier que si son contenu a
réellement changé, et garde la trace de chaque récupération.

Chaque intitulé renvoie à la page du producteur : c'est là que se lisent la définition
exacte de la série, sa méthodologie et ses révisions. La dernière colonne donne le dernier
point **publié par la source**, tel qu'il était au dernier rafraîchissement du site — pas
la date du jour. Les rythmes de publication et les délais diffèrent d'un producteur à
l'autre, donc ces dates ne s'alignent pas, et c'est normal.

<div class="hm-sources-wrap">
<table class="hm-sources">
  <thead>
    <tr><th>Ce qui est mesuré</th><th>Producteur</th><th>Voie d'accès</th><th>Dernier point</th></tr>
  </thead>
  <tbody>
    <!-- hm:sources:début — lignes régénérées par web/export/sources_table.py -->
    <tr><td><a href="https://www.data.gouv.fr/datasets/logements-autorises-et-commences-nombre-et-surfaces-series-mensuelles-donnees-estimees-1">Logements autorisés et commencés (SIT@DEL)</a></td><td>SDES</td><td>API DiDo (data.gouv.fr)</td><td class="hm-when">juin 2026</td></tr>
    <tr><td><a href="https://www.data.gouv.fr/datasets/donnees-nationales-sur-la-commercialisation-des-logements-neufs">Commercialisation des logements neufs (ECLN)</a></td><td>SDES</td><td>API DiDo (data.gouv.fr)</td><td class="hm-when">T1 2026</td></tr>
    <tr><td><a href="https://www.igedd.developpement-durable.gouv.fr/prix-immobilier-evolution-a-long-terme-a1048.html">Ventes de logements anciens</a></td><td>IGEDD</td><td>Classeur publié</td><td class="hm-when">juin 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/010567059">Prix des logements anciens</a></td><td>Notaires-INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">T1 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/010751595">Prix des logements neufs</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">T1 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001587668">Confiance des ménages</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">juillet 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001616794">Intentions d'achat de logement</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">juillet 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001688527">Taux de chômage au sens du BIT</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">T2 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001586954">Activité du second œuvre (rénovation)</a></td><td>INSEE — enquête de conjoncture</td><td>API SDMX (BDM)</td><td class="hm-when">juillet 2026</td></tr>
    <tr><td><a href="https://data.ecb.europa.eu/data/datasets/MIR">Taux et volume des crédits nouveaux à l'habitat</a></td><td>Banque de France / BCE</td><td>API SDMX (MIR)</td><td class="hm-when">juin 2026</td></tr>
    <tr><td><a href="https://data.ecb.europa.eu/data/datasets/BLS">Demande de crédits habitat (enquête BLS)</a></td><td>BCE / Banque de France</td><td>API SDMX (BLS)</td><td class="hm-when">T3 2026</td></tr>
    <tr><td><a href="https://data.ecb.europa.eu/data/datasets/FM">Euribor 3 mois</a></td><td>BCE</td><td>API SDMX (FM)</td><td class="hm-when">juillet 2026</td></tr>
    <tr><td><a href="https://data.ecb.europa.eu/data/datasets/IRS">OAT 10 ans</a></td><td>BCE</td><td>API SDMX (IRS)</td><td class="hm-when">juillet 2026</td></tr>
    <!-- hm:sources:fin -->
  </tbody>
</table>
</div>

Ces données sont réutilisées au titre de la
[Licence ouverte / Etalab](https://www.etalab.gouv.fr/licence-ouverte-open-licence/). Les
producteurs cités ne sont ni auteurs ni relecteurs de ce site : les erreurs d'assemblage,
d'interprétation ou de calcul n'engagent que lui.

## Comment le site est fabriqué

Le calcul est en Python ; l'agrégation des séries passe par une seule couche SQL (DuckDB
sur des fichiers Parquet), pour que le tableau de bord, le rapport PDF et ce site affichent
les mêmes chiffres par construction plutôt que par coïncidence. Chaque requête est comparée
automatiquement à une implémentation de référence indépendante : si les deux divergent, les
tests échouent.

Les cinq premières pages sont des fichiers statiques régénérés par la chaîne Python à
chaque publication de données ; les deux dernières interrogent une petite API HTTP, parce
qu'elles relancent un calcul à chaque question posée. Le site lui-même est statique et
n'a besoin d'aucun serveur pour être consulté.

**Un automate rafraîchit les sources chaque lundi**, ne committe que les fichiers
réellement modifiés, et déclenche la reconstruction du site dans la foulée.

## Limites à connaître

- **Chiffres nationaux.** Aucune ventilation régionale ni départementale : les séries
  retenues sont celles de la France entière.
- **Des rythmes de publication différents.** Les permis et les ventes dans l'ancien sont
  mensuels, la commercialisation du neuf est trimestrielle, et chaque source a son propre
  délai. Une page ne s'arrête donc pas toutes séries confondues à la même date.
- **Une prévision reste une prévision.** Elle est publiée avec sa bande d'incertitude
  précisément parce qu'elle se trompera ; elle ne constitue pas un conseil en
  investissement, ni une recommandation d'achat ou de vente.
- **Le site n'est disponible qu'en français**, alors que le tableau de bord d'origine est
  bilingue.
- **Vos propres données ne quittent pas votre navigateur.** Le fichier de ventes que la
  page Données permet de charger est lu localement : il n'est envoyé ni à l'API, ni à
  l'hébergeur, et rien n'en est conservé.

## Qui écrit

Ce site est un travail personnel de Baptiste Soulard : le code, les données et la méthode
sont publics, et c'est la seule garantie qu'il offre — tout y est vérifiable.

<div class="hm-actions">
  <a class="hm-btn hm-btn--primary" href="https://github.com/baptistesoulard/housing-market">Le code sur GitHub</a>
  <a class="hm-btn" href="https://github.com/baptistesoulard/housing-market/issues">Signaler une erreur</a>
</div>

<!--
  À COMPLÉTER par l'auteur : un lien de contact direct (profil LinkedIn, adresse
  courriel). Volontairement laissé vide plutôt que rempli au jugé — publier une adresse
  personnelle sur une page publique est une décision qui appartient à son propriétaire,
  et un lien de contact faux vaut moins que pas de lien du tout. Modèle :

  <a class="hm-btn" href="https://www.linkedin.com/in/…">Me contacter sur LinkedIn</a>
-->
