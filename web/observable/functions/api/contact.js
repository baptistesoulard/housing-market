/**
 * POST /api/contact — relais du formulaire de contact de la page « À propos ».
 *
 * POURQUOI CE FICHIER EXISTE
 * Le site est 100 % statique : `observable build` produit du HTML dans `dist/`, que
 * Cloudflare sert depuis son CDN. Il n'y a donc AUCUN serveur pour recevoir un POST, et
 * un <form> posé tel quel ne partirait nulle part. Une Pages Function est le seul bout
 * de code serveur du projet — Cloudflare exécute automatiquement ce qu'il trouve dans
 * `functions/` à la racine du projet (ici `web/observable/`, cf. web/README.md).
 *
 * Ce n'est PAS l'API Flask de `api/` : celle-ci expose des calculs (queries, forecast) et
 * n'est pas hébergée. Les deux n'ont rien à voir et ne doivent pas fusionner — ce fichier
 * ne calcule rien, il valide trois champs et relaie.
 *
 * L'ADRESSE DE DESTINATION N'EST PAS DANS LE CODE, et c'est délibéré : le dépôt est
 * public, et une adresse personnelle écrite dans un fichier versionné est moissonnée par
 * les robots aussi sûrement que dans un mailto:. Elle vient de la variable
 * d'environnement CONTACT_TO (Cloudflare Pages → Settings → Environment variables).
 *
 * Variables attendues :
 *   RESEND_API_KEY  (secret)  clé API Resend — https://resend.com, 3 000 mails/mois
 *   CONTACT_TO      (secret)  adresse de destination
 *   CONTACT_FROM    (option.) expéditeur ; défaut = le domaine de bac à sable de Resend,
 *                             qui n'autorise l'envoi QUE vers l'adresse du compte. Pour
 *                             écrire ailleurs, vérifier un domaine chez Resend.
 *
 * Sans RESEND_API_KEY ou CONTACT_TO, la route répond 503 et la page affiche un message
 * clair au lieu d'avaler le message en silence — le pire des deux mondes serait un
 * formulaire qui remercie sans rien envoyer.
 */

const LIMITES = {nom: 120, email: 200, sujet: 80, message: 5000};
const MESSAGE_MIN = 10;

// Un formulaire public reçoit du spam de robots en quelques jours. Deux gardes sans
// service tiers ni énigme imposée au visiteur (un test que l'humain doit résoudre écarte
// aussi des humains — lecteurs d'écran en tête) :
//   1. le pot de miel : un champ que le CSS cache et qu'un humain ne voit donc jamais.
//      Les robots remplissent tout ce qu'ils trouvent ;
//   2. le délai : la page mesure le temps écoulé depuis son chargement, et un envoi parti
//      en moins de trois secondes n'a pas pu être tapé. C'est bien une DURÉE que la page
//      transmet, pas l'heure de son chargement : comparer l'horloge du visiteur à celle
//      du serveur ferait jeter en silence les messages de tous ceux dont la machine est
//      à l'heure près de quelques minutes — un mode de panne invisible des deux côtés.
// Si du spam passe malgré ça, l'étage suivant est Cloudflare Turnstile — même
// hébergeur, gratuit — à brancher ici avant l'envoi.
const DELAI_MINIMAL_MS = 3000;

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {"content-type": "application/json; charset=utf-8", "cache-control": "no-store"},
  });

/** Validation d'adresse volontairement large : le seul juge fiable est la délivrance. */
const emailPlausible = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);

const texte = (v, max) => (typeof v === "string" ? v.trim().slice(0, max) : "");

export async function onRequest({request, env}) {
  // UN seul gestionnaire plutôt qu'un onRequestPost doublé d'un onRequest fourre-tout :
  // quand les deux sont exportés, Cloudflare n'en retient qu'un et lequel n'est pas une
  // évidence à la lecture. Ici la méthode est vérifiée en clair.
  if (request.method !== "POST") {
    return new Response(JSON.stringify({ok: false, error: "methode"}), {
      status: 405,
      headers: {"content-type": "application/json; charset=utf-8", allow: "POST"},
    });
  }

  if (!env.RESEND_API_KEY || !env.CONTACT_TO) {
    return json({ok: false, error: "config"}, 503);
  }

  let corps;
  try {
    corps = await request.json();
  } catch {
    return json({ok: false, error: "format"}, 400);
  }

  // Pot de miel et délai : on répond 200 sans rien envoyer. Un robot qui reçoit une
  // erreur apprend la règle et réessaie ; un robot qui croit avoir réussi passe au
  // suivant.
  const depuisChargement = Number(corps._t);
  if (texte(corps._hp, 50) || !(depuisChargement >= DELAI_MINIMAL_MS)) {
    return json({ok: true});
  }

  const nom = texte(corps.nom, LIMITES.nom);
  const email = texte(corps.email, LIMITES.email);
  const sujet = texte(corps.sujet, LIMITES.sujet) || "Message";
  const message = texte(corps.message, LIMITES.message);

  if (!nom || !emailPlausible(email) || message.length < MESSAGE_MIN) {
    return json({ok: false, error: "champs"}, 400);
  }

  // Envoi en texte brut : aucun HTML à échapper, donc aucune façon pour un message reçu
  // d'injecter quoi que ce soit dans le client de messagerie qui l'affichera.
  const envoi = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.RESEND_API_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      from: env.CONTACT_FROM || "Baromètre du Logement <onboarding@resend.dev>",
      to: [env.CONTACT_TO],
      // reply_to porte l'adresse du visiteur : répondre depuis sa boîte suffit, sans
      // recopier une adresse à la main.
      reply_to: email,
      subject: `[Baromètre du Logement] ${sujet} — ${nom}`,
      text: `${message}\n\n—\nDe : ${nom} <${email}>\nSujet : ${sujet}\nEnvoyé depuis la page À propos du Baromètre du Logement.\n`,
    }),
  });

  if (!envoi.ok) {
    // Le détail du refus (clé invalide, domaine non vérifié, quota) part dans les logs
    // Cloudflare, pas dans la réponse : il n'apprend rien d'utile au visiteur et
    // renseignerait un attaquant sur la configuration.
    console.error("resend", envoi.status, await envoi.text());
    return json({ok: false, error: "envoi"}, 502);
  }

  return json({ok: true});
}

