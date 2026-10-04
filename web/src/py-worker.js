/* Web Worker : exécute le moteur Python CorroborIA dans le navigateur grâce à Pyodide.
   Les appels LLM passent par le relais Cloudflare (XHR synchrone, autorisé dans un worker) :
   aucune clé n'est présente côté navigateur. */
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
let py = null;

const progress = (message) => self.postMessage({ type: "progress", message });

const DRIVER = `
import json, sys
from pathlib import Path
sys.path.insert(0, "/home/pyodide")
from corroborai.engine import Engine
from corroborai import serialize
from corroborai.ai.feedback import FeedbackStore
from corroborai.ai.llm.relay import RelayRouter
from corroborai.report import build_csv, build_excel

FB_PATH = Path("/tmp/feedback.json")
FB = FeedbackStore(FB_PATH)
STATE = {}

def run_engine(paths_json, use_llm, relay_url, recorded_json, feedback_json):
    FB_PATH.write_text(feedback_json or "[]", encoding="utf-8")
    paths = json.loads(paths_json) or None
    router = RelayRouter(relay_url, json.loads(recorded_json or "{}"))
    res = Engine(router=router, feedback=FB, use_llm=bool(use_llm)).run(paths)
    STATE["res"] = res
    return serialize.dumps(serialize.to_payload(res))

def add_feedback(fid, verdict, commentaire, portee, auteur):
    f = STATE["res"].by_id(fid)
    if f is None:
        raise ValueError("Constat introuvable")
    FB.add(f, verdict, commentaire, portee, auteur)
    return FB_PATH.read_text(encoding="utf-8")

def export_file(kind):
    return build_excel(STATE["res"]) if kind == "xlsx" else build_csv(STATE["res"])
`;

async function fetchOk(url, as = "json") {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Téléchargement impossible : ${url} (HTTP ${r.status})`);
  return as === "json" ? r.json() : new Uint8Array(await r.arrayBuffer());
}

const handlers = {
  async init({ base, version }) {
    const v = `?v=${encodeURIComponent(version || "dev")}`; // contournement du cache : moteur = version du site
    progress("Téléchargement de Pyodide (Python dans le navigateur)…");
    self.importScripts(`${PYODIDE_URL}pyodide.js`);
    py = await self.loadPyodide({ indexURL: PYODIDE_URL });
    progress("Chargement de pandas, numpy et scikit-learn…");
    await py.loadPackage(["pandas", "numpy", "scikit-learn", "micropip"]);
    progress("Installation d'openpyxl et ftfy…");
    await py.pyimport("micropip").install(["openpyxl", "ftfy"]);
    progress("Chargement du moteur CorroborIA et des extractions…");
    const bundle = await fetchOk(new URL(`py/bundle.json${v}`, base));
    for (const [path, content] of Object.entries(bundle.files)) {
      const full = `/home/pyodide/${path}`;
      py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
      py.FS.writeFile(full, content);
    }
    const dataDir = "/home/pyodide/corroborai-participants";
    py.FS.mkdirTree(dataDir);
    for (const name of await fetchOk(new URL(`data/index.json${v}`, base))) {
      py.FS.writeFile(`${dataDir}/${name}`, await fetchOk(new URL(`data/${encodeURIComponent(name)}${v}`, base), "bytes"));
    }
    py.runPython(DRIVER);
    return { version: py.version };
  },

  async run({ files, useLlm, relayUrl, recorded, feedback }) {
    py.FS.mkdirTree("/tmp/uploads");
    const paths = {};
    for (const [k, buf] of Object.entries(files || {})) {
      const p = `/tmp/uploads/${k}.xlsx`;
      py.FS.writeFile(p, new Uint8Array(buf));
      paths[k] = p;
    }
    progress("Corroboration en cours (moteur Python)…");
    const fn = py.globals.get("run_engine");
    try {
      return JSON.parse(fn(JSON.stringify(paths), useLlm, relayUrl || "", JSON.stringify(recorded || {}), JSON.stringify(feedback || [])));
    } finally {
      fn.destroy();
    }
  },

  async addFeedback({ finding_id, verdict, commentaire, portee, auteur }) {
    const fn = py.globals.get("add_feedback");
    try {
      return JSON.parse(fn(finding_id, verdict, commentaire || "", portee, auteur || "expert"));
    } finally {
      fn.destroy();
    }
  },

  async exportFile({ kind }) {
    const fn = py.globals.get("export_file");
    const proxy = fn(kind);
    try {
      return proxy.toJs();
    } finally {
      proxy.destroy();
      fn.destroy();
    }
  },
};

self.onmessage = async (e) => {
  const { id, type, args } = e.data;
  try {
    const result = await handlers[type](args || {});
    const transfer = result instanceof Uint8Array ? [result.buffer] : [];
    self.postMessage({ id, ok: true, result }, transfer);
  } catch (err) {
    const msg = String(err?.message || err);
    self.postMessage({ id, ok: false, error: msg.length > 600 ? `${msg.slice(0, 600)}…` : msg });
  }
};
