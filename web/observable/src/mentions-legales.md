---
title: Mentions légales
toc: true
---

# Mentions légales

<!--
  PAGE ENTIÈREMENT STATIQUE, comme l'accueil et À propos, et pour la même raison : aucun
  aperçu de partage n'exécute de JavaScript, et une page qui engage l'éditeur ne doit pas
  dépendre d'un runtime pour exister. Aucun bloc ```js ici, délibérément.

  ⚠️ LES COORDONNÉES DE L'HÉBERGEUR SONT À VÉRIFIER sur la page de Cloudflare avant toute
  publication, et à corriger ici si elles ont changé : c'est la seule information de cette
  page que le dépôt ne peut pas vérifier tout seul.
-->

Cette page dit qui publie ce site, qui l'héberge, ce qu'il fait des rares données
personnelles qu'il reçoit, et sous quelles conditions ses sources sont réutilisées. Elle
est écrite en clair plutôt qu'en formules : un lecteur qui veut savoir ce que devient son
message ne devrait pas avoir à déchiffrer un paragraphe pour le découvrir.

## Éditeur

**Baptiste Soulard**, éditeur du site à titre personnel, également directeur de la
publication.

Le contact se fait par le [formulaire de la page À propos](/a-propos#me-contacter). Aucune
adresse électronique n'est écrite sur le site ni dans son dépôt : une adresse publiée en
clair est moissonnée par les robots, et le formulaire remplit exactement le même office
sans ce coût.

## Hébergement

Le site est un ensemble de fichiers statiques servis par **Cloudflare Pages**.

> Cloudflare, Inc. — 101 Townsend Street, San Francisco, CA 94107, États-Unis —
> +1 (650) 319-8930 — [cloudflare.com](https://www.cloudflare.com)

## Données personnelles

### Ce que le site ne fait pas

**Aucun cookie, aucune mesure d'audience, aucun traceur.** Le site ne charge ni Google
Analytics, ni pixel publicitaire, ni script tiers d'aucune sorte — c'est vérifiable dans
son [code source](https://github.com/baptistesoulard/housing-market). C'est aussi pourquoi
vous ne voyez aucun bandeau de consentement : il n'y a rien à consentir.

**Le fichier de ventes que vous pouvez charger sur la page Données ne quitte jamais votre
navigateur.** Il est lu localement, conservé dans le stockage de l'onglet, et tous les
calculs qui en dépendent se font sur votre machine. Rien n'est téléversé.

### Le formulaire de contact

Il recueille quatre champs : nom, adresse de courriel, sujet et message. Ils servent à une
seule chose — vous répondre — et le message part parce que vous l'avez décidé.

Deux prestataires interviennent dans cet acheminement, et il faut les nommer plutôt que de
prétendre que le message ne va nulle part :

| Qui | Ce qu'il fait | Où |
|---|---|---|
| Cloudflare, Inc. | héberge le site et exécute la fonction qui reçoit le formulaire | États-Unis |
| Resend, Inc. | achemine le courriel jusqu'à ma boîte | États-Unis |

Ces transferts hors Union européenne reposent sur les garanties contractuelles publiées
par ces deux sociétés. Aucune base de données n'est constituée : votre message vit dans
une boîte de courriel, le temps que l'échange reste utile, et il est supprimé sur simple
demande.

Cloudflare journalise par ailleurs les accès au site, adresse IP comprise, pour son
fonctionnement et sa sécurité. Ces journaux ne me sont ni transmis ni exploités.

### Vos droits

Vous disposez d'un droit d'accès, de rectification, d'effacement, d'opposition et de
portabilité sur ces données. La façon la plus simple de l'exercer est de répondre au
courriel de l'échange, ou de repasser par le formulaire. Vous pouvez également introduire
une réclamation auprès de la [CNIL](https://www.cnil.fr).

## Sources et réutilisation

Les séries publiées ici proviennent d'organismes publics, citées une à une avec leur
producteur et leur voie d'accès sur la page [À propos](/a-propos).

Les données publiques françaises — SDES (SIT@DEL, ECLN), IGEDD, DGFiP (DVF) et INSEE — sont
réutilisées au titre de la
[Licence ouverte / Etalab](https://www.etalab.gouv.fr/licence-ouverte-open-licence/). Les
séries de la **Banque centrale européenne** relèvent, elles, des
[conditions de réutilisation propres à la BCE](https://data.ecb.europa.eu/help/disclaimer-copyright).

Les producteurs cités ne sont ni auteurs ni relecteurs de ce site. Les erreurs
d'assemblage, d'interprétation ou de calcul n'engagent que lui.

Les valeurs foncières publiées par département sont des **médianes trimestrielles
agrégées** : aucune transaction individuelle, aucune adresse et aucun nom ne sont diffusés,
et le site n'a pas vocation à en diffuser.

## Ce que ce site n'est pas

Les chiffres publiés sont des mesures de séries officielles et des projections statistiques
assorties de leur incertitude. **Ils ne constituent pas un conseil en investissement, ni
une recommandation d'achat ou de vente, ni une estimation de la valeur d'un bien
particulier.**

Le site publie d'ailleurs ses propres erreurs : la page
[Prévisions passées](/previsions-passees) confronte chaque prévision au réalisé, y compris
là où le modèle fait moins bien qu'une simple reconduction du dernier chiffre connu. C'est
la mesure honnête de ce qu'on peut lui demander.

## Le code

Le code qui produit ce site est [public sur GitHub](https://github.com/baptistesoulard/housing-market),
y compris la chaîne d'acquisition des données et les tests. Il est diffusé sous
[licence MIT](https://github.com/baptistesoulard/housing-market/blob/main/LICENSE) : vous
pouvez le réutiliser, le modifier et le redistribuer, y compris commercialement, à
condition d'en conserver la mention de paternité.

Cette licence porte sur le **code**, pas sur les données : celles-ci restent soumises aux
conditions de leurs producteurs, rappelées plus haut. Les textes rédigés du site
(chapeaux, analyses, commentaires de méthode) restent la propriété de leur auteur.
