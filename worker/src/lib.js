// Fonctions pures du relais (testées par vitest) : origine, validation stricte, consignes, clés de cache.
import { normalizeQuestion } from "../../shared/normalize.js";

export const JUSTIFIE = "Écart justifié";
export const ANOMALIE = "Anomalie";
export const MAX_QUESTION = 800;
export const MAX_MESSAGES = 8;
export const MAX_CASES = 25;
export const MAX_BODY_BYTES = 64 * 1024;

export class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// ------------------------------------------------------------------ origine
export function isAllowedOrigin(origin, allowedCsv) {
  if (!origin) return false;
  const allowed = String(allowedCsv || "").split(",").map((s) => s.trim()).filter(Boolean);
  return allowed.some((a) => {
    if (origin === a) return true;
    // http://localhost et http://127.0.0.1 : tout port autorisé (développement)
    return /^http:\/\/(localhost|127\.0\.0\.1)$/.test(a) && (origin === a || origin.startsWith(`${a}:`));
  });
}

export function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

// ------------------------------------------------------------------ validation
const isStr = (v, max) => typeof v === "string" && v.length <= max;
const strOrNull = (v, max, name) => {
  if (v === null || v === undefined) return null;
  if (!isStr(v, max)) throw new HttpError(400, `Champ « ${name} » invalide ou trop long.`);
  return v;
};
const int = (v, name, max = 100000) => {
  if (!Number.isInteger(v) || v < 0 || v > max) throw new HttpError(400, `Champ « ${name} » invalide.`);
  return v;
};

export function validateJudge(body, champs) {
  if (!body || typeof body !== "object") throw new HttpError(400, "Corps de requête invalide.");
  if (!champs.includes(body.champ)) throw new HttpError(400, "Champ inconnu du mapping.");
  if (!Array.isArray(body.cas) || body.cas.length < 1 || body.cas.length > MAX_CASES) {
    throw new HttpError(400, `Entre 1 et ${MAX_CASES} cas par requête.`);
  }
  const cas = body.cas.map((c, i) => {
    if (!c || typeof c !== "object" || !isStr(c.id, 120) || !c.id) throw new HttpError(400, `Cas ${i + 1} : identifiant invalide.`);
    const a = c.analyse_locale;
    if (!a || typeof a !== "object" || ![JUSTIFIE, ANOMALIE].includes(a.verdict)) throw new HttpError(400, `Cas ${i + 1} : analyse locale invalide.`);
    if (typeof a.confiance !== "number" || a.confiance < 0 || a.confiance > 1) throw new HttpError(400, `Cas ${i + 1} : confiance invalide.`);
    if (!Array.isArray(a.signaux) || a.signaux.length > 10 || !a.signaux.every((s) => isStr(s, 400))) {
      throw new HttpError(400, `Cas ${i + 1} : signaux invalides.`);
    }
    return {
      id: c.id,
      valeur_systeme_A: strOrNull(c.valeur_systeme_A, 400, "valeur_systeme_A"),
      valeur_attendue_selon_regle: strOrNull(c.valeur_attendue_selon_regle, 400, "valeur_attendue_selon_regle"),
      valeur_systeme_B: strOrNull(c.valeur_systeme_B, 400, "valeur_systeme_B"),
      analyse_locale: { verdict: a.verdict, confiance: a.confiance, signaux: a.signaux, justification: strOrNull(a.justification, 800, "justification") ?? "" },
    };
  });
  return { champ: body.champ, cas };
}

export function validateSummary(body) {
  if (!body || typeof body !== "object") throw new HttpError(400, "Corps de requête invalide.");
  if (!Array.isArray(body.groupes) || body.groupes.length > 40) throw new HttpError(400, "Groupes invalides.");
  return {
    enregistrements: int(body.enregistrements, "enregistrements"),
    anomalies: int(body.anomalies, "anomalies"),
    justifies: int(body.justifies, "justifies"),
    conformes: int(body.conformes, "conformes"),
    groupes: body.groupes.map((g, i) => {
      if (!g || typeof g !== "object" || !isStr(g.champ, 60) || !isStr(g.diagnostic_type, 80)) throw new HttpError(400, `Groupe ${i + 1} invalide.`);
      if (!Array.isArray(g.matricules) || g.matricules.length > 100 || !g.matricules.every((m) => isStr(m, 20))) {
        throw new HttpError(400, `Groupe ${i + 1} : matricules invalides.`);
      }
      return { champ: g.champ, diagnostic_type: g.diagnostic_type, nombre: int(g.nombre, "nombre"), matricules: g.matricules,
        exemple: strOrNull(g.exemple, 1000, "exemple") ?? "" };
    }),
  };
}

export function validateChat(body) {
  if (!body || typeof body !== "object" || !Array.isArray(body.messages)) throw new HttpError(400, "Corps de requête invalide.");
  const { messages } = body;
  if (messages.length < 1 || messages.length > MAX_MESSAGES) throw new HttpError(400, `Conversation trop longue (${MAX_MESSAGES} messages maximum).`);
  const clean = messages.map((m) => {
    if (!m || !["user", "assistant"].includes(m.role) || typeof m.content !== "string") throw new HttpError(400, "Message invalide.");
    const content = m.content.trim();
    if (!content) throw new HttpError(400, "Message vide.");
    if (content.length > (m.role === "user" ? MAX_QUESTION : 2000)) {
      throw new HttpError(400, `Question trop longue (${MAX_QUESTION} caractères maximum).`);
    }
    return { role: m.role, content };
  });
  if (clean[clean.length - 1].role !== "user") throw new HttpError(400, "Le dernier message doit être une question.");
  return { messages: clean };
}

// ------------------------------------------------------------------ consignes (construites ici, jamais par le client)
// Même consigne de format que le serveur Python : le schéma JSON attendu est ajouté à la consigne système.
const withSchema = (system, schema) =>
  `${system}\n\nRéponds UNIQUEMENT par un objet JSON valide conforme à ce schéma :\n${JSON.stringify(schema)}`;

export function buildJudge(data, v) {
  return {
    system: withSchema(data.prompts.judge_system, data.prompts.judge_schema),
    contents: [{ role: "user", parts: [{ text: JSON.stringify({ champ: v.champ, regle_mapping: data.regles_par_champ[v.champ] ?? "", cas: v.cas }, null, 1) }] }],
    json: true,
  };
}

export function buildSummary(data, v) {
  return {
    system: withSchema(data.prompts.summary_system, data.prompts.summary_schema),
    contents: [{ role: "user", parts: [{ text: JSON.stringify(v, null, 1) }] }],
    json: true,
  };
}

export function buildChat(data, v) {
  return {
    system: withSchema(data.prompts.chat_system.replace("{{context}}", data.context), data.prompts.chat_schema),
    contents: v.messages.map((m) => ({ role: m.role === "user" ? "user" : "model", parts: [{ text: m.content }] })),
    json: true,
  };
}

// ------------------------------------------------------------------ réponses du modèle
export function repairJson(text) {
  let t = String(text ?? "").trim().replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/, "").trim();
  try {
    return JSON.parse(t);
  } catch {
    const start = t.indexOf("{");
    if (start < 0) throw new HttpError(502, "Réponse du modèle illisible.");
    let depth = 0;
    let inStr = false;
    for (let i = start; i < t.length; i++) {
      const ch = t[i];
      if (inStr) { if (ch === "\\") i++; else if (ch === '"') inStr = false; continue; }
      if (ch === '"') inStr = true;
      else if (ch === "{") depth++;
      else if (ch === "}" && --depth === 0) {
        t = t.slice(start, i + 1).replace(/,\s*([}\]])/g, "$1");
        return JSON.parse(t);
      }
    }
    throw new HttpError(502, "Réponse du modèle incomplète.");
  }
}

const normVerdict = (v) => {
  const s = String(v ?? "").toLowerCase();
  if (s.includes("anomal") || s.includes("erreur")) return ANOMALIE;
  if (s.includes("justif") || s.includes("écart") || s.includes("ecart")) return JUSTIFIE;
  return null;
};

export function checkJudgeOutput(out, v) {
  const ids = new Set(v.cas.map((c) => c.id));
  const cas = [];
  for (const c of out?.cas ?? []) {
    const verdict = normVerdict(c?.verdict);
    if (ids.has(c?.id) && verdict) {
      cas.push({ id: c.id, verdict, confiance: Math.max(0, Math.min(1, Number(c.confiance) || 0.5)), justification: String(c.justification ?? "").trim() });
      ids.delete(c.id);
    }
  }
  if (ids.size) throw new HttpError(502, "Réponse du modèle incomplète.");
  return { cas };
}

export function checkSummaryOutput(out) {
  if (typeof out?.resume !== "string" || !Array.isArray(out?.causes_racines)) throw new HttpError(502, "Synthèse du modèle invalide.");
  return { resume: out.resume, causes_racines: out.causes_racines.slice(0, 20) };
}

export function checkChatOutput(out) {
  // Tolérant : clé « reponse » attendue, sinon variantes courantes ou première valeur textuelle.
  const r = typeof out === "string" ? out
    : out?.reponse ?? out?.["réponse"] ?? out?.response ?? out?.answer ?? Object.values(out ?? {}).find((x) => typeof x === "string");
  if (typeof r !== "string" || !r.trim()) throw new HttpError(502, "Réponse vide du modèle.");
  return { reponse: r.trim() };
}

// ------------------------------------------------------------------ cache
export function stableStringify(v) {
  if (Array.isArray(v)) return `[${v.map(stableStringify).join(",")}]`;
  if (v && typeof v === "object") return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${stableStringify(v[k])}`).join(",")}}`;
  return JSON.stringify(v);
}

export function normalizedForCache(route, v) {
  if (route !== "chat") return v;
  return { messages: v.messages.map((m) => ({ role: m.role, content: normalizeQuestion(m.content) })) };
}

export async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function cacheKey(route, model, system, v) {
  const fingerprint = (await sha256(system)).slice(0, 16);
  return `${route}:${await sha256(`${model}\u001f${fingerprint}\u001f${stableStringify(normalizedForCache(route, v))}`)}`;
}

// Repères inventés par le modèle : on retire les crochets (aucun lien mort), les repères réels sont conservés.
export function sanitizeCitations(text, reperes) {
  return String(text).replace(/\[([^\[\]\n]{1,80})\]/g, (m, inner) => (reperes.has(`[${inner}]`) ? m : inner));
}
