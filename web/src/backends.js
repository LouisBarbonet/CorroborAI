// Deux implémentations de la même interface :
// - ApiBackend    : serveur Python local (FastAPI) ;
// - StaticBackend : site statique (GitHub Pages / hors ligne) = instantané embarqué + moteur Python dans le
//                   navigateur (Pyodide, chargé à la demande) + relais Cloudflare pour le LLM.
import PyWorker from "./py-worker.js?worker&inline";

const FEEDBACK_KEY = "corroboria.feedback.v1";

export function download(bytes, filename, type) {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function jsonOrThrow(r) {
  let body = {};
  try { body = await r.json(); } catch { /* corps vide */ }
  if (!r.ok) throw new Error(body.detail || body.erreur || `HTTP ${r.status}`);
  return body;
}

// ------------------------------------------------------------------ serveur Python local
export class ApiBackend {
  mode = "python";
  label = "Serveur Python local";

  async api(path, opts) {
    return jsonOrThrow(await fetch(`api/${path}`, opts));
  }

  summary() { return this.api("summary"); }
  findings(params) { return this.api(`findings?${new URLSearchParams(params)}`); }
  finding(id) { return this.api(`findings/${encodeURIComponent(id)}`); }

  run({ files = {}, useLlm = true } = {}) {
    const body = new FormData();
    for (const [k, f] of Object.entries(files)) body.append(k, f);
    return this.api(`run?use_llm=${useLlm}`, { method: "POST", body });
  }

  feedback(fb) {
    return this.api("feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fb) });
  }

  clearFeedback() { return this.api("feedback", { method: "DELETE" }); }

  async exportFile(kind) {
    const r = await fetch(`api/export.${kind}`);
    if (!r.ok) throw new Error(`Export impossible (HTTP ${r.status})`);
    download(await r.arrayBuffer(), `rapport_corroboration.${kind}`, r.headers.get("Content-Type"));
  }

  chat(messages) {
    return this.api("chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages }) });
  }
}

// ------------------------------------------------------------------ moteur Pyodide (Web Worker)
class EngineClient {
  constructor(onProgress) {
    this.onProgress = onProgress;
    this.worker = null;
    this.ready = null;
    this.seq = 0;
    this.pending = new Map();
  }

  start(base) {
    if (!this.ready) {
      this.worker = new PyWorker();
      this.worker.onmessage = (e) => {
        const m = e.data;
        if (m.type === "progress") return this.onProgress?.(m.message);
        const p = this.pending.get(m.id);
        if (!p) return;
        this.pending.delete(m.id);
        m.ok ? p.resolve(m.result) : p.reject(new Error(m.error));
      };
      this.ready = this.call("init", { base, version: __APP_VERSION__ }).catch((err) => {
        this.worker.terminate();
        this.ready = null;
        throw new Error(`Le moteur Python n'a pas pu démarrer : ${err.message}`);
      });
    }
    return this.ready;
  }

  call(type, args, transfer = []) {
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ id, type, args }, transfer);
    });
  }
}

// ------------------------------------------------------------------ site statique
export class StaticBackend {
  mode = "static";

  constructor(snapshot, relayUrl, onProgress) {
    this.relayUrl = (relayUrl || "").replace(/\/+$/, "");
    this.recorded = snapshot.recorded || {};
    this.engine = new EngineClient(onProgress);
    this.engineRan = false;
    this.label = `Version web · instantané du ${snapshot.summary.date_execution.slice(0, 10)}`;
    this.setPayload(snapshot, true);
  }

  setPayload(payload, fromSnapshot = false) {
    this.data = payload;
    this.byId = new Map(payload.findings.map((f) => [f.id, f]));
    const llm = payload.summary.llm;
    if (fromSnapshot) {
      // L'état des fournisseurs de la machine de génération n'a pas de sens en ligne : on décrit le relais.
      llm.fournisseurs = [
        { fournisseur: "relais Cloudflare → Gemini", modele: (llm.utilise[0] || "").split("/")[1] || "gemini", local: false,
          disponible: Boolean(this.relayUrl),
          detail: this.relayUrl ? "clé Gemini gardée côté serveur (secret Cloudflare)" : "aucun relais configuré dans ce build" },
        { fournisseur: "gabarit-local", modele: "", disponible: true, local: true, detail: "toujours disponible (aucun appel externe)" },
      ];
      llm.ordre = ["relais", "gabarit-local"];
      llm.instantane = true;
    }
  }

  feedbackList() {
    try { return JSON.parse(localStorage.getItem(FEEDBACK_KEY) || "[]"); } catch { return []; }
  }

  saveFeedback(list) {
    try { localStorage.setItem(FEEDBACK_KEY, JSON.stringify(list)); } catch { /* stockage indisponible */ }
  }

  async compute({ files = {}, useLlm = true } = {}) {
    await this.engine.start(new URL(".", location.href).href);
    const buffers = {};
    for (const [k, f] of Object.entries(files)) buffers[k] = await f.arrayBuffer();
    const payload = await this.engine.call("run", {
      files: buffers, useLlm, relayUrl: this.relayUrl, recorded: this.recorded, feedback: this.feedbackList(),
    }, Object.values(buffers));
    this.setPayload(payload);
    this.engineRan = true;
    this.label = "Moteur Python exécuté dans le navigateur (Pyodide)";
    return payload.summary;
  }

  async summary() { return this.data.summary; }

  async findings({ verdict, champ, niveau, q, a_valider } = {}) {
    const ql = (q || "").toLowerCase();
    return this.data.findings.filter((f) => (!verdict || f.verdict === verdict) && (!champ || f.champ_b === champ)
      && (a_valider === undefined || f.a_valider === (a_valider === true || a_valider === "true"))
      && (!niveau || f.niveau.startsWith(niveau))
      && (!ql || `${f.matricule} ${f.employe} ${f.champ_b} ${f.valeur_a} ${f.valeur_b} ${f.justification}`.toLowerCase().includes(ql)));
  }

  async finding(id) {
    const f = this.byId.get(id);
    if (!f) throw new Error("Constat introuvable");
    return f;
  }

  run({ files = {}, useLlm = true } = {}) { return this.compute({ files, useLlm }); }

  async feedback(fb) {
    if (!this.engineRan) await this.compute();
    this.saveFeedback(await this.engine.call("addFeedback", fb));
    const summary = await this.compute();
    return { constats_impactes: this.data.findings.filter((f) => f.niveau === "Expert").map((f) => f.id), compteurs: summary.compteurs };
  }

  async clearFeedback() {
    this.saveFeedback([]);
    if (this.engineRan) await this.compute();
    return { ok: true };
  }

  async exportFile(kind) {
    if (!this.engineRan) await this.compute();
    const bytes = await this.engine.call("exportFile", { kind });
    download(bytes, `rapport_corroboration.${kind}`, kind === "xlsx"
      ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" : "text/csv;charset=utf-8");
  }

  async chat(messages) {
    if (!this.relayUrl) throw new Error("Aucun relais LLM n'est configuré pour cette version du site.");
    let r;
    try {
      r = await fetch(`${this.relayUrl}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages }) });
    } catch {
      throw new Error("Le relais LLM est injoignable (réseau ou mode hors ligne).");
    }
    const d = await jsonOrThrow(r);
    return { reponse: d.reponse, cached: Boolean(d.cached), fournisseur: `gemini/${d.modele}` };
  }
}
