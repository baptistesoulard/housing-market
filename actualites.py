"""Veille « Aides & dispositifs » — aides publiques et plans logement (FR + UE).

Contenu ÉDITORIAL curaté manuellement (pas de flux automatique) : chaque entrée décrit un
dispositif ou un plan (statut, jalons, montants) et son impact POTENTIEL sur trois piliers
(neuf = permis/ventes SIT@DEL-ECLN, ancien = transactions IGEDD, rénovation = second
œuvre). Les impacts sont des lectures qualitatives (-2..+2), pas des sorties de modèle.

Mise à jour : éditer NEWS_ITEMS puis la constante MAJ. Textes bilingues {"FR": .., "EN": ..}
(le site ne publie que le FR ; l'EN est conservé pour une version anglaise éventuelle).
`tests/test_actualites.py` vérifie la cohérence du contenu, et échoue si la veille a plus
de 120 jours.

Revue du 2026-10-04 : décret MaPrimeRénov' du 25 août 2026 (fin du parcours par geste pour
l'isolation et les fenêtres), PLF 2027 présenté le 1er octobre (PTZ, Anah, dons), projet
de loi Relance logement à l'Assemblée, Affordable Housing Act proposé le 9 septembre, et
deux corrections : la 6e période CEE court jusqu'en 2030 (et non 2029), et le Citizens
Energy Package avait été présenté dès le 10 mars 2026.
"""

# Date d'arrêt de la veille (affichée sur la page — à mettre à jour à chaque édition).
MAJ = "2026-10-04"

# Le chiffre-clé de la carte de tête de la page, revu avec le reste de la veille (il
# était écrit en dur dans l'export, et vieillissait sans que rien ne le signale).
CHIFFRE_CLE = {"label": "Dotation de l'État à l'Anah 2027 (PLF)", "value": "1,2 Md€",
               "sub": "contre 1,4 Md€ en 2026"}

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

# Types de jalons pour l'échéancier (symbole + libellé de légende).
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
        "id": "ptz_2026",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-10-01",
        "court": {"FR": "PTZ", "EN": "PTZ"},
        "titre": {
            "FR": "Prêt à taux zéro : tout le territoire, et un PTZ « parentalité » au PLF 2027",
            "EN": "Zero-interest loan (PTZ): nationwide, plus a 'parenthood' PTZ in the 2027 budget bill",
        },
        "montant": {"FR": "Plafond de dépense de 2,1 Md€ supprimé (PLF 2027)",
                    "EN": "€2.1bn spending cap removed (2027 budget bill)"},
        "horizon": {"FR": "3-18 mois", "EN": "3-18 months"},
        "impacts": {"neuf": 2, "ancien": 1, "renovation": 1},
        "resume": {
            "FR": "Depuis le **1er avril 2025**, le PTZ couvre **tout le territoire** et de "
                  "nouveau la **maison individuelle neuve** ; dans l'ancien, il reste "
                  "conditionné à des travaux (≥ 25 % du coût total) en zone détendue. Il "
                  "court jusqu'au **31 décembre 2027**. Le **PLF 2027**, présenté le **1er "
                  "octobre 2026**, crée un **PTZ « parentalité »** — ouvert une fois aux "
                  "ménages qui attendent un enfant ou ont un enfant de moins de trois ans, "
                  "même s'ils ont déjà bénéficié d'un PTZ — et **supprime le plafond annuel "
                  "de dépense de 2,1 Md€**, inchangé depuis 2016. Le Premier ministre a "
                  "annoncé une prolongation au-delà de 2027, que le texte présenté ne "
                  "contient pas encore.",
            "EN": "Since **1 April 2025** the PTZ covers the **whole country** and again "
                  "**new detached houses**; for existing homes it still requires works "
                  "(≥ 25% of total cost) in low-pressure areas. It runs until **31 December "
                  "2027**. The **2027 budget bill**, presented on **1 October 2026**, creates "
                  "a **'parenthood' PTZ** — available once to households expecting a child "
                  "or with a child under three, even if they already had a PTZ — and "
                  "**removes the €2.1bn annual spending cap** unchanged since 2016. The "
                  "Prime Minister announced an extension beyond 2027 that the bill as "
                  "presented does not yet contain.",
        },
        "impact_detail": {
            "FR": "Principal levier de solvabilisation des primo-accédants : soutien direct "
                  "aux ventes de maisons neuves puis aux permis. Le volet « ancien avec "
                  "travaux » alimente aussi les transactions et la rénovation (25 % de "
                  "travaux imposés). Le PTZ « parentalité » élargit le public sans changer "
                  "le mécanisme ; l'absence de prolongation écrite au-delà de 2027 reste le "
                  "point à surveiller pour les programmes neufs lancés en 2027.",
            "EN": "Main solvency lever for first-time buyers: direct support to new "
                  "detached-house sales, then permits. The 'existing home with works' leg "
                  "also feeds transactions and renovation (25% works requirement). The "
                  "parenthood PTZ widens the audience without changing the mechanism; the "
                  "lack of a written extension beyond 2027 is the point to watch for new-"
                  "build programmes launched in 2027.",
        },
        "jalons": [
            ("2025-04-01", {"FR": "Extension nationale + maison neuve", "EN": "Nationwide extension + new houses"}, "effet"),
            ("2026-10-01", {"FR": "PLF 2027 : PTZ parentalité, plafond supprimé", "EN": "2027 budget bill: parenthood PTZ, cap removed"}, "jalon"),
            ("2026-11-17", {"FR": "Adoption visée du PLF 2027 à l'Assemblée", "EN": "Targeted Assembly vote on the 2027 budget bill"}, "echeance"),
            ("2027-12-31", {"FR": "Fin de la prorogation actuelle", "EN": "End of current extension"}, "echeance"),
        ],
        "sources": [
            ("HLM.coop — PLF 2027 et logement", "https://www.hlm.coop/actualites/all/21771"),
            ("Batiactu — annonces logement du PLF 2027", "https://www.batiactu.com/edito/budget-2027-annonces-lecornu-sur-logement-75394.php"),
            ("Service-Public — PTZ", "https://www.service-public.fr/particuliers/vosdroits/F10871"),
        ],
    },
    {
        "id": "relance_logement",
        "categorie": "FR",
        "statut": "discussion",
        "date": "2026-09-21",
        "court": {"FR": "Loi Relance logement", "EN": "Housing relaunch bill"},
        "titre": {
            "FR": "Projet de loi « Relance logement et décentralisation » : adopté au Sénat, examiné à l'Assemblée",
            "EN": "'Housing relaunch and decentralisation' bill: passed by the Senate, before the Assembly",
        },
        "montant": {"FR": "Objectif : 400 000 logements/an, 2 millions d'ici 2030",
                    "EN": "Target: 400,000 homes/yr, 2 million by 2030"},
        "horizon": {"FR": "6-36 mois", "EN": "6-36 months"},
        "impacts": {"neuf": 1, "ancien": 1, "renovation": 0},
        "resume": {
            "FR": "Présenté le **24 juin 2026** par le ministre Vincent Jeanbrun, adopté en "
                  "première lecture par le **Sénat le 8 juillet**, arrivé à l'**Assemblée "
                  "nationale le 21 septembre** (procédure accélérée, adoption visée avant la "
                  "fin de l'année). Deux articles comptent pour le marché : l'**article 4** "
                  "retouche le statut du bailleur privé créé par la loi de finances 2026 "
                  "(le Sénat a remplacé le seuil de 20 % de travaux dans l'ancien par un "
                  "critère de performance énergétique et ouvert le dispositif aux SCPI) ; "
                  "l'**article 6** permettrait de **continuer à louer un logement F ou G** "
                  "si le propriétaire s'engage par contrat à le rénover — en **3 ans** pour "
                  "une maison, **5 ans** en copropriété — jusqu'à la classe E au moins. Le "
                  "gouvernement estime que 650 000 à 700 000 logements resteraient ou "
                  "reviendraient sur le marché locatif d'ici 2028. Le texte donne aussi de "
                  "nouveaux pouvoirs aux maires. Tant qu'il n'est pas voté, le calendrier "
                  "de la loi Climat & Résilience s'applique.",
            "EN": "Presented on **24 June 2026** by minister Vincent Jeanbrun, passed at "
                  "first reading by the **Senate on 8 July**, sent to the **National "
                  "Assembly on 21 September** (fast-track procedure, final vote targeted "
                  "before year-end). Two articles matter for the market: **article 4** "
                  "amends the private-landlord status created by the 2026 budget law (the "
                  "Senate replaced the 20% works threshold for existing homes with an "
                  "energy-performance criterion and opened it to SCPIs); **article 6** "
                  "would let owners **keep renting F- or G-rated homes** if they commit by "
                  "contract to renovate them — within **3 years** for a house, **5 years** "
                  "in a condominium — to at least class E. The government estimates "
                  "650,000-700,000 homes would stay on or return to the rental market by "
                  "2028. The bill also gives mayors new powers. Until it passes, the "
                  "Climate & Resilience calendar applies.",
        },
        "impact_detail": {
            "FR": "Pour l'**ancien**, l'article 6 retire une partie des ventes contraintes de "
                  "passoires que l'échéance F-2028 aurait provoquées, et garde des biens sur "
                  "le marché locatif. Pour la **rénovation**, l'effet est ambigu : moins "
                  "d'urgence réglementaire, mais des travaux contractualisés et étalés sur "
                  "3 à 5 ans plutôt qu'un retrait du marché. Pour le **neuf**, l'effet passe "
                  "par le statut du bailleur privé (voir l'entrée dédiée).",
            "EN": "For **existing homes**, article 6 removes part of the forced sales of "
                  "energy sieves the F-2028 deadline would have triggered, and keeps homes "
                  "on the rental market. For **renovation** the effect is ambiguous: less "
                  "regulatory urgency, but contracted works spread over 3-5 years rather "
                  "than withdrawal. For **new-build**, the effect runs through the private-"
                  "landlord status (see its own entry).",
        },
        "jalons": [
            ("2026-06-24", {"FR": "Présentation du projet de loi", "EN": "Bill presented"}, "jalon"),
            ("2026-07-08", {"FR": "Adoption au Sénat (1re lecture)", "EN": "Senate first-reading vote"}, "jalon"),
            ("2026-09-21", {"FR": "Transmission à l'Assemblée nationale", "EN": "Sent to the National Assembly"}, "jalon"),
            ("2026-12-31", {"FR": "Adoption définitive visée avant la fin de l'année", "EN": "Final adoption targeted by year-end"}, "echeance"),
        ],
        "sources": [
            ("Banque des Territoires — le Sénat adopte le projet de loi", "https://www.banquedesterritoires.fr/le-senat-adopte-le-projet-de-loi-logement-et-donne-du-pouvoir-aux-maires"),
            ("LocService — passoires thermiques", "https://www.locservice.fr/actualites/assouplissement-interdiction-location-passoires-thermiques-2026-16079.html"),
            ("vie-publique.fr — loi Relance logement", "https://www.vie-publique.fr/loi/303813-relance-logement-projet-de-loi-jeanbrun"),
        ],
    },
    {
        "id": "eu_aha",
        "categorie": "EU",
        "statut": "discussion",
        "date": "2026-09-09",
        "court": {"FR": "Affordable Housing Act", "EN": "Affordable Housing Act"},
        "titre": {
            "FR": "Affordable Housing Act : la Commission propose un règlement européen sur le logement abordable",
            "EN": "Affordable Housing Act: the Commission proposes an EU regulation on affordable housing",
        },
        "montant": None,
        "horizon": {"FR": "24-48 mois", "EN": "24-48 months"},
        "impacts": {"neuf": 1, "ancien": 0, "renovation": 0},
        "resume": {
            "FR": "Proposé le **9 septembre 2026** (COM(2026) 599), un **règlement** qui "
                  "donne un cadre commun aux mesures nationales : une méthode commune pour "
                  "désigner les **zones sous tension**, les conditions auxquelles une "
                  "autorité peut **restreindre les locations de courte durée** (impact "
                  "négatif démontré sur trois ans, mesure ciblée et proportionnée), un cadre "
                  "pour les résidences secondaires et les logements durablement vacants, et "
                  "un plan d'accélération (permis, rénovation, reconversion de bâtiments) "
                  "adossé à de nouvelles règles d'aides d'État. Le Parlement européen et le "
                  "Conseil doivent encore s'accorder sur le texte.",
            "EN": "Proposed on **9 September 2026** (COM(2026) 599), a **regulation** giving "
                  "national measures a common framework: a shared method to designate "
                  "**high-pressure areas**, conditions under which authorities may "
                  "**restrict short-term rentals** (negative impact shown over three "
                  "years, targeted and proportionate), a framework for second homes and "
                  "long-term vacant dwellings, and an acceleration plan (permits, "
                  "renovation, building conversion) backed by new state-aid rules. "
                  "Parliament and Council still have to agree on the text.",
        },
        "impact_detail": {
            "FR": "Effet de **long terme** et indirect : des aides d'État plus faciles pour le "
                  "logement abordable soutiendraient la production neuve des bailleurs "
                  "sociaux, et un cadre clair pour les meublés de tourisme peut remettre des "
                  "logements sur le marché dans les zones tendues. Rien ne change tant que "
                  "le règlement n'est pas adopté.",
            "EN": "A **long-term**, indirect effect: easier state aid for affordable housing "
                  "would support social landlords' new-build output, and a clear framework "
                  "for short-term lets can bring homes back to market in tight areas. "
                  "Nothing changes until the regulation is adopted.",
        },
        "jalons": [
            ("2026-09-09", {"FR": "Proposition de la Commission", "EN": "Commission proposal"}, "jalon"),
        ],
        "sources": [
            ("Commission européenne — Affordable Housing Act", "https://housing.ec.europa.eu/european-affordable-housing-plan/affordable-housing-act_en"),
            ("Commission — communiqué du 9 septembre 2026", "https://luxembourg.representation.ec.europa.eu/actualites-et-evenements/actualites/new-eu-rules-help-local-authorities-tackle-housing-crisis-2026-09-09_en"),
        ],
    },
    {
        "id": "mpr_2026",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-09-01",
        "court": {"FR": "MaPrimeRénov'", "EN": "MaPrimeRénov'"},
        "titre": {
            "FR": "MaPrimeRénov' : fin de l'aide par geste pour l'isolation et les fenêtres depuis le 1er septembre 2026",
            "EN": "MaPrimeRénov': no more single-measure grants for insulation and windows since 1 September 2026",
        },
        "montant": {"FR": "Dotation de l'État à l'Anah : 1,2 Md€ en 2027 (-200 M€)",
                    "EN": "State allocation to Anah: €1.2bn in 2027 (-€200m)"},
        "horizon": {"FR": "0-12 mois", "EN": "0-12 months"},
        "impacts": {"neuf": 0, "ancien": 0, "renovation": -1},
        "resume": {
            "FR": "Le **décret n° 2026-822 du 25 août 2026** retire six travaux du parcours "
                  "« par geste » au **1er septembre 2026** : **isolation des combles et "
                  "toitures**, **fenêtres et portes**, ventilation double flux, chauffe-eau "
                  "thermodynamique, poêles à bois ou granulés et solaire thermique "
                  "(métropole). Ne restent finançables seuls que la pompe à chaleur de "
                  "chauffage, le raccordement à un réseau de chaleur, l'audit énergétique et "
                  "la dépose d'une cuve à fioul ; les dossiers déposés avant le 1er "
                  "septembre gardent les anciennes règles. Le Conseil national de l'habitat "
                  "avait rendu un avis défavorable le 2 juillet. Le **PLF 2027** prévoit "
                  "1,2 Md€ de crédits de l'État pour l'Anah, contre 1,4 Md€ en 2026 : les "
                  "travaux isolés sont désormais financés par les seuls CEE. La rénovation "
                  "d'ampleur (gain d'au moins deux classes de DPE) reste aidée.",
            "EN": "**Decree no. 2026-822 of 25 August 2026** removes six works from the "
                  "single-measure track on **1 September 2026**: **attic and roof "
                  "insulation**, **windows and doors**, balanced ventilation, heat-pump "
                  "water heaters, wood or pellet stoves and solar thermal (mainland). Only "
                  "heating heat pumps, heat-network connection, energy audits and oil-tank "
                  "removal remain fundable on their own; applications filed before 1 "
                  "September keep the old rules. The national housing council had issued "
                  "an unfavourable opinion on 2 July. The **2027 budget bill** plans €1.2bn "
                  "of State funding for Anah, down from €1.4bn in 2026: single works are "
                  "now funded through energy-saving certificates (CEE) only. Deep "
                  "renovation (at least two EPC classes gained) remains subsidised.",
        },
        "impact_detail": {
            "FR": "**Frein** pour la rénovation par geste : l'isolation et les fenêtres posées "
                  "seules perdent l'aide de l'État et ne gardent que la prime CEE. Attendre "
                  "un **pic de dossiers déposés en août 2026**, puis un creux sur ces "
                  "travaux, plus marqué chez les ménages modestes, pour qui MaPrimeRénov' "
                  "pesait le plus. La rénovation d'ampleur et les pompes à chaleur sont "
                  "épargnées.",
            "EN": "A **headwind** for single-measure renovation: insulation and windows done "
                  "on their own lose State aid and keep only the CEE premium. Expect a "
                  "**spike of applications filed in August 2026**, then a dip on these "
                  "works, sharper for low-income households, for whom MaPrimeRénov' "
                  "mattered most. Deep renovation and heat pumps are spared.",
        },
        "jalons": [
            ("2026-02-06", {"FR": "Réouverture avec la LF 2026 (3,6 Md€)", "EN": "Reopening with the 2026 budget (€3.6bn)"}, "effet"),
            ("2026-07-02", {"FR": "Avis défavorable du CNH", "EN": "Unfavourable housing-council opinion"}, "jalon"),
            ("2026-09-01", {"FR": "Six gestes retirés du parcours par geste", "EN": "Six measures removed from the single-measure track"}, "effet"),
            ("2026-10-01", {"FR": "PLF 2027 : dotation Anah à 1,2 Md€", "EN": "2027 budget bill: Anah allocation at €1.2bn"}, "jalon"),
        ],
        "sources": [
            ("Argile — le décret du 25 août 2026", "https://www.argile.ai/blog/fin-des-monogestes-maprimerenov-deux-ans-de-bras-de-fer"),
            ("Boursorama — budget de l'Anah 2027", "https://www.boursorama.com/immobilier/actualites/maprimerenov-le-budget-de-l-anah-en-baisse-de-200-millions-d-euros-f48d4509cb23c93b33d7614a2d00be3d"),
            ("Selectra — avis du CNH", "https://selectra.info/energie/actualites/renovation-energetique/cnh-avis-defavorable-suppression-monogestes-maprimerenov"),
        ],
    },
    {
        "id": "citizens_energy",
        "categorie": "EU",
        "statut": "adopte",
        "date": "2026-03-10",
        "court": {"FR": "Citizens Energy Package", "EN": "Citizens Energy Package"},
        "titre": {
            "FR": "Citizens Energy Package (UE) : factures et précarité énergétique, sans volet rénovation",
            "EN": "Citizens Energy Package (EU): bills and energy poverty, no renovation strand",
        },
        "montant": None,
        "horizon": {"FR": "12-36 mois", "EN": "12-36 months"},
        "impacts": {"neuf": 0, "ancien": 0, "renovation": 0},
        "resume": {
            "FR": "Présenté le **10 mars 2026** : une **communication** de la Commission "
                  "(COM(2026) 115), non contraignante, complétée le 30 avril par des "
                  "recommandations aux États membres. Elle vise les factures d'énergie "
                  "(protection contre les coupures, baisse des taxes sur l'électricité, qui "
                  "pèsent environ 25 % du prix payé par les ménages) et la précarité "
                  "énergétique — un ménage européen sur dix ne peut pas se chauffer "
                  "correctement — sans mesure propre à la rénovation des logements.",
            "EN": "Presented on **10 March 2026**: a non-binding Commission "
                  "**communication** (COM(2026) 115), followed on 30 April by "
                  "recommendations to Member States. It targets energy bills (protection "
                  "against disconnection, lower taxes on electricity, about 25% of the "
                  "price households pay) and energy poverty — one European household in ten "
                  "cannot heat its home adequately — with no measure specific to housing "
                  "renovation.",
        },
        "impact_detail": {
            "FR": "Pas d'effet direct attendu sur les volumes : un cadre d'orientation, pas un "
                  "financement. Corrige la veille de juillet, qui l'annonçait encore à venir "
                  "et en attendait un levier sur la rénovation.",
            "EN": "No direct effect on volumes expected: guidance, not funding. Corrects the "
                  "July review, which still described it as upcoming and expected a "
                  "renovation lever.",
        },
        "jalons": [
            ("2026-03-10", {"FR": "Communication de la Commission", "EN": "Commission communication"}, "effet"),
            ("2026-04-30", {"FR": "Recommandations aux États membres", "EN": "Recommendations to Member States"}, "jalon"),
        ],
        "sources": [
            ("Commission européenne — communiqué du 10 mars 2026", "https://energy.ec.europa.eu/news/commission-boost-access-affordable-and-clean-energy-all-europeans-2026-03-10_en"),
            ("Commission européenne — Citizens Energy Package", "https://energy.ec.europa.eu/topics/markets-and-consumers/energy-consumers-and-prosumers/citizens-energy-package_en"),
        ],
    },
    {
        "id": "jeanbrun",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-02-21",
        "court": {"FR": "Statut du bailleur privé", "EN": "Private-landlord status"},
        "titre": {
            "FR": "Statut du bailleur privé (« dispositif Jeanbrun ») : l'amortissement locatif remplace le Pinel",
            "EN": "Private-landlord status ('Jeanbrun scheme'): rental depreciation replaces Pinel",
        },
        "montant": {"FR": "Amortissement 3,5 à 5,5 %/an, plafonné à 8-12 k€",
                    "EN": "3.5-5.5%/yr depreciation, capped at €8-12k"},
        "horizon": {"FR": "6-24 mois", "EN": "6-24 months"},
        "impacts": {"neuf": 2, "ancien": 1, "renovation": 1},
        "resume": {
            "FR": "Créé par la **loi de finances 2026** (loi n° 2026-103 du 19 février 2026, "
                  "art. 47), **en vigueur depuis le 21 février 2026** pour les acquisitions "
                  "jusqu'au **31 décembre 2028** : le bailleur qui loue nu pendant **9 ans**, "
                  "sous plafonds de loyer et de ressources, déduit chaque année de ses "
                  "revenus fonciers un amortissement de 80 % de la valeur du bien — 3,5 % en "
                  "loyer intermédiaire, 4,5 % en social, 5,5 % en très social, plafonné à "
                  "8 000, 10 000 et 12 000 € par an. Sans zonage, au **neuf** comme à "
                  "l'**ancien rénové**. Le projet de loi Relance logement, à l'Assemblée "
                  "depuis le 21 septembre, en retouche les conditions (voir l'entrée "
                  "dédiée).",
            "EN": "Created by the **2026 budget law** (law no. 2026-103 of 19 February 2026, "
                  "art. 47), **in force since 21 February 2026** for purchases until **31 "
                  "December 2028**: landlords letting unfurnished for **9 years**, under "
                  "rent and income ceilings, deduct each year from rental income a "
                  "depreciation of 80% of the property value — 3.5% at intermediate rent, "
                  "4.5% social, 5.5% very social, capped at €8,000, €10,000 and €12,000 a "
                  "year. No zoning, for **new-build** and **renovated existing homes** "
                  "alike. The Housing relaunch bill, before the Assembly since 21 "
                  "September, amends its conditions (see its own entry).",
        },
        "impact_detail": {
            "FR": "Relance de la demande d'investissement locatif → soutien aux réservations "
                  "de logements neufs (ECLN), puis aux permis (transmission 12-24 mois). "
                  "L'éligibilité de l'**ancien rénové** joue doublement : transactions, et "
                  "travaux sur les biens achetés pour être loués.",
            "EN": "Restarts rental-investment demand → supports new-build reservations "
                  "(ECLN), then permits (12-24-month transmission). Eligibility of "
                  "**renovated existing homes** works twice: transactions, and works on "
                  "homes bought to let.",
        },
        "jalons": [
            ("2026-02-21", {"FR": "Entrée en vigueur (LF 2026)", "EN": "Entry into force (2026 budget law)"}, "effet"),
            ("2028-12-31", {"FR": "Fin des acquisitions éligibles", "EN": "End of eligible purchases"}, "echeance"),
        ],
        "sources": [
            ("Kohen Avocats — statut du bailleur privé", "https://kohenavocats.fr/2026/09/09/statut-bailleur-prive-2026-amortissement-locatif-relance-logement-conditions/"),
            ("info.gouv.fr — Relance logement", "https://www.info.gouv.fr/grand-dossier/relance-logement"),
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
                  "**F au 1er janvier 2028**, pour les E en 2034 — mais le projet de loi "
                  "Relance logement, à l'Assemblée, permettrait de continuer à louer un F ou "
                  "un G contre un engagement de travaux (voir l'entrée dédiée).",
            "EN": "On **1 January 2026** the electricity conversion factor in the French EPC "
                  "drops from **2.3 to 1.9** (EU alignment): about **850,000 electrically "
                  "heated homes mechanically exit 'energy sieve' status** (F/G). The "
                  "Climate & Resilience calendar still applies: renting G-rated homes "
                  "banned since 2025, **F-rated from 1 January 2028**, E-rated from 2034 — "
                  "but the Housing relaunch bill, before the Assembly, would let owners "
                  "keep renting F or G homes against a works commitment (see its entry).",
        },
        "impact_detail": {
            "FR": "Double lecture : la sortie de 850 000 logements du statut F/G **fluidifie "
                  "les transactions dans l'ancien** (moins de décotes, moins de ventes "
                  "contraintes) mais **réduit la pression réglementaire à rénover** ces "
                  "biens — léger frein pour la rénovation, que l'assouplissement en "
                  "discussion accentuerait.",
            "EN": "Two-sided: 850,000 homes exiting F/G status **smooths existing-home "
                  "transactions** (fewer discounts, fewer forced sales) but **eases the "
                  "regulatory pressure to renovate** — a mild headwind for renovation, "
                  "which the softening under discussion would reinforce.",
        },
        "jalons": [
            ("2026-01-01", {"FR": "Nouveau coefficient électricité", "EN": "New electricity factor"}, "effet"),
            ("2028-01-01", {"FR": "Interdiction de louer les logements F (loi actuelle)", "EN": "Ban on renting F-rated homes (current law)"}, "echeance"),
        ],
        "sources": [
            ("Ministère — le DPE", "https://www.ecologie.gouv.fr/politiques-publiques/diagnostic-performance-energetique-dpe"),
            ("Zepros Bâti — MPR/DPE/CEE 2026", "https://bati.zepros.fr/actu-generale/maprimerenov-dpe-cee-est-2026"),
        ],
    },
    {
        "id": "cee_p6",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2026-01-01",
        "court": {"FR": "CEE 6e période", "EN": "CEE 6th period"},
        "titre": {
            "FR": "Certificats d'économies d'énergie : 6e période 2026-2030, obligations relevées de 27 %",
            "EN": "Energy-saving certificates (CEE): 6th period 2026-2030, obligations up 27%",
        },
        "montant": {"FR": "1 050 TWhc/an, dont 280 pour la précarité",
                    "EN": "1,050 TWhc/yr, of which 280 for energy poverty"},
        "horizon": {"FR": "0-60 mois", "EN": "0-60 months"},
        "impacts": {"neuf": 0, "ancien": 0, "renovation": 2},
        "resume": {
            "FR": "La **6e période des CEE** (décret n° 2025-1048 du 4 novembre 2025) court "
                  "du **1er janvier 2026 au 31 décembre 2030** — cinq ans, et non quatre "
                  "comme l'indiquait la veille précédente. Obligation de **1 050 TWh cumac "
                  "par an**, dont **280 réservés à la précarité énergétique**, soit environ "
                  "27 % de plus que la période précédente ; les bonifications « coup de "
                  "pouce » sont prolongées. Depuis le 1er septembre 2026, les CEE sont la "
                  "**seule aide nationale** pour l'isolation et les fenêtres posées seules "
                  "(voir MaPrimeRénov').",
            "EN": "The **6th CEE period** (decree no. 2025-1048 of 4 November 2025) runs "
                  "from **1 January 2026 to 31 December 2030** — five years, not four as "
                  "the previous review said. Obligation of **1,050 TWh cumac a year**, of "
                  "which **280 for energy poverty**, about 27% more than the previous "
                  "period; 'coup de pouce' boosts are extended. Since 1 September 2026, "
                  "CEE are the **only national aid** for insulation and windows done on "
                  "their own (see MaPrimeRénov').",
        },
        "impact_detail": {
            "FR": "Soutien structurel à la rénovation sur cinq ans, financé par les vendeurs "
                  "d'énergie et non par le budget de l'État : c'est le contrepoids au "
                  "recentrage de MaPrimeRénov', et désormais le principal financement des "
                  "travaux d'isolation et de menuiserie réalisés seuls.",
            "EN": "Structural five-year support for renovation, funded by energy sellers "
                  "rather than the State budget: the counterweight to the MaPrimeRénov' "
                  "refocus, and now the main funding for insulation and joinery works done "
                  "on their own.",
        },
        "jalons": [
            ("2026-01-01", {"FR": "Début de la 6e période", "EN": "6th period starts"}, "effet"),
            ("2030-12-31", {"FR": "Fin de la 6e période", "EN": "6th period ends"}, "echeance"),
        ],
        "sources": [
            ("Hellio — la 6e période des CEE", "https://www.hellio.com/actualites/reglementation/sixieme-periode-cee"),
            ("Ministère — dispositif CEE", "https://www.ecologie.gouv.fr/politiques-publiques/dispositif-certificats-deconomies-denergie"),
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
                  "logement de l'UE : **10 Md€ supplémentaires du budget européen en "
                  "2026-2027** et **375 Md€ mobilisés via la BEI et les institutions "
                  "financières partenaires d'ici 2029** pour la construction et la "
                  "rénovation abordables. Résolution de soutien du Parlement européen le 24 "
                  "mars 2026. Son volet législatif, l'**Affordable Housing Act**, a été "
                  "proposé le 9 septembre 2026 (voir l'entrée dédiée).",
            "EN": "Presented by the Commission on **16 December 2025** — the EU's first "
                  "housing plan: **an extra €10bn from the EU budget in 2026-2027** and "
                  "**€375bn mobilised via the EIB and partner institutions by 2029** for "
                  "affordable construction and renovation. Supporting European Parliament "
                  "resolution on 24 March 2026. Its legislative strand, the **Affordable "
                  "Housing Act**, was proposed on 9 September 2026 (see its entry).",
        },
        "impact_detail": {
            "FR": "Effet surtout **moyen-long terme** via le financement BEI du logement "
                  "social et abordable et de la rénovation : renfort potentiel des ventes en "
                  "bloc aux bailleurs sociaux (visibles dans les réservations ECLN de la "
                  "page Logement neuf) et des programmes de rénovation du parc social.",
            "EN": "Mostly a **medium-to-long-term** effect via EIB funding of social and "
                  "affordable housing and renovation: potential boost to block sales to "
                  "social landlords (visible in ECLN reservations on the new-build page) "
                  "and to social-housing renovation programmes.",
        },
        "jalons": [
            ("2025-12-16", {"FR": "Présentation par la Commission", "EN": "Presented by the Commission"}, "effet"),
            ("2026-03-24", {"FR": "Résolution du Parlement européen", "EN": "European Parliament resolution"}, "jalon"),
            ("2029-12-31", {"FR": "Horizon des 375 Md€ mobilisés", "EN": "Horizon for the €375bn mobilised"}, "echeance"),
        ],
        "sources": [
            ("Commission européenne — EAHP", "https://housing.ec.europa.eu/european-affordable-housing-plan_en"),
            ("Euronews — résolution du Parlement", "https://www.euronews.com/my-europe/2026/03/24/eu-parliament-adopts-motion-to-face-europes-housing-crisis"),
        ],
    },
    {
        "id": "donation_neuf",
        "categorie": "FR",
        "statut": "vigueur",
        "date": "2025-04-01",
        "court": {"FR": "Donations exonérées", "EN": "Tax-free gifts"},
        "titre": {
            "FR": "Dons familiaux exonérés pour l'achat neuf ou la rénovation énergétique : fin le 31 décembre 2026",
            "EN": "Tax-free family gifts for new-build purchase or energy renovation: ends 31 December 2026",
        },
        "montant": {"FR": "100 k€/donateur, 300 k€/bénéficiaire", "EN": "€100k/donor, €300k/beneficiary"},
        "horizon": {"FR": "0-3 mois — expire fin 2026", "EN": "0-3 months — expires end-2026"},
        "impacts": {"neuf": 1, "ancien": 0, "renovation": 1},
        "resume": {
            "FR": "Depuis 2025 et **jusqu'au 31 décembre 2026**, les dons familiaux (parents, "
                  "grands-parents, arrière-grands-parents) sont exonérés de droits jusqu'à "
                  "**100 000 € par donateur** et **300 000 € par bénéficiaire** s'ils "
                  "financent l'achat d'un **logement neuf** ou en VEFA, ou des **travaux de "
                  "rénovation énergétique** ; les fonds doivent être employés dans les six "
                  "mois et le logement conservé cinq ans. Le **PLF 2027 ne prolonge pas** ce "
                  "régime : la réforme des donations annoncée pour 2027 porte sur les dons "
                  "familiaux en général, sans fléchage vers le logement.",
            "EN": "Since 2025 and **until 31 December 2026**, family gifts (parents, "
                  "grandparents, great-grandparents) are exempt up to **€100,000 per donor** "
                  "and **€300,000 per beneficiary** when they fund a **new-build** or off-"
                  "plan home, or **energy-renovation works**; funds must be used within six "
                  "months and the home kept five years. The **2027 budget bill does not "
                  "extend** it: the gift reform announced for 2027 covers family gifts in "
                  "general, with no housing earmark.",
        },
        "impact_detail": {
            "FR": "L'échéance du 31/12/2026, désormais confirmée, devrait **concentrer des "
                  "réservations neuves et des travaux au dernier trimestre 2026**, puis "
                  "laisser un **contrecoup début 2027**.",
            "EN": "The 31/12/2026 sunset, now confirmed, should **bunch new-build "
                  "reservations and works into Q4 2026**, then leave a **hangover in early "
                  "2027**.",
        },
        "jalons": [
            ("2025-04-01", {"FR": "Début de l'exonération", "EN": "Exemption starts"}, "effet"),
            ("2026-12-31", {"FR": "Fin du dispositif, non prolongé au PLF 2027", "EN": "Scheme expires, not extended in the 2027 bill"}, "echeance"),
        ],
        "sources": [
            ("Kohen Avocats — fin au 31 décembre 2026", "https://kohenavocats.com/don-logement-100000-euros-exoneration-31-decembre-2026-texte-reel/"),
            ("Médicis — budget 2027 et donations", "https://www.medicis-patrimoine.com/actualites-immobilier-neuf/prix-de-l-immobilier/2026/09/17/4264-Budget-le-gouvernement-veut-accelerer-les-donations-familiales-quel-impact-pour-les-projets-immobiliers.html"),
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
