"""Le formulaire de contact de la page « À propos ».

Deux choses seulement sont vérifiées ici, et ce sont les deux qui échouent en SILENCE.

1. **Aucune adresse de courriel personnelle dans le dépôt.** Il est public. Une adresse
   écrite dans un fichier versionné est moissonnée par les robots exactement comme un
   `mailto:` — c'est précisément ce que le formulaire évite, et une seule ligne ajoutée
   par commodité (« pour tester ») annulerait tout le dispositif. La destination vit dans
   la variable d'environnement CONTACT_TO, côté Cloudflare.

2. **Le formulaire est du HTML statique et complet.** S'il était monté en JavaScript, il
   n'existerait plus dès que le runtime échoue, et le visiteur verrait un trou sous un
   titre « Me contacter » — un titre suivi de vide se lit comme une panne. Le champ pot de
   miel est vérifié caché HORS ÉCRAN : `display:none` serait sauté par les robots un peu
   sérieux, et le champ redeviendrait décoratif.

Le comportement du serveur, lui, se vérifie en Node (voir web/README.md) : rien ici ne
lance de build ni de navigateur.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
PAGE = RACINE / "web" / "observable" / "src" / "a-propos.md"
FONCTION = RACINE / "web" / "observable" / "functions" / "api" / "contact.js"

# Les manifestes npm portent les adresses des auteurs de dépendances et des chaînes
# « paquet@version » que la même expression attrape : ils ne sont pas écrits ici, et il
# n'y a rien à y corriger.
EXCLUS = {"package.json", "package-lock.json"}

# Les adresses de service (exemples, expéditeur de bac à sable Resend) sont légitimes.
ADRESSES_AUTORISEES = {"onboarding@resend.dev", "a@b.fr", "moi@example.com"}
ADRESSE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _fichiers_versionnes() -> list[Path]:
    sortie = subprocess.run(
        ["git", "ls-files"], cwd=RACINE, capture_output=True, text=True,
        encoding="utf-8", check=True,
    ).stdout
    return [RACINE / ligne for ligne in sortie.splitlines() if ligne]


def test_aucune_adresse_de_courriel_personnelle_n_est_versionnee():
    coupables: list[str] = []
    for fichier in _fichiers_versionnes():
        if fichier.suffix.lower() not in {".md", ".js", ".py", ".json", ".yml", ".yaml", ".html"}:
            continue
        if fichier.name in EXCLUS:
            continue
        try:
            contenu = fichier.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for trouvee in ADRESSE.findall(contenu):
            # example.com / example.fr sont les domaines réservés à la documentation.
            if trouvee in ADRESSES_AUTORISEES or trouvee.endswith((".example", "@example.com")):
                continue
            coupables.append(f"{fichier.relative_to(RACINE)} : {trouvee}")
    assert not coupables, (
        "Adresse(s) de courriel dans des fichiers versionnés — le dépôt est public et les "
        "robots les moissonnent. La destination du formulaire se règle par la variable "
        "d'environnement CONTACT_TO :\n  " + "\n  ".join(coupables)
    )


def test_la_fonction_ne_code_en_dur_ni_adresse_ni_cle():
    source = FONCTION.read_text(encoding="utf-8")
    assert "env.CONTACT_TO" in source, "la destination doit venir de l'environnement"
    assert "env.RESEND_API_KEY" in source, "la clé API doit venir de l'environnement"


def test_le_formulaire_est_ecrit_en_html_statique():
    page = PAGE.read_text(encoding="utf-8")
    # Le formulaire doit se trouver AVANT toute cellule de code : s'il en dépendait, il
    # disparaîtrait avec elle.
    debut_formulaire = page.index('<form class="hm-form"')
    assert '<h2' not in page[debut_formulaire:], "le formulaire doit clore la page"
    assert "## Me contacter" in page, "la section doit avoir un titre Markdown (sommaire)"


@pytest.mark.parametrize("champ", ["nom", "email", "sujet", "message"])
def test_chaque_champ_attendu_est_present_et_etiquete(champ):
    page = PAGE.read_text(encoding="utf-8")
    assert f'name="{champ}"' in page, f"champ « {champ} » absent du formulaire"
    identifiant = re.search(rf'id="([\w-]+)"[^>]*name="{champ}"', page)
    assert identifiant, f"le champ « {champ} » n'a pas d'id, donc pas d'étiquette liable"
    assert f'for="{identifiant.group(1)}"' in page, (
        f"le champ « {champ} » n'a pas de <label for> — inutilisable au lecteur d'écran"
    )


def test_le_pot_de_miel_est_cache_hors_ecran_et_non_par_display_none():
    css = (RACINE / "web" / "observable" / "observablehq.config.js").read_text(encoding="utf-8")
    regle = re.search(r"\.hm-hp \{([^}]*)\}", css)
    assert regle, ".hm-hp n'est pas stylé — le pot de miel serait visible"
    corps = regle.group(1)
    assert "position: absolute" in corps and "-9999px" in corps
    assert "display: none" not in corps and "visibility: hidden" not in corps, (
        "un robot un peu sérieux saute ces deux propriétés : le champ redeviendrait "
        "décoratif au lieu de piéger"
    )
    page = PAGE.read_text(encoding="utf-8")
    assert 'aria-hidden="true"' in page and 'tabindex="-1"' in page, (
        "le pot de miel doit être retiré des lecteurs d'écran et du parcours clavier"
    )
