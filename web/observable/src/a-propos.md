---
title: À propos
toc: true
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

Le Baromètre du Logement est un observatoire indépendant du marché immobilier français :
il rassemble
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
    <tr><td><a href="https://www.data.gouv.fr/datasets/logements-autorises-et-commences-nombre-et-surfaces-series-mensuelles-donnees-estimees-1">Logements autorisés et commencés (SIT@DEL)</a></td><td>SDES</td><td>API DiDo (data.gouv.fr)</td><td class="hm-when">juillet 2026</td></tr>
    <tr><td><a href="https://www.data.gouv.fr/datasets/donnees-nationales-sur-la-commercialisation-des-logements-neufs">Commercialisation des logements neufs (ECLN)</a></td><td>SDES</td><td>API DiDo (data.gouv.fr)</td><td class="hm-when">T2 2026</td></tr>
    <tr><td><a href="https://www.igedd.developpement-durable.gouv.fr/prix-immobilier-evolution-a-long-terme-a1048.html">Ventes de logements anciens</a></td><td>IGEDD</td><td>Classeur publié</td><td class="hm-when">juin 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/010567059">Prix des logements anciens</a></td><td>Notaires-INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">T1 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/010751595">Prix des logements neufs</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">T1 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001587668">Confiance des ménages</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">août 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001616794">Intentions d'achat de logement</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">août 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001688527">Taux de chômage au sens du BIT</a></td><td>INSEE</td><td>API SDMX (BDM)</td><td class="hm-when">T2 2026</td></tr>
    <tr><td><a href="https://www.insee.fr/fr/statistiques/serie/001586954">Activité du second œuvre (rénovation)</a></td><td>INSEE — enquête de conjoncture</td><td>API SDMX (BDM)</td><td class="hm-when">août 2026</td></tr>
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

## Le vocabulaire

<details class="hm-howto">
  <summary>Les sigles du site, en clair</summary>
  <div class="hm-caption">

**SIT@DEL** — le fichier du SDES qui recense les permis de construire et les mises en
chantier. Source des courbes de la page Marché du neuf.

**ECLN** — l'Enquête sur la Commercialisation des Logements Neufs, trimestrielle : ce que
les promoteurs réservent, mettent en vente et vendent, avec leur prix.

**IGEDD** — l'Inspection Générale de l'Environnement et du Développement Durable, qui
publie le suivi mensuel des ventes de logements anciens en France.

**DVF** — les Demandes de Valeurs Foncières, fichier de la DGFiP qui recense les ventes
immobilières réellement enregistrées chez le notaire. Source des 101 pages par
département.

**OAT** — l'Obligation Assimilable du Trésor à 10 ans : le taux auquel l'État français
emprunte, référence du coût du crédit à long terme, y compris immobilier.

**Euribor** — le taux auquel les banques de la zone euro se prêtent entre elles à court
terme (ici, à 3 mois). Avec l'OAT, il explique le taux de crédit immobilier dans le
modèle de ce site.

**BLS** — la Bank Lending Survey, une enquête trimestrielle de la BCE auprès des banques
sur leurs conditions d'octroi de crédit et la demande qu'elles observent.

**BIT** — le Bureau International du Travail, dont la définition standardisée du chômage
permet de comparer le taux français à celui des autres pays.

**CVS(-CJO)** — Corrigé des Variations Saisonnières (et des Jours Ouvrés) : un traitement
statistique qui retire l'effet du calendrier (mois plus ou moins longs, vacances) pour
que deux mois se comparent équitablement.

**R²** — le coefficient de détermination : la part de la variation d'une série qu'un
modèle explique, entre 0 (rien) et 1 (tout).

**MAPE** — l'erreur moyenne en pourcentage entre une prévision et ce qui s'est
réellement passé. C'est le chiffre publié sur la page Prévisions passées.

**Backtest** — un test du modèle sur des données qu'il n'a pas vues à l'entraînement :
il mesure sa valeur prédictive, pas seulement sa capacité à s'ajuster au passé.

**Base 100** — une convention d'indice où une période de référence (ici la moyenne de
l'année 2015) vaut 100 : un niveau de 110 se lit « +10 % depuis 2015 ».

  </div>
</details>

## Comment le site est fabriqué

Le calcul est en Python ; l'agrégation des séries passe par une seule couche SQL (DuckDB
sur des fichiers Parquet), pour que le tableau de bord, le rapport PDF et ce site affichent
les mêmes chiffres par construction plutôt que par coïncidence. Chaque requête est comparée
automatiquement à une implémentation de référence indépendante : si les deux divergent, les
tests échouent.

Toutes les pages du site sont des fichiers statiques régénérés par la chaîne Python à
chaque publication de données — y compris la prévision et son panneau de scénarios, qui
appliquent en JavaScript la même formule que le modèle Python à des coefficients déjà
calculés. Le site n'a besoin d'aucun serveur pour être consulté.

**Un automate rafraîchit les sources chaque lundi**, ne committe que les fichiers
réellement modifiés, et déclenche la reconstruction du site dans la foulée.

## Limites à connaître

- **Les huit pages de données sont nationales.** Aucune ventilation régionale : les
  séries qu'elles retiennent sont celles de la France entière. Seul le prix au m² a une
  déclinaison départementale (DVF), sur ses [101 pages dédiées](/departement/75) — les
  taux, le chômage et les intentions d'achat qui alimentent la prévision restent
  nationaux, faute d'équivalent local publié.
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

<!--
  SECTION AUTEUR — la seule du site qui parle d'une personne, et c'est délibéré : le sujet
  du site est le marché du logement, pas celui qui l'observe. Il n'y a donc pas de page
  dédiée, et il ne doit pas y en avoir.

  Cette section porte malgré tout l'entité `Person` du JSON-LD (voir AUTHOR dans
  site.config.js, et le nœud ProfilePage dans observablehq.config.js). Trois contraintes
  en découlent, aucune n'étant cosmétique :

  1. L'ancre `#auteur` est l'IDENTIFIANT de cette entité — c'est le `@id` que le JSON-LD
     de l'accueil référence. Elle est posée en dur plutôt que laissée à la fabrique
     d'ancres du framework : celle-ci dérive l'ancre du LIBELLÉ, si bien que reformuler le
     titre changerait silencieusement l'identifiant, et l'accueil pointerait alors vers une
     entité qui n'existe plus. Le titre garde par ailleurs son ancre auto-générée ; les
     deux coexistent.

     Le `<span>` est DANS le titre, et non sur la ligne d'avant : seul, il formerait un
     paragraphe à lui tout seul, dont la marge se verrait au-dessus du titre. Vide, il
     ne change ni le libellé du sommaire ni l'ancre auto-générée.
  2. Le nom figure dans le TITRE de section, pas seulement dans la prose. « Baptiste
     Soulard » est porté par plusieurs personnes ; un nom cité au fil d'une phrase, en bas
     d'une page dont le sujet est la méthodologie, ne suffit pas à dire que la page parle
     de lui.
  3. Les trois liens sortants sont les mêmes que le `sameAs` du JSON-LD, et ce n'est pas
     une redondance : le balisage déclare la correspondance, les liens la corroborent.
     Ajouter un profil ici sans l'ajouter à AUTHOR — ou l'inverse — casse l'appariement.
-->

## <span id="auteur"></span>Qui écrit : Baptiste Soulard

Ce site est un travail personnel de Baptiste Soulard. Il en écrit le code, choisit les
sources, arbitre les méthodes de calcul et assume les chiffres publiés : il n'y a ni
rédaction, ni comité, ni commanditaire derrière ces pages.

Passionné de **supply chain et de tech**, il applique ici des méthodes venues de la
planification industrielle : prévoir une demande, mesurer l'écart de la prévision
précédente, recommencer. Le marché du logement s'y prête mieux qu'il n'y paraît — c'est
une chaîne longue, où les permis déposés cette année sont les chantiers de la suivante et
les livraisons d'après, et où chaque maillon se mesure.

Le parti pris tient en une phrase : **tout est vérifiable, et c'est la seule garantie
offerte.** Les données viennent d'institutions publiques et sont citées une par une avec
leur date de dernière mise à jour ; le code qui les transforme est ouvert ; et chaque
prévision est archivée le jour de sa publication, puis confrontée au réalisé — y compris
quand elle a eu tort. Une erreur signalée est corrigée et datée, et c'est aussi à cela que
sert le formulaire au bas de cette page.

<!--
  `rel="me"` est le pendant HTML du `sameAs` du JSON-LD : la convention par laquelle une
  page déclare « ces profils sont moi ». Le balisage structuré l'annonce dans un langage
  que seuls les moteurs lisent ; `rel="me"` le dit dans le HTML lui-même, et il est repris
  par d'autres consommateurs (Mastodon le vérifie pour valider un lien de profil). Les
  deux doivent lister les mêmes adresses que AUTHOR.sameAs — un test le vérifie.

  Le premier lien n'en porte PAS : il mène au dépôt de ce site, qui est un projet, pas
  une identité. Le confondre avec un profil rattacherait l'entité à un dépôt.
-->
<div class="hm-actions">
  <a class="hm-btn hm-btn--primary" href="https://github.com/baptistesoulard/housing-market">Le code de ce site</a>
  <a class="hm-btn" rel="me" href="https://github.com/baptistesoulard">Son GitHub</a>
  <a class="hm-btn" rel="me" href="https://soulard-baptiste-bs.medium.com/">Ses articles sur Medium</a>
  <a class="hm-btn" rel="me" href="https://www.linkedin.com/in/baptistesoulard1994">Son LinkedIn</a>
</div>

## Me contacter

Une erreur dans un chiffre, une question sur la méthode, une source qui manque, une
remarque sur une page : ce formulaire arrive directement dans ma boîte, et je réponds à
l'adresse que vous indiquez.

<!--
  FORMULAIRE ÉCRIT EN HTML STATIQUE, comme le reste de la page — pas construit en JS.
  Deux raisons, et la seconde est la vraie :
  1. les robots d'aperçu de partage n'exécutent aucun JavaScript (voir l'en-tête) ;
  2. surtout, un formulaire monté par JS n'existe pas tant que le runtime n'a pas tourné.
     Le bloc ```js plus bas ne fait que BRANCHER l'envoi : si ce script échoue, le
     visiteur voit encore les champs et la mention <noscript>, au lieu d'un trou.

  Le POST part vers /api/contact, une Cloudflare Pages Function (web/observable/functions/
  api/contact.js). C'est le SEUL bout de serveur du site ; l'adresse de destination y est
  une variable d'environnement, jamais une valeur écrite dans le dépôt.

  Champs : nom, courriel, sujet, message — et rien de plus. Un prénom et un nom séparés
  ne serviraient à rien qu'un champ libre ne serve déjà, et chaque donnée personnelle
  collectée est une donnée à justifier, à conserver et à pouvoir supprimer.
-->

<form class="hm-form" id="hm-contact" novalidate>
  <div class="hm-field">
    <label for="hm-nom">Votre nom</label>
    <input id="hm-nom" name="nom" type="text" required maxlength="120" autocomplete="name">
  </div>
  <div class="hm-field">
    <label for="hm-email">Votre adresse de courriel <span class="hm-field-note">— pour la réponse, et rien d'autre</span></label>
    <input id="hm-email" name="email" type="email" required maxlength="200" autocomplete="email">
  </div>
  <div class="hm-field">
    <label for="hm-sujet">Sujet</label>
    <select id="hm-sujet" name="sujet">
      <option>Signaler une erreur dans les données</option>
      <option>Question sur la méthode</option>
      <option>Une source qui manque</option>
      <option>Remarque ou proposition</option>
      <option>Autre</option>
    </select>
  </div>
  <div class="hm-field">
    <label for="hm-message">Votre message</label>
    <textarea id="hm-message" name="message" required rows="6" maxlength="5000"></textarea>
  </div>
  <div class="hm-hp" aria-hidden="true">
    <label for="hm-hp">Ne remplissez pas ce champ</label>
    <input id="hm-hp" name="_hp" type="text" tabindex="-1" autocomplete="off">
  </div>
  <div class="hm-form-actions">
    <button class="hm-btn hm-btn--primary" type="submit">Envoyer</button>
    <p class="hm-form-status" role="status" aria-live="polite"></p>
  </div>
  <p class="hm-form-legal">Votre nom, votre adresse et votre message me sont transmis par
  courriel pour que je puisse vous répondre : ils ne sont ni enregistrés dans une base, ni
  utilisés à d'autres fins, ni transmis à qui que ce soit. Pour les faire effacer, il
  suffit de le demander en réponse.</p>
  <noscript><p class="hm-form-legal">Ce formulaire a besoin de JavaScript pour partir.
  Sans lui, passez par les
  <a href="https://github.com/baptistesoulard/housing-market/issues">signalements sur
  GitHub</a>.</p></noscript>
</form>

```js
// Branchement de l'envoi. La page reste utilisable si ce bloc échoue : les champs sont
// déjà dans le document (voir le commentaire au-dessus du formulaire).
const form = document.querySelector("#hm-contact");
const statut = form?.querySelector(".hm-form-status");

// Instant du chargement. Ce qui part vers le serveur est la DURÉE écoulée jusqu'à
// l'envoi, jamais cet instant : la fonction refuse un envoi parti en moins de trois
// secondes (aucun humain ne tape un message en ce temps-là, un robot si), et une durée
// se mesure ici seule, sans confronter l'horloge du visiteur à celle du serveur.
const charge = Date.now();

// Les messages d'erreur nomment CE QUI a échoué et ce que le visiteur peut faire. Un
// « une erreur est survenue » laisse croire que le message est peut-être parti.
const MESSAGES = {
  champs: "Vérifiez le nom, l'adresse de courriel et un message d'au moins dix caractères.",
  config: "La messagerie du site n'est pas joignable pour le moment. Réessayez plus tard.",
  envoi: "L'envoi a échoué en route. Réessayez dans quelques minutes.",
  reseau: "Envoi impossible — vérifiez votre connexion, puis réessayez.",
};

if (form && !form.dataset.wired) {
  form.dataset.wired = "1";
  form.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const bouton = form.querySelector("button[type=submit]");
    const champs = Object.fromEntries(new FormData(form).entries());

    // Validation côté navigateur AVANT l'envoi : elle évite un aller-retour, mais elle ne
    // remplace pas celle du serveur — le formulaire n'est pas le seul chemin vers la route.
    if (!champs.nom?.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(champs.email ?? "")
        || (champs.message ?? "").trim().length < 10) {
      statut.textContent = MESSAGES.champs;
      statut.className = "hm-form-status hm-form-status--ko";
      return;
    }

    bouton.disabled = true;
    statut.className = "hm-form-status";
    statut.textContent = "Envoi…";

    try {
      const rep = await fetch("/api/contact", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({...champs, _t: Date.now() - charge}),
      });
      const data = await rep.json().catch(() => ({}));
      if (data.ok) {
        form.reset();
        statut.textContent = "Message envoyé — merci. Je réponds à l'adresse indiquée.";
        statut.className = "hm-form-status hm-form-status--ok";
      } else {
        statut.textContent = MESSAGES[data.error] ?? MESSAGES.envoi;
        statut.className = "hm-form-status hm-form-status--ko";
      }
    } catch {
      statut.textContent = MESSAGES.reseau;
      statut.className = "hm-form-status hm-form-status--ko";
    } finally {
      bouton.disabled = false;
    }
  });
}
```
