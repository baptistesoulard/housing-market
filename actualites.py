"""Veille « Actualités & Aides » — aides publiques et plans de relance logement (FR + UE).

Contenu ÉDITORIAL curaté manuellement (pas de flux automatique) : chaque entrée décrit un
dispositif ou un plan (statut, jalons, montants) et son impact POTENTIEL sur les trois
piliers du modèle de l'app (neuf = permis/ventes SIT@DEL-ECLN, ancien = transactions
IGEDD, rénovation = second œuvre). Les impacts sont des lectures qualitatives (-2..+2),
pas des sorties de modèle — ils servent de grille de lecture pour les scénarios de
l'onglet « 📡 Prévision & Scénarios ».

Mise à jour : éditer NEWS_ITEMS puis la constante MAJ. Textes bilingues {"FR": .., "EN": ..}
comme le helper _L() d'app.py. `tests/test_actualites.py` vérifie la cohérence du contenu.
"""

# Date d'arrêt de la veille (affichée dans l'onglet — à mettre à jour à chaque édition).
MAJ = "2026-07-16"

# Échelle qualitative d'impact par pilier (emoji + libellé, rendus tels quels dans l'UI).
IMPACT_LABELS = {
    "FR": {2: "⬆⬆ Soutien fort", 1: "⬆ Soutien", 0: "➖ Neutre / mitigé",
           -1: "⬇ Frein", -2: "⬇⬇ Frein fort"},
    "EN": {2: "⬆⬆ Strong support", 1: "⬆ Support", 0: "➖ Neutral / mixed",
           -1: "⬇ Headwind", -2: "⬇⬇ Strong headwind"},
}

PILIERS = {
    "FR": {"neuf": "🏗️ Neuf (permis & ventes)",
           "ancien": "🏠 Ancien (transactions)",
           "renovation": "🛠️ Rénovation (second œuvre)"},
    "EN": {"neuf": "🏗️ New-build (permits & sales)",
           "ancien": "🏠 Existing homes (transactions)",
           "renovation": "🛠️ Renovation (secondary works)"},
}

STATUTS = {
    "FR": {"vigueur": "✅ En vigueur", "adopte": "🗳️ Adopté / en déploiement",
           "discussion": "🔄 En discussion / annoncé"},
    "EN": {"vigueur": "✅ In force", "adopte": "🗳️ Adopted / rolling out",
           "discussion": "🔄 Under discussion / announced"},
}

CATEGORIES = {
    "FR": {"FR": "🇫🇷 France", "EU": "🇪🇺 Union européenne"},
    "EN": {"FR": "🇫🇷 France", "EU": "🇪🇺 European Union"},
}

# Types de jalons pour l'échéancier (symbole Plotly + libellé de légende).
JALON_TYPES = {
    "effet": {"symbol": "circle", "FR": "Entrée en vigueur", "EN": "Entry into force"},
    "jalon": {"symbol": "diamond", "FR": "Jalon", "EN": "Milestone"},
    "echeance": {"symbol": "x", "FR": "Échéance / attendu", "EN": "Deadline / expected"},
}

# Chaque item : catégorie FR/EU, statut, date de référence (tri), jalons datés pour
# l'échéancier, impacts par pilier (-2..+2), montant clé, horizon de transmission
# attendu vers l'activité, résumé + lecture d'impact, sources publiques.
NEWS_ITEMS = [
    {
        "id": "jeanbrun",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-01-01",
        "court": {"FR": "Dispositif Jeanbrun", "EN": "Jeanbrun scheme"},
        "titre": {
            "FR": "Plan « Relance Logement » & dispositif Jeanbrun (statut du bailleur privé)",
            "EN": "'Relance Logement' plan & Jeanbrun scheme (private-landlord status)",
        },
        "montant": {"FR": "≈ 12 k€/an d'amortissement max", "EN": "≈ €12k/yr max amortisation"},
        "horizon": {"FR": "6-24 mois", "EN": "6-24 months"},
        "impacts": {"neuf": 2, "ancien": 1, "renovation": 1},
        "resume": {
            "FR": "Cœur du plan gouvernemental « Relance Logement », le dispositif Jeanbrun "
                  "(du nom du ministre du Logement Vincent Jeanbrun, voté en loi de finances "
                  "2026) remplace définitivement le Pinel par un statut du bailleur privé : "
                  "amortissement annuel du bien déductible des revenus fonciers (jusqu'à "
                  "12 000 €/an en location très sociale), engagement locatif de 9 ans, "
                  "déficit foncier renforcé. Contrairement au Pinel, il s'applique **sans "
                  "zonage, sur tout le territoire**, au **neuf comme à l'ancien rénové**. "
                  "Objectifs affichés : 50 000 logements locatifs dès 2026, 400 000 "
                  "logements construits/an, 2 millions d'ici 2030.",
            "EN": "Centrepiece of the government's 'Relance Logement' plan, the Jeanbrun "
                  "scheme (named after housing minister Vincent Jeanbrun, voted in the 2026 "
                  "budget) permanently replaces the Pinel scheme with a private-landlord "
                  "status: annual amortisation of the dwelling deductible from rental income "
                  "(up to €12,000/yr for very-social rents), 9-year rental commitment, "
                  "enhanced land-deficit rules. Unlike Pinel it applies **nationwide, with "
                  "no zoning**, to **new-builds and renovated existing homes** alike. Stated "
                  "targets: 50,000 rental units from 2026, 400,000 dwellings built per year, "
                  "2 million by 2030.",
        },
        "impact_detail": {
            "FR": "Relance directe de la demande d'investissement locatif → soutien aux "
                  "réservations ECLN puis aux permis SIT@DEL (transmission 12-24 mois, cf. "
                  "lags de l'onglet Time-Lag). L'éligibilité de l'**ancien rénové** crée un "
                  "double effet : transactions IGEDD + travaux de second œuvre (menuiseries, "
                  "fermetures) sur les biens acquis pour être loués.",
            "EN": "Directly restarts rental-investment demand → supports ECLN reservations "
                  "then SIT@DEL permits (12-24-month transmission, see Time-Lag tab). "
                  "Eligibility of **renovated existing homes** creates a double effect: "
                  "IGEDD transactions + secondary-works jobs (joinery, closures) on "
                  "buy-to-let acquisitions.",
        },
        "jalons": [
            ("2026-01-01", {"FR": "Entrée en vigueur (LF 2026)", "EN": "Entry into force (2026 budget)"}, "effet"),
            ("2026-02-06", {"FR": "Adoption définitive du PLF 2026", "EN": "Final adoption of the 2026 budget bill"}, "jalon"),
        ],
        "sources": [
            ("info.gouv.fr — Relance logement", "https://www.info.gouv.fr/grand-dossier/relance-logement"),
            ("Ministère — plan Relance logement", "https://www.ecologie.gouv.fr/dossiers/plan-relance-logement"),
            ("vie-publique.fr — loi Jeanbrun", "https://www.vie-publique.fr/loi/303813-relance-logement-projet-de-loi-jeanbrun"),
        ],
    },
    {
        "id": "mpr_2026",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-07-02",
        "court": {"FR": "MaPrimeRénov' 2026", "EN": "MaPrimeRénov' 2026"},
        "titre": {
            "FR": "MaPrimeRénov' 2026 : budget 3,6 Md€, recentrage sur les rénovations d'ampleur",
            "EN": "MaPrimeRénov' 2026: €3.6bn budget, refocus on deep renovations",
        },
        "montant": {"FR": "3,6 Md€ (vs 3,4 Md€ en 2025)", "EN": "€3.6bn (vs €3.4bn in 2025)"},
        "horizon": {"FR": "0-12 mois", "EN": "0-12 months"},
        "impacts": {"neuf": 0, "ancien": 0, "renovation": 0},
        "resume": {
            "FR": "Après une suspension au 1er janvier 2026 (« pas de budget, pas de "
                  "guichet » faute de loi de finances), MaPrimeRénov' a rouvert avec la LF "
                  "2026 : budget de **3,6 Md€**, cible d'au moins **120 000 rénovations "
                  "d'ampleur** et **150 000 rénovations par geste**, priorité aux passoires "
                  "thermiques et aux ménages modestes. Réforme présentée au Conseil national "
                  "de l'habitat le **2 juillet 2026** : suppression prévue en **septembre "
                  "2026** de plusieurs forfaits monogestes (poêles biomasse, solaire "
                  "thermique/hybride hors outre-mer, PAC eau chaude sanitaire).",
            "EN": "After a suspension on 1 January 2026 ('no budget, no counter' pending the "
                  "budget law), MaPrimeRénov' reopened with the 2026 budget: **€3.6bn**, "
                  "targeting at least **120,000 deep renovations** and **150,000 single-"
                  "measure renovations**, with priority to energy sieves and low-income "
                  "households. A reform presented to the national housing council on **2 "
                  "July 2026** plans to scrap several single-measure grants from "
                  "**September 2026** (biomass stoves, solar thermal/hybrid outside "
                  "overseas territories, heat-pump water heaters).",
        },
        "impact_detail": {
            "FR": "Impact **mitigé** pour le second œuvre : le budget global progresse et "
                  "les rénovations d'ampleur (qui incluent l'isolation et les menuiseries) "
                  "restent finançables, mais la coupe des monogestes dès septembre 2026 "
                  "peut provoquer un **pic d'anticipation puis un trou d'air** sur les "
                  "familles produits concernées — à surveiller dans le pilier rénovation "
                  "du modèle de ventes.",
            "EN": "**Mixed** impact for secondary works: the overall budget grows and deep "
                  "renovations (which include insulation and joinery) remain fundable, but "
                  "cutting single-measure grants from September 2026 may cause a **pull-"
                  "forward spike then an air pocket** in the affected product families — "
                  "worth watching in the sales model's renovation pillar.",
        },
        "jalons": [
            ("2026-01-01", {"FR": "Suspension du guichet (loi spéciale)", "EN": "Counter suspended (stopgap law)"}, "jalon"),
            ("2026-02-06", {"FR": "Réouverture avec la LF 2026 (3,6 Md€)", "EN": "Reopening with the 2026 budget (€3.6bn)"}, "effet"),
            ("2026-07-02", {"FR": "Réforme présentée au CNH", "EN": "Reform presented to the housing council"}, "jalon"),
            ("2026-09-01", {"FR": "Suppression prévue des forfaits monogestes ciblés", "EN": "Planned removal of targeted single-measure grants"}, "echeance"),
        ],
        "sources": [
            ("Hellio — MaPrimeRénov' 2026", "https://particulier.hellio.com/blog/financement/maprimerenov-2026"),
            ("LeSiteImmo — réforme juillet 2026", "https://news.lesiteimmo.com/2026/07/01/maprimerenov-travaux-non-finances-reforme-2026/"),
            ("Zepros Bâti — MPR/DPE/CEE 2026", "https://bati.zepros.fr/actu-generale/maprimerenov-dpe-cee-est-2026"),
        ],
    },
    {
        "id": "ptz_2026",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2025-04-01",
        "court": {"FR": "PTZ élargi", "EN": "Extended PTZ"},
        "titre": {
            "FR": "Prêt à taux zéro élargi : tout le territoire, maison individuelle incluse",
            "EN": "Extended zero-interest loan (PTZ): nationwide, detached houses included",
        },
        "montant": {"FR": "Prorogé jusqu'à fin 2027", "EN": "Extended until end-2027"},
        "horizon": {"FR": "3-18 mois", "EN": "3-18 months"},
        "impacts": {"neuf": 2, "ancien": 1, "renovation": 1},
        "resume": {
            "FR": "Depuis le **1er avril 2025**, le PTZ est étendu à **tout le territoire** "
                  "(fin du zonage) et de nouveau ouvert à la **maison individuelle neuve**. "
                  "La loi de finances 2026 le maintient et ajuste les plafonds de ressources "
                  "et de coût d'opération pour solvabiliser davantage de primo-accédants. Le "
                  "PTZ dans l'ancien reste conditionné à des travaux (≥ 25 % du coût total) "
                  "en zone détendue. Dispositif prorogé jusqu'à fin 2027.",
            "EN": "Since **1 April 2025** the PTZ has been extended **nationwide** (no more "
                  "zoning) and reopened to **new detached houses**. The 2026 budget law "
                  "keeps it and adjusts income and cost ceilings to solvabilise more first-"
                  "time buyers. The PTZ for existing homes still requires works (≥ 25% of "
                  "total cost) in low-pressure areas. Extended until end-2027.",
        },
        "impact_detail": {
            "FR": "Principal levier de solvabilisation des primo-accédants : soutien direct "
                  "aux ventes de maisons neuves (constructeurs type Hexaom, benchmark CA de "
                  "l'app) puis aux permis. Le volet « ancien avec travaux » alimente aussi "
                  "les transactions IGEDD et le second œuvre (25 % de travaux imposés).",
            "EN": "Main solvency lever for first-time buyers: direct support to new detached-"
                  "house sales (builders like Hexaom, the app's revenue benchmark) then to "
                  "permits. The 'existing home with works' leg also feeds IGEDD transactions "
                  "and secondary works (25% works requirement).",
        },
        "jalons": [
            ("2025-04-01", {"FR": "Extension nationale + maison neuve", "EN": "Nationwide extension + new houses"}, "effet"),
            ("2026-01-01", {"FR": "LF 2026 : plafonds ajustés", "EN": "2026 budget: ceilings adjusted"}, "jalon"),
            ("2027-12-31", {"FR": "Fin de la prorogation actuelle", "EN": "End of current extension"}, "echeance"),
        ],
        "sources": [
            ("Ministère — accéder à la propriété", "https://www.ecologie.gouv.fr/acceder-propriete"),
            ("Service-Public — PTZ", "https://www.service-public.fr/particuliers/vosdroits/F10871"),
        ],
    },
    {
        "id": "donation_neuf",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2025-04-01",
        "court": {"FR": "Donations exonérées", "EN": "Tax-free gifts"},
        "titre": {
            "FR": "Exonération des dons familiaux pour l'achat neuf ou la rénovation énergétique",
            "EN": "Family-gift tax exemption for new-build purchase or energy renovation",
        },
        "montant": {"FR": "100 k€/donateur, 300 k€/bénéficiaire", "EN": "€100k/donor, €300k/beneficiary"},
        "horizon": {"FR": "0-12 mois — expire fin 2026", "EN": "0-12 months — expires end-2026"},
        "impacts": {"neuf": 1, "ancien": 0, "renovation": 1},
        "resume": {
            "FR": "Depuis le 1er avril 2025 et **jusqu'au 31 décembre 2026**, les dons "
                  "familiaux (parents, grands-parents, arrière-grands-parents) sont exonérés "
                  "de droits jusqu'à **100 000 € par donateur** et **300 000 € par "
                  "bénéficiaire**, s'ils financent l'achat d'un **logement neuf** (résidence "
                  "principale) ou des **travaux de rénovation énergétique** de la résidence "
                  "principale.",
            "EN": "From 1 April 2025 **until 31 December 2026**, family gifts (parents, "
                  "grandparents, great-grandparents) are exempt from gift tax up to "
                  "**€100,000 per donor** and **€300,000 per beneficiary** when they fund "
                  "the purchase of a **new-build main home** or **energy-renovation works** "
                  "on the main home.",
        },
        "impact_detail": {
            "FR": "Apport supplémentaire qui débloque des projets neufs et des chantiers de "
                  "rénovation. **L'échéance du 31/12/2026 devrait concentrer des ventes et "
                  "des travaux au S2 2026** (effet d'aubaine avant extinction) — possible "
                  "sur-performance temporaire des piliers neuf et rénovation, puis "
                  "contrecoup début 2027.",
            "EN": "Extra down-payment capacity that unlocks new-build projects and "
                  "renovation jobs. **The 31/12/2026 sunset should concentrate sales and "
                  "works in H2 2026** (rush before expiry) — possible temporary over-"
                  "performance of the new-build and renovation pillars, then a hangover in "
                  "early 2027.",
        },
        "jalons": [
            ("2025-04-01", {"FR": "Début de l'exonération", "EN": "Exemption starts"}, "effet"),
            ("2026-12-31", {"FR": "Fin du dispositif", "EN": "Scheme expires"}, "echeance"),
        ],
        "sources": [
            ("Lamotte — exonération dons familiaux", "https://www.lamotte.fr/conseils/exoneration-dons-familiaux/"),
            ("Médicis — PLF 2026 & immobilier", "https://www.medicis-patrimoine.com/actualites-immobilier-neuf/marche-de-l-immobilier/2026/02/06/4208-budget-le-plf-adopte-ce-qui-change-ou-pas-pour-l-immobilier.html"),
        ],
    },
    {
        "id": "dpe_2026",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-01-01",
        "court": {"FR": "Réforme DPE", "EN": "EPC reform"},
        "titre": {
            "FR": "Réforme du DPE au 1er janvier 2026 : ~850 000 logements sortent du statut de passoire",
            "EN": "EPC reform on 1 January 2026: ~850,000 homes exit 'energy sieve' status",
        },
        "montant": {"FR": "Coefficient électricité 2,3 → 1,9", "EN": "Electricity factor 2.3 → 1.9"},
        "horizon": {"FR": "0-24 mois", "EN": "0-24 months"},
        "impacts": {"neuf": 0, "ancien": 1, "renovation": -1},
        "resume": {
            "FR": "Au **1er janvier 2026**, le facteur de conversion de l'électricité dans "
                  "le DPE passe de **2,3 à 1,9** (alignement européen) : environ **850 000 "
                  "logements chauffés à l'électricité sortent mécaniquement du statut de "
                  "passoire énergétique** (F/G). Le calendrier de la loi Climat & Résilience "
                  "reste en vigueur : location interdite pour les G depuis 2025, pour les "
                  "**F au 1er janvier 2028**, pour les E en 2034. Le DPE collectif est "
                  "obligatoire pour les copropriétés ≤ 50 lots depuis 2026.",
            "EN": "On **1 January 2026** the electricity conversion factor in the French EPC "
                  "drops from **2.3 to 1.9** (EU alignment): about **850,000 electrically "
                  "heated homes mechanically exit 'energy sieve' status** (F/G). The "
                  "Climate & Resilience law calendar still applies: renting G-rated homes "
                  "banned since 2025, **F-rated from 1 January 2028**, E-rated from 2034. "
                  "Building-level EPCs are mandatory for condos ≤ 50 units since 2026.",
        },
        "impact_detail": {
            "FR": "Double lecture : la sortie de 850 000 logements du statut F/G **fluidifie "
                  "les transactions dans l'ancien** (moins de décotes, moins de ventes "
                  "contraintes) mais **réduit la pression réglementaire à rénover** ces "
                  "biens — léger frein pour le pilier rénovation. L'échéance F-2028 "
                  "maintient toutefois un flux de chantiers obligatoires.",
            "EN": "Two-sided: 850,000 homes exiting F/G status **smooths existing-home "
                  "transactions** (fewer discounts, fewer forced sales) but **eases the "
                  "regulatory pressure to renovate** them — a mild headwind for the "
                  "renovation pillar. The F-2028 deadline still sustains a pipeline of "
                  "mandatory works.",
        },
        "jalons": [
            ("2026-01-01", {"FR": "Nouveau coefficient électricité", "EN": "New electricity factor"}, "effet"),
            ("2028-01-01", {"FR": "Interdiction de louer les logements F", "EN": "Ban on renting F-rated homes"}, "echeance"),
        ],
        "sources": [
            ("Zepros Bâti — MPR/DPE/CEE 2026", "https://bati.zepros.fr/actu-generale/maprimerenov-dpe-cee-est-2026"),
            ("Ministère — le DPE", "https://www.ecologie.gouv.fr/politiques-publiques/diagnostic-performance-energetique-dpe"),
        ],
    },
    {
        "id": "cee_p6",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-01-01",
        "court": {"FR": "CEE 6e période", "EN": "CEE 6th period"},
        "titre": {
            "FR": "Certificats d'économies d'énergie : 6e période 2026-2029, obligations relevées",
            "EN": "Energy-saving certificates (CEE): 6th period 2026-2029, higher obligations",
        },
        "montant": {"FR": "P6 : 2026 → 2029", "EN": "P6: 2026 → 2029"},
        "horizon": {"FR": "0-48 mois", "EN": "0-48 months"},
        "impacts": {"neuf": 0, "ancien": 0, "renovation": 2},
        "resume": {
            "FR": "La **6e période des CEE** court du **1er janvier 2026 au 31 décembre "
                  "2029**, avec un relèvement significatif des obligations d'économies "
                  "d'énergie imposées aux vendeurs d'énergie. L'accent est mis sur les "
                  "opérations performantes : isolation, chauffage décarboné, rénovations "
                  "globales. Ce financement privé compense en partie la contraction des "
                  "aides budgétaires directes (MaPrimeRénov').",
            "EN": "The **6th CEE period** runs from **1 January 2026 to 31 December 2029**, "
                  "with a significant increase in the energy-saving obligations placed on "
                  "energy sellers. Emphasis is on high-performance operations: insulation, "
                  "decarbonised heating, whole-home renovations. This private funding "
                  "partly offsets the contraction of direct budget aid (MaPrimeRénov').",
        },
        "impact_detail": {
            "FR": "Soutien structurel au pilier rénovation sur 4 ans : primes CEE (et "
                  "bonifications type « coup de pouce ») directement mobilisables sur les "
                  "familles second œuvre (isolation, fermetures & menuiseries). Contrepoids "
                  "au recentrage de MaPrimeRénov' — les deux dispositifs sont cumulables.",
            "EN": "Structural 4-year support for the renovation pillar: CEE premiums (and "
                  "'coup de pouce' boosts) directly usable on secondary-works families "
                  "(insulation, closures & joinery). A counterweight to the MaPrimeRénov' "
                  "refocus — the two schemes can be combined.",
        },
        "jalons": [
            ("2026-01-01", {"FR": "Début de la 6e période", "EN": "6th period starts"}, "effet"),
            ("2029-12-31", {"FR": "Fin de la 6e période", "EN": "6th period ends"}, "echeance"),
        ],
        "sources": [
            ("Ministère — dispositif CEE", "https://www.ecologie.gouv.fr/politiques-publiques/dispositif-certificats-deconomies-denergie"),
            ("Zepros Bâti — MPR/DPE/CEE 2026", "https://bati.zepros.fr/actu-generale/maprimerenov-dpe-cee-est-2026"),
        ],
    },
    {
        "id": "eahp",
        "categorie": "EU",
        "statut": "adopte",
        "date": "2025-12-16",
        "court": {"FR": "Plan logement UE", "EN": "EU housing plan"},
        "titre": {
            "FR": "Plan européen pour le logement abordable (EAHP) : 10 Md€ UE, 375 Md€ mobilisés",
            "EN": "European Affordable Housing Plan (EAHP): €10bn EU, €375bn mobilised",
        },
        "montant": {"FR": "10 Md€ (2026-27) + 375 Md€ d'ici 2029", "EN": "€10bn (2026-27) + €375bn by 2029"},
        "horizon": {"FR": "12-48 mois", "EN": "12-48 months"},
        "impacts": {"neuf": 1, "ancien": 0, "renovation": 1},
        "resume": {
            "FR": "Présenté par la Commission le **16 décembre 2025** — premier plan "
                  "logement de l'UE. Il prévoit **10 Md€ supplémentaires du budget européen "
                  "en 2026-2027** et **375 Md€ mobilisés via la BEI et les institutions "
                  "financières partenaires d'ici 2029** pour la construction et la "
                  "rénovation abordables. Un **Affordable Housing Act** est attendu en 2026 "
                  "(dont encadrement des locations de courte durée), ainsi que le **premier "
                  "sommet européen des chefs d'État sur le logement** et une European "
                  "Housing Alliance. Résolution de soutien du Parlement européen le 24 mars "
                  "2026.",
            "EN": "Presented by the Commission on **16 December 2025** — the EU's first "
                  "housing plan. It earmarks **an extra €10bn from the EU budget in "
                  "2026-2027** and **€375bn mobilised via the EIB and partner financial "
                  "institutions by 2029** for affordable construction and renovation. An "
                  "**Affordable Housing Act** is expected in 2026 (including short-term "
                  "rental rules), plus the **first EU heads-of-state housing summit** and a "
                  "European Housing Alliance. Supporting European Parliament resolution on "
                  "24 March 2026.",
        },
        "impact_detail": {
            "FR": "Effet surtout **moyen-long terme** via le financement BEI du logement "
                  "social/abordable et de la rénovation : renfort potentiel des ventes en "
                  "bloc aux bailleurs sociaux (visibles dans les réservations ECLN "
                  "« bailleurs sociaux » de l'onglet Commercialisation Neuf) et des "
                  "programmes de rénovation du parc social.",
            "EN": "Mostly a **medium-to-long-term** effect via EIB funding of social/"
                  "affordable housing and renovation: potential boost to block sales to "
                  "social landlords (visible in the ECLN 'social landlords' reservations in "
                  "the New-Build Sales tab) and to social-housing renovation programmes.",
        },
        "jalons": [
            ("2025-12-16", {"FR": "Présentation par la Commission", "EN": "Presented by the Commission"}, "effet"),
            ("2026-03-24", {"FR": "Résolution du Parlement européen", "EN": "European Parliament resolution"}, "jalon"),
            ("2026-12-31", {"FR": "Affordable Housing Act + sommet UE attendus en 2026", "EN": "Affordable Housing Act + EU summit expected in 2026"}, "echeance"),
        ],
        "sources": [
            ("Commission européenne — EAHP", "https://housing.ec.europa.eu/european-affordable-housing-plan_en"),
            ("Euronews — résolution du Parlement", "https://www.euronews.com/my-europe/2026/03/24/eu-parliament-adopts-motion-to-face-europes-housing-crisis"),
        ],
    },
    {
        "id": "citizens_energy",
        "categorie": "EU",
        "statut": "discussion",
        "date": "2026-06-30",
        "court": {"FR": "Citizens Energy Package", "EN": "Citizens Energy Package"},
        "titre": {
            "FR": "Citizens Energy Package (UE) : factures, précarité énergétique, rénovation",
            "EN": "Citizens Energy Package (EU): bills, energy poverty, renovation",
        },
        "montant": None,
        "horizon": {"FR": "12-36 mois", "EN": "12-36 months"},
        "impacts": {"neuf": 0, "ancien": 0, "renovation": 1},
        "resume": {
            "FR": "Volet complémentaire du plan logement européen, annoncé pour **2026** : "
                  "un paquet « énergie des citoyens » visant à faire baisser les factures, "
                  "éradiquer la précarité énergétique et accompagner une transition juste — "
                  "avec un levier attendu sur la rénovation énergétique des logements des "
                  "ménages modestes. Contenu législatif précis encore en préparation.",
            "EN": "Companion piece to the EU housing plan, announced for **2026**: a "
                  "'Citizens Energy Package' to lower energy bills, eradicate energy "
                  "poverty and support a just transition — with an expected lever on "
                  "energy renovation of low-income households' homes. Precise legislative "
                  "content still in preparation.",
        },
        "impact_detail": {
            "FR": "À ce stade un signal plutôt qu'un dispositif : à suivre pour le pilier "
                  "rénovation (aides européennes ciblées précarité énergétique, possibles "
                  "co-financements des monogestes que la France recentre par ailleurs).",
            "EN": "At this stage a signal rather than a scheme: watch it for the renovation "
                  "pillar (EU aid targeting energy poverty, possible co-funding of the "
                  "single-measure works France is otherwise refocusing).",
        },
        "jalons": [
            ("2026-12-31", {"FR": "Présentation attendue courant 2026", "EN": "Expected during 2026"}, "echeance"),
        ],
        "sources": [
            ("Commission européenne — EAHP", "https://housing.ec.europa.eu/european-affordable-housing-plan_en"),
            ("Commission — logement abordable", "https://commission.europa.eu/topics/employment-and-social-affairs/affordable-housing_fr"),
        ],
    },
]


def items_sorted():
    """NEWS_ITEMS du plus récent au plus ancien (date de référence)."""
    return sorted(NEWS_ITEMS, key=lambda it: it["date"], reverse=True)


def jalons_frame(items, lang):
    """DataFrame des jalons datés (échéancier) : Dispositif / Date / Jalon / Type / Catégorie."""
    import pandas as pd
    rows = []
    for it in items:
        for d, label, typ in it.get("jalons", []):
            rows.append({
                "Dispositif": it["court"][lang],
                "Date": pd.Timestamp(d),
                "Jalon": label[lang],
                "Type": typ,
                "Categorie": it["categorie"],
            })
    return pd.DataFrame(rows)


def impact_matrix(items, lang):
    """DataFrame récapitulatif dispositif × pilier (libellés emoji), + statut et horizon."""
    import pandas as pd
    lab = IMPACT_LABELS[lang]
    rows = []
    for it in items:
        rows.append({
            ("Dispositif" if lang == "FR" else "Measure"): it["court"][lang],
            ("Périmètre" if lang == "FR" else "Scope"): CATEGORIES[lang][it["categorie"]],
            ("Statut" if lang == "FR" else "Status"): STATUTS[lang][it["statut"]],
            PILIERS[lang]["neuf"]: lab[it["impacts"]["neuf"]],
            PILIERS[lang]["ancien"]: lab[it["impacts"]["ancien"]],
            PILIERS[lang]["renovation"]: lab[it["impacts"]["renovation"]],
            ("Horizon" if lang == "FR" else "Horizon"): it["horizon"][lang],
        })
    return pd.DataFrame(rows)
