---
title: À propos
toc: false
---

<!--
  Page ÉCRITE, comme l'accueil : aucun JSON, aucun calcul. C'est la page qu'un visiteur
  ouvre pour décider s'il peut citer un graphique d'ici — elle doit donc répondre sans
  dépendre de rien, et rester lisible même si l'export Python n'a pas tourné.
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

<table class="hm-sources">
  <thead>
    <tr><th>Ce qui est mesuré</th><th>Producteur</th><th>Voie d'accès</th></tr>
  </thead>
  <tbody>
    <tr><td>Logements autorisés et commencés (SIT@DEL)</td><td>SDES</td><td>API DiDo (data.gouv.fr)</td></tr>
    <tr><td>Commercialisation des logements neufs (ECLN)</td><td>SDES</td><td>API DiDo (data.gouv.fr)</td></tr>
    <tr><td>Ventes de logements anciens</td><td>IGEDD</td><td>Classeur publié</td></tr>
    <tr><td>Prix des logements anciens et neufs</td><td>Notaires-INSEE / INSEE</td><td>API SDMX (BDM)</td></tr>
    <tr><td>Confiance des ménages, intentions d'achat, chômage BIT</td><td>INSEE</td><td>API SDMX (BDM)</td></tr>
    <tr><td>Activité du second œuvre (rénovation)</td><td>INSEE — enquête de conjoncture</td><td>API SDMX (BDM)</td></tr>
    <tr><td>Taux des crédits à l'habitat, production de crédits</td><td>Banque de France / BCE</td><td>API SDMX (MIR)</td></tr>
    <tr><td>Demande de crédits habitat (enquête BLS)</td><td>BCE / Banque de France</td><td>API SDMX (BLS)</td></tr>
    <tr><td>Euribor 3 mois, OAT 10 ans</td><td>BCE</td><td>API SDMX</td></tr>
  </tbody>
</table>

Ces données sont réutilisées au titre de la
[Licence ouverte / Etalab](https://www.etalab.gouv.fr/licence-ouverte-open-licence/). Les
producteurs cités ne sont ni auteurs ni relecteurs de ce site : les erreurs d'assemblage,
d'interprétation ou de calcul n'engagent que lui. La page
[Données & Sources](/donnees) donne la date d'arrêt de chaque série.

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
