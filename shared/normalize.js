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

export function extractCitations(text) {
  return [...String(text ?? "").matchAll(CITATION_RE)].map((m) => `[${m[1]}]`)
    .filter((c) => /^\[(R-[A-Z-]+|\d{5,8}\/[A-Za-z()]+)\]$/.test(c) || c.includes("/") || c.startsWith("[R-"));
}
