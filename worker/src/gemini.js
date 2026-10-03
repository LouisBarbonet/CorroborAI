// Appel REST à Gemini : 2 nouvelles tentatives sur 429/5xx, puis modèle de repli.
import { HttpError } from "./lib.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const URL_TPL = (model) => `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;

export async function callGemini(env, { system, contents, json }, fetchImpl = fetch) {
  if (!env.GEMINI_API_KEY) throw new HttpError(503, "Le relais n'est pas configuré (clé Gemini absente).");
  const models = [env.GEMINI_MODEL || "gemini-flash-lite-latest", env.GEMINI_FALLBACK_MODEL].filter(Boolean);
  let lastStatus = 0;
  for (const model of models) {
    for (let attempt = 0; attempt < 3; attempt++) {
      let r;
      try {
        r = await fetchImpl(URL_TPL(model), {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: system }] },
            contents,
            generationConfig: { temperature: 0.2, maxOutputTokens: 4096, ...(json ? { responseMimeType: "application/json" } : {}) },
          }),
        });
      } catch {
        lastStatus = 502;
        await sleep(400 * 2 ** attempt);
        continue;
      }
      if (r.ok) {
        const data = await r.json();
        const text = (data?.candidates?.[0]?.content?.parts ?? []).map((p) => p.text ?? "").join("");
        if (text) return { text, model };
        lastStatus = 502;
        break; // réponse vide (filtrage…) : on essaie le modèle de repli
      }
      lastStatus = r.status;
      if (r.status === 429 || r.status >= 500) {
        await sleep(400 * 2 ** attempt);
        continue;
      }
      break; // autre 4xx : inutile de réessayer ce modèle
    }
  }
  if (lastStatus === 429) throw new HttpError(503, "Le quota du service Gemini est atteint pour le moment. Réessayez plus tard.");
  if (lastStatus >= 500) throw new HttpError(503, "Le service Gemini est momentanément surchargé. Réessayez dans quelques instants.");
  throw new HttpError(502, `Le service Gemini a refusé la requête (HTTP ${lastStatus}).`);
}
