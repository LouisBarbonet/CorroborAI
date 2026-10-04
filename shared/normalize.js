// Partagé par le site (réponses pré-enregistrées) et le relais Cloudflare (clé de cache) :
// minuscules, espaces multiples réduits, ponctuation finale ignorée.
export function normalizeQuestion(s) {
  return String(s ?? "")
    .normalize("NFC")
    .toLowerCase()
    .replace(/[’`]/g, "'")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[\s?!.…;:,]+$/u, "");
}

// Repères citables dans les réponses : [R-XXX] ou [matricule/champ]
export const CITATION_RE = /\[([^\[\]\n]{1,80})\]/g;

// Tout texte entre crochets est affiché comme un repère cliquable : il doit donc correspondre à un repère réel.
export function extractCitations(text) {
  return [...String(text ?? "").matchAll(CITATION_RE)].map((m) => `[${m[1]}]`);
}
