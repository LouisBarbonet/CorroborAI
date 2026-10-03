"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => (v === null || v === undefined || v === "" ? "∅" : String(v))
  .replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const VERDICTS = ["Anomalie", "Écart justifié", "Conforme"];
const state = { verdict: "Anomalie", champ: "", niveau: "", q: "", review: false, summary: null };

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) { /* ignore */ }
    throw new Error(msg);
  }
  return r.json();
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 3500);
}

const loading = (on) => $("#loading").classList.toggle("hidden", !on);
const vClass = (v) => v.split(" ")[0];
function levelBadge(niveau, decidePar) {
  const k = niveau.startsWith("1") ? "lvl1" : niveau.startsWith("2") ? "lvl2" : niveau.startsWith("3") ? "lvl3" : "lvlE";
  const label = niveau.startsWith("Expert") ? "Expert" : niveau;
  return `<span class="badge ${k}" title="${esc(decidePar)}">${esc(label)}</span>`;
}

// ------------------------------------------------------------------ résumé
function renderSummary(s) {
  state.summary = s;
  const c = s.compteurs;
  const kpis = [
    ["red", c["Anomalie"], "Anomalies réelles", "Anomalie"],
    ["amber", c["Écart justifié"], "Écarts justifiés automatiquement", "Écart justifié"],
    ["green", c["Conforme"], "Conformes", "Conforme"],
    ["blue", c.a_valider, "À valider par un expert", "review"],
    ["", c.total, `Constats (${s.nb_lignes.source} lignes A × champs du mapping)`, ""],
  ];
  $("#kpis").innerHTML = kpis.map(([cls, v, l, key]) =>
    `<div class="kpi ${cls}" data-key="${key}"><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`).join("");
  document.querySelectorAll(".kpi").forEach((el) => el.addEventListener("click", () => {
    const k = el.dataset.key;
    if (k === "review") { state.review = true; $("#reviewOnly").checked = true; state.verdict = ""; }
    else { state.verdict = k; state.review = false; $("#reviewOnly").checked = false; }
    renderChips(); loadFindings();
    $("#table").scrollIntoView({ behavior: "smooth" });
  }));

  const syn = s.synthese || {};
  $("#synthText").textContent = syn.resume || "";
  $("#synthProvider").textContent = syn.fournisseur ? `générée par : ${syn.fournisseur}` : "";
  $("#causes").innerHTML = `<div class="causes">${(syn.causes_racines || []).map((c) =>
    `<div class="cause"><b>${esc(c.cause)}</b> · ${esc(c.nombre)} cas · <span class="muted">${esc((c.champs || []).join(", "))}</span><br>${esc(c.recommandation)}</div>`).join("")}</div>`;

  $("#calibration").innerHTML = (s.calibration_regles || []).map((cal) =>
    `<div class="callout"><b>Calibration de règle ${esc(cal.regle)}</b> — ${esc(cal.texte_mapping)}<br>
     Concordance avec le Système B : ${Object.entries(cal.interpretations).map(([k, v]) => `${esc(k)} <b>${esc(v)}</b>`).join(" · ")}.<br>${esc(cal.conclusion)}</div>`).join("");

  const sel = $("#fieldFilter");
  const cur = sel.value;
  sel.innerHTML = `<option value="">Tous les champs</option>` + s.champs.map((c) => `<option>${esc(c)}</option>`).join("");
  sel.value = cur;

  const llm = s.llm || {};
  const used = (llm.utilise || []).join(", ") || llm.actif;
  const b = $("#llmBadge");
  b.textContent = `IA : ${used || "—"}`;
  b.title = (llm.fournisseurs || []).map((p) => `${p.fournisseur}: ${p.disponible ? "✓" : "✗"} ${p.detail}`).join("\n");

  $("#coverage").innerHTML = `<table><thead><tr><th>Champ A</th><th>Champ B</th><th>Ligne</th><th>Statut</th></tr></thead><tbody>${
    s.couverture_mapping.map((r) => `<tr><td>${esc(r.champ_a)}</td><td>${esc(r.champ_b)}</td><td>${esc(r.ligne_excel)}</td><td>${esc(r.statut)}</td></tr>`).join("")}</tbody></table>`;
  $("#providers").innerHTML = `<table><thead><tr><th>Ordre</th><th>Fournisseur</th><th>Modèle</th><th>État</th><th>Local</th></tr></thead><tbody>${
    (llm.fournisseurs || []).map((p, i) => `<tr><td>${i + 1}</td><td>${esc(p.fournisseur)}</td><td>${esc(p.modele)}</td><td>${p.disponible ? "✓ " : "✗ "}${esc(p.detail)}</td><td>${p.local ? "oui" : "non"}</td></tr>`).join("")}</tbody></table>`;
  const ml = s.ml || {};
  const cacheNote = llm.reponses_cache ? ` · ${llm.reponses_cache} réponse(s) LLM rejouée(s) depuis le cache` : "";
  $("#mlInfo").innerHTML = `<p><b>LLM utilisé :</b> ${esc(used)}${esc(cacheNote)}</p>`;
  $("#mlInfo").innerHTML += `<p><b>ML :</b> ${esc(ml.modele)} — ${esc(ml.exemples_entrainement)} exemples d'entraînement (verdicts déterministes)
    + ${esc(ml.corrections_expert)} correction(s) expert. Corrections expert actives : ${esc(s.corrections_expert)}.</p>`;
  const intact = (s.integrite || []).every((i) => i.intact);
  $("#integrity").innerHTML = `<p><b>Intégrité des sources :</b> ${intact ? "✓ fichiers inchangés (sha256 conformes au manifest)" : "⚠ écart sha256 détecté"} ·
    exécution du ${esc(s.date_execution)} (${esc(s.duree_s)} s)</p>`;
}

// ------------------------------------------------------------------ tableau
function renderChips() {
  const c = state.summary ? state.summary.compteurs : {};
  const opts = [["", "Tous", c.total], ...VERDICTS.map((v) => [v, v, c[v]])];
  $("#verdictChips").innerHTML = opts.map(([v, l, n]) =>
    `<button class="chip ${state.verdict === v ? "active" : ""}" data-v="${esc(v)}">${esc(l)} <span class="muted">${n ?? ""}</span></button>`).join("");
  document.querySelectorAll(".chip").forEach((el) => el.addEventListener("click", () => {
    state.verdict = el.dataset.v === "∅" ? "" : el.dataset.v;
    renderChips(); loadFindings();
  }));
}

async function loadFindings() {
  const p = new URLSearchParams();
  if (state.verdict) p.set("verdict", state.verdict);
  if (state.champ) p.set("champ", state.champ);
  if (state.niveau) p.set("niveau", state.niveau);
  if (state.q) p.set("q", state.q);
  if (state.review) p.set("a_valider", "true");
  const rows = await api(`/api/findings?${p}`);
  $("#table tbody").innerHTML = rows.map((f) => {
    const differs = f.valeur_attendue !== f.valeur_b;
    return `<tr data-id="${esc(f.id)}">
      <td><div class="prio">${f.priorite ? `<b>${f.priorite}</b><div class="bar"><span style="width:${f.priorite}%"></span></div>` : '<span class="muted">—</span>'}</div></td>
      <td><span class="badge ${vClass(f.verdict)}">${esc(f.verdict)}</span>${f.a_valider ? ' <span class="badge review">à valider</span>' : ""}</td>
      <td>${esc(f.employe)}<br><span class="muted small">${esc(f.matricule)} · ${esc(f.type_affectation)} · poste ${esc(f.code_poste)}</span></td>
      <td><b>${esc(f.champ_b)}</b><br><span class="muted small">${esc(f.champ_a)}</span></td>
      <td class="val">${esc(f.valeur_a).replaceAll(" | ", "<br>")}</td>
      <td class="val">${esc(f.valeur_attendue)}</td>
      <td class="val ${differs && f.verdict === "Anomalie" ? "diff" : ""}">${esc(f.valeur_b)}</td>
      <td>${levelBadge(f.niveau, f.decide_par)}<br><span class="muted small">${esc(f.decide_par)}</span></td>
      <td>${Math.round(f.confiance * 100)} %</td></tr>`;
  }).join("") || `<tr><td colspan="9" class="muted">Aucun constat pour ces filtres.</td></tr>`;
  $("#tableInfo").textContent = `${rows.length} constat(s) affiché(s). Cliquez sur une ligne pour voir la justification, les preuves et corriger le verdict.`;
  document.querySelectorAll("#table tbody tr[data-id]").forEach((tr) => tr.addEventListener("click", () => openFinding(tr.dataset.id)));
}

// ------------------------------------------------------------------ détail
function jsonBlock(obj) {
  return `<pre class="json">${esc(JSON.stringify(obj, null, 2))}</pre>`;
}

function historyTable(h) {
  if (!Array.isArray(h) || !h.length) return "";
  return `<table class="small-table"><thead><tr><th>Date d'effet</th><th>Unité adm.</th><th>H/sem.</th><th>H/jour</th></tr></thead><tbody>${
    h.map((r) => `<tr><td>${esc(r.DateEffet)}</td><td>${esc(r["Unité"])}</td><td>${esc(r.HeuresSemaine)}</td><td>${esc(r.HeuresJour)}</td></tr>`).join("")}</tbody></table>`;
}

async function openFinding(id) {
  const f = await api(`/api/findings/${encodeURIComponent(id)}`);
  $("#dVerdict").className = `badge ${vClass(f.verdict)}`;
  $("#dVerdict").textContent = f.verdict;
  $("#dReview").innerHTML = `${f.a_valider ? '<span class="badge review">à valider</span> ' : ""}${levelBadge(f.niveau, f.decide_par)}
    <span class="muted small">confiance ${Math.round(f.confiance * 100)} % · priorité ${f.priorite}</span>`;
  const ev = { ...f.preuves };
  const hist = ev.historique_poste;
  delete ev.historique_poste;
  const ia = f.ia || {};
  const signals = (ia.signaux || []).map((s) => `<li>${esc(s)}</li>`).join("");
  const llm = ia.llm ? `<p><b>LLM (${esc(ia.llm.fournisseur)})</b> : ${esc(ia.llm.verdict)} (${Math.round(ia.llm.confiance * 100)} %) — ${esc(ia.llm.justification)}</p>` : "";
  const local = ia.analyse_locale ? `<p><b>Analyse locale</b> : ${esc(ia.analyse_locale.verdict)} (${Math.round(ia.analyse_locale.confiance * 100)} %)</p>` : "";
  const ml = ia.ml_proba_anomalie !== undefined ? `<p><b>Modèle ML</b> : P(anomalie) = ${Math.round(ia.ml_proba_anomalie * 100)} %${ia.atypicite !== undefined ? ` · atypicité ${Math.round(ia.atypicite * 100)} %` : ""}</p>` : "";
  const before = ia.avant_expert ? `<p class="callout">Verdict initial : <b>${esc(ia.avant_expert.verdict)}</b> (${esc(ia.avant_expert.decide_par)}) — ${esc(ia.avant_expert.justification)}</p>` : "";

  $("#drawerBody").innerHTML = `
    <div>
      <h2>${esc(f.employe)} · ${esc(f.champ_b)}</h2>
      <p class="muted small">Matricule ${esc(f.matricule)} · affectation ${esc(f.type_affectation)} · poste ${esc(f.code_poste)} · emploi ${esc(f.code_emploi)} · ${esc(f.description)}</p>
    </div>
    <div class="values">
      <div><span>Système A (source) · ${esc(f.champ_a)}</span><code>${esc(f.valeur_a)}</code></div>
      <div><span>Attendue selon la règle</span><code>${esc(f.valeur_attendue)}</code></div>
      <div><span>Système B (cible) · ${esc(f.champ_b)}</span><code>${esc(f.valeur_b)}</code></div>
    </div>
    <section><h3>Pourquoi ce verdict</h3><p>${esc(f.justification)}</p>
      ${f.diagnostic ? `<p class="callout"><b>Cause probable :</b> ${esc(f.diagnostic)}</p>` : ""}${before}</section>
    <section><h3>Règle appliquée</h3>
      <dl class="kv"><dt>Identifiant</dt><dd><code>${esc(f.regle_id)}</code></dd>
      <dt>Texte (mapping)</dt><dd>${esc(f.regle_texte)}</dd>
      <dt>Décidé par</dt><dd>${esc(f.decide_par)}</dd>
      <dt>Motif (signature)</dt><dd><code>${esc(f.signature)}</code></dd></dl></section>
    ${signals || llm || local || ml ? `<section><h3>Analyse IA</h3>${signals ? `<ul class="signals">${signals}</ul>` : ""}${local}${llm}${ml}</section>` : ""}
    ${hist ? `<section><h3>Historique du poste (détail du poste)</h3>${historyTable(hist)}</section>` : ""}
    <section><h3>Preuves et données utilisées</h3>${jsonBlock(ev)}</section>
    <section><h3>Corriger le verdict (expert fonctionnel)</h3>
      <form class="feedback-form" id="fbForm">
        <div class="row">
          <select name="verdict">${VERDICTS.map((v) => `<option ${v === f.verdict ? "selected" : ""}>${v}</option>`).join("")}</select>
          <select name="portee">
            <option value="cas">Ce cas uniquement</option>
            <option value="motif">Tous les cas du même motif (${esc(f.signature)})</option>
          </select>
          <input name="auteur" placeholder="Votre nom" value="expert" style="width:140px">
        </div>
        <textarea name="commentaire" rows="2" placeholder="Justification de la correction (sera tracée dans le rapport)"></textarea>
        <div class="row"><button class="btn primary" type="submit">Enregistrer la correction</button>
        <span class="muted small">La correction est conservée et réappliquée aux prochaines exécutions. Elle sert aussi à réentraîner le modèle ML.</span></div>
      </form></section>`;
  $("#fbForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    loading(true);
    try {
      const out = await api("/api/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ finding_id: f.id, verdict: fd.get("verdict"), portee: fd.get("portee"),
          commentaire: fd.get("commentaire"), auteur: fd.get("auteur") || "expert" }),
      });
      toast(`Correction enregistrée : ${out.constats_impactes.length} constat(s) désormais décidés par un expert.`);
      await refresh();
      openFinding(f.id);
    } catch (err) { toast(`Erreur : ${err.message}`); } finally { loading(false); }
  });
  $("#drawer").classList.add("open");
  $("#overlay").classList.remove("hidden");
}

function closeDrawer() {
  $("#drawer").classList.remove("open");
  $("#overlay").classList.add("hidden");
}

// ------------------------------------------------------------------ actions
async function refresh() {
  renderSummary(await api("/api/summary"));
  renderChips();
  await loadFindings();
}

async function runCorroboration(formData) {
  loading(true);
  try {
    const useLlm = formData ? formData.get("use_llm") === "on" : true;
    const body = new FormData();
    if (formData) for (const k of ["source", "destination", "detail", "motif", "mapping"]) {
      const f = formData.get(k);
      if (f && f.size) body.append(k, f);
    }
    renderSummary(await api(`/api/run?use_llm=${useLlm}`, { method: "POST", body }));
    renderChips();
    await loadFindings();
    toast("Corroboration terminée.");
  } catch (err) { toast(`Erreur : ${err.message}`); } finally { loading(false); }
}

let searchTimer;
document.addEventListener("DOMContentLoaded", async () => {
  $("#toggleUpload").addEventListener("click", () => $("#uploadPanel").classList.toggle("hidden"));
  $("#uploadForm").addEventListener("submit", (e) => { e.preventDefault(); runCorroboration(new FormData(e.target)); });
  $("#rerun").addEventListener("click", () => runCorroboration(null));
  $("#fieldFilter").addEventListener("change", (e) => { state.champ = e.target.value; loadFindings(); });
  $("#levelFilter").addEventListener("change", (e) => { state.niveau = e.target.value; loadFindings(); });
  $("#reviewOnly").addEventListener("change", (e) => { state.review = e.target.checked; loadFindings(); });
  $("#search").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.q = e.target.value.trim(); loadFindings(); }, 200);
  });
  $("#closeDrawer").addEventListener("click", closeDrawer);
  $("#overlay").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
  loading(true);
  try { await refresh(); } catch (err) { toast(`Erreur : ${err.message}`); } finally { loading(false); }
});
