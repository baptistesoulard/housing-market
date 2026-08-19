// Filtre de période GLOBAL — la frise à deux poignées de la barre latérale.
//
// Miroir du curseur « 📅 Période (années) » de la barre latérale Streamlit : un seul
// contrôle pour toutes les pages, au lieu des deux listes déroulantes qui vivaient
// auparavant dans chaque page.
//
// Deux particularités par rapport à Streamlit, qui tiennent au support :
//
// 1. Le site est un ensemble de pages HTML distinctes : naviguer d'un onglet à l'autre
//    RECHARGE la page. La position de la frise est donc persistée dans localStorage et
//    relue au montage — c'est ce qui donne l'illusion d'un contrôle unique qui suit
//    l'utilisateur d'un onglet à l'autre, comme la barre latérale Streamlit qui, elle,
//    survit aux changements d'onglet sans rien faire.
// 2. La barre latérale est rendue par Observable Framework, pas par les pages : le
//    contrôle est monté dans le DOM du `<nav id="observablehq-sidebar">` au lieu d'être
//    affiché en flux dans `main`.
//
// Comme les listes déroulantes qu'il remplace, ce filtre ne rogne que l'AFFICHAGE :
// cumuls glissants et moyennes mobiles restent calculés en amont, côté Python, sur
// l'historique complet — exactement comme `app.py` qui filtre APRÈS avoir calculé.
import {html} from "npm:htl";

const STORE_KEY = "hm.period.v1";
const THUMB = 14; // diamètre de la poignée, en px (doit suivre le CSS de la config)

// --- Persistance inter-pages -------------------------------------------------------
function readStored(min, max) {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE_KEY));
    if (Array.isArray(raw) && raw.length === 2) {
      const clamp = (v) => Math.max(min, Math.min(max, Math.round(+v)));
      const [a, b] = [clamp(raw[0]), clamp(raw[1])];
      if (Number.isFinite(a) && Number.isFinite(b)) return [Math.min(a, b), Math.max(a, b)];
    }
  } catch (e) {
    // localStorage indisponible (navigation privée, cookies bloqués) ou valeur illisible :
    // on retombe simplement sur la plage complète, comme au premier chargement.
  }
  return [min, max];
}

function writeStored(value) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(value));
  } catch (e) {
    // Écriture impossible : le filtre reste utilisable, il ne survit juste pas au
    // changement de page. Pas de quoi casser la page.
  }
}

// --- Le contrôle lui-même ----------------------------------------------------------
// Deux `<input type="range">` superposés (poignée basse / poignée haute) au-dessus d'un
// rail commun. Seules les poignées reçoivent les clics (`pointer-events` dans le CSS),
// si bien que les deux curseurs cohabitent sans se voler les événements.
export function periodInput({min, max, value = [min, max], label = "📅 Période (années)",
                             note = null} = {}) {
  const lo = html`<input type="range" min=${min} max=${max} step="1" value=${value[0]}
                         aria-label="Première année">`;
  const hi = html`<input type="range" min=${min} max=${max} step="1" value=${value[1]}
                         aria-label="Dernière année">`;
  const loTxt = html`<span class="hm-period-val"></span>`;
  const hiTxt = html`<span class="hm-period-val"></span>`;
  const fill = html`<div class="hm-period-fill"></div>`;
  const node = html`<div class="hm-period">
    <div class="hm-period-label">${label}</div>
    <div class="hm-period-values">${loTxt}${hiTxt}</div>
    <div class="hm-period-track"><div class="hm-period-rail"></div>${fill}${lo}${hi}</div>
    <div class="hm-period-bounds"><span>${min}</span><span>${max}</span></div>
    ${note ? html`<div class="hm-period-note">${note}</div>` : ""}
  </div>`;

  const pct = (v) => (max === min ? 0 : ((v - min) / (max - min)) * 100);
  // Le centre d'une poignée ne parcourt pas toute la largeur du rail : il va de
  // THUMB/2 à (largeur − THUMB/2). Sans cette correction, l'étiquette décrocherait de
  // la poignée aux deux extrémités.
  const atThumb = (p) => `calc(${p}% + ${(0.5 - p / 100) * THUMB}px)`;

  function refresh(source) {
    let a = +lo.value, b = +hi.value;
    if (a > b) {                       // les poignées ne se croisent pas : elles poussent
      if (source === hi) lo.value = a = b;
      else hi.value = b = a;
    }
    const [pa, pb] = [pct(a), pct(b)];
    fill.style.left = `${pa}%`;
    fill.style.width = `${pb - pa}%`;
    loTxt.textContent = a;
    hiTxt.textContent = b;
    loTxt.style.left = atThumb(pa);
    hiTxt.style.left = atThumb(pb);
    // Poignées superposées (typiquement les deux au maximum) : celle du bas deviendrait
    // inatteignable. On remonte `lo` dès qu'elle est dans la moitié haute du domaine.
    lo.style.zIndex = pa > 50 ? 4 : 2;
  }

  for (const el of [lo, hi]) {
    el.addEventListener("input", (event) => {
      event.stopPropagation();          // un seul événement sort du contrôle : le nôtre
      refresh(el);
      node.dispatchEvent(new Event("input", {bubbles: true}));
    });
  }

  Object.defineProperty(node, "value", {
    get: () => [+lo.value, +hi.value],
    set: (v) => {
      lo.value = Math.min(v[0], v[1]);
      hi.value = Math.max(v[0], v[1]);
      refresh();
    },
  });

  refresh();
  return node;
}

// --- Montage dans la barre latérale -------------------------------------------------
// Renvoie l'élément : à passer à `Generators.input(...)` côté page pour rendre la valeur
// réactive, SANS `view(...)` qui l'afficherait aussi en plein milieu de la page.
export function periodFilter({min, max, note = null} = {}) {
  const node = periodInput({min, max, value: readStored(min, max), note});
  node.addEventListener("input", () => writeStored(node.value));

  const nav = document.querySelector("#observablehq-sidebar");
  if (nav) {
    let slot = nav.querySelector("#hm-period-slot");
    if (!slot) {
      slot = document.createElement("div");
      slot.id = "hm-period-slot";
      // Sous le titre du site (premier <ol> de la barre latérale), au-dessus de la
      // liste des onglets — la place qu'occupe le curseur dans l'app Streamlit.
      const title = nav.querySelector("ol");
      if (title) title.after(slot);
      else nav.prepend(slot);
    }
    slot.replaceChildren(node);        // idempotent si le bloc est réexécuté
  }
  return node;
}
