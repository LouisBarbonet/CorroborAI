// Relais Cloudflare de CorroborIA : garde la clé Gemini secrète et n'accepte que des requêtes structurées.
// Protections, dans l'ordre : origine (CORS) → validation stricte → cache KV (gratuit) → limite par IP →
// plafond quotidien global → appel Gemini. Routes : POST /judge, /summary, /chat ; GET /health.
import data from "./data.generated.json";
import { callGemini } from "./gemini.js";
import {
  buildChat, buildJudge, buildSummary, cacheKey, checkChatOutput, checkJudgeOutput, checkSummaryOutput, corsHeaders,
  HttpError, isAllowedOrigin, MAX_BODY_BYTES, repairJson, sanitizeCitations, validateChat, validateJudge, validateSummary,
} from "./lib.js";

const CACHE_TTL = 60 * 60 * 24 * 30; // 30 jours
const REPERES = new Set(data.reperes);
const clean = (route, out) => (route === "chat" ? { ...out, reponse: sanitizeCitations(out.reponse, REPERES) } : out);

const ROUTES = {
  judge: { validate: (b) => validateJudge(b, data.champs), build: buildJudge, check: checkJudgeOutput },
  summary: { validate: validateSummary, build: buildSummary, check: checkSummaryOutput },
  chat: { validate: validateChat, build: buildChat, check: checkChatOutput },
};

const json = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8", ...headers } });

async function dailyGate(env) {
  const limit = Number(env.DAILY_LIMIT || 100);
  const key = `daily:${new Date().toISOString().slice(0, 10)}`;
  const used = Number((await env.CACHE.get(key)) || 0);
  if (used >= limit) {
    throw new HttpError(429, "Le quota quotidien du relais est atteint. Les questions d'exemple (réponses pré-enregistrées) restent disponibles ; réessayez demain.");
  }
  await env.CACHE.put(key, String(used + 1), { expirationTtl: 60 * 60 * 48 });
}

async function handle(route, request, env, origin) {
  const spec = ROUTES[route];
  // 1. Origine
  if (!isAllowedOrigin(origin, env.ALLOWED_ORIGINS)) throw new HttpError(403, "Origine non autorisée.");
  // 2. Validation stricte du corps
  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) throw new HttpError(413, "Requête trop volumineuse.");
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    throw new HttpError(400, "Corps JSON invalide.");
  }
  const v = spec.validate(body);
  const prompt = spec.build(data, v);
  const model = env.GEMINI_MODEL || "gemini-flash-lite-latest";
  // 3. Cache (avant les limites : une question déjà posée ne coûte rien)
  const key = await cacheKey(route, model, prompt.system, v);
  const hit = await env.CACHE.get(key, "json");
  if (hit) return { ...clean(route, hit), cached: true };
  // 4. Limite par IP
  const ip = request.headers.get("CF-Connecting-IP") || "inconnue";
  if (env.RATE_LIMITER) {
    const { success } = await env.RATE_LIMITER.limit({ key: ip });
    if (!success) throw new HttpError(429, "Trop de questions en peu de temps : patientez une minute avant de réessayer.");
  }
  // 5. Plafond quotidien global
  await dailyGate(env);
  // 6. Gemini
  const { text, model: used } = await callGemini(env, prompt);
  const out = clean(route, { ...spec.check(repairJson(text), v), modele: used });
  await env.CACHE.put(key, JSON.stringify(out), { expirationTtl: CACHE_TTL });
  return { ...out, cached: false };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "";
    const allowed = isAllowedOrigin(origin, env.ALLOWED_ORIGINS);
    const cors = allowed ? corsHeaders(origin) : {};

    if (request.method === "OPTIONS") return new Response(null, { status: allowed ? 204 : 403, headers: cors });
    if (url.pathname === "/health" && request.method === "GET") {
      return json({ ok: true, service: "corroboria-relais", modele: env.GEMINI_MODEL, repli: env.GEMINI_FALLBACK_MODEL,
        cle_configuree: Boolean(env.GEMINI_API_KEY), donnees: data.genere_le }, 200, cors);
    }
    const route = url.pathname.replace(/^\/+/, "");
    if (request.method !== "POST" || !ROUTES[route]) return json({ erreur: "Route inconnue." }, 404, cors);
    try {
      return json(await handle(route, request, env, origin), 200, cors);
    } catch (e) {
      const status = e instanceof HttpError ? e.status : 500;
      return json({ erreur: e instanceof HttpError ? e.message : "Erreur interne du relais." }, status, cors);
    }
  },
};
