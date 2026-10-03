// Chat du jury : réponses pré-enregistrées instantanées pour les questions d'exemple, sinon relais LLM
// (serveur Python local ou relais Cloudflare). Les repères [R-XXX] et [matricule/champ] sont cliquables.
import { normalizeQuestion } from "../../shared/normalize.js";
import { esc } from "./util.js";

const MAX_Q = 800;

export function formatAnswer(text) {
  const lines = esc(text).split(/\n/);
  let html = "";
  let inList = false;
  for (const raw of lines) {
    const m = raw.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (m) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${m[1]}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (raw.trim()) html += `<p>${raw}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\[\]]{1,80})\]/g, (_, ref) => `<button type="button" class="cite" data-ref="${ref}">${ref}</button>`);
}

export function initChat({ backend, precomputed, questions, onCite }) {
  const $ = (s) => document.querySelector(s);
  const panel = $("#chatPanel");
  const list = $("#chatMessages");
  const input = $("#chatInput");
  const counter = $("#chatCounter");
  const history = [];
  const pre = new Map(precomputed.reponses.map((r) => [normalizeQuestion(r.question), r]));

  const toggle = (open) => {
    panel.classList.toggle("open", open ?? !panel.classList.contains("open"));
    panel.setAttribute("aria-hidden", String(!panel.classList.contains("open")));
    if (panel.classList.contains("open")) input.focus();
  };
  $("#chatToggle").addEventListener("click", () => toggle());
  $("#chatClose").addEventListener("click", () => toggle(false));

  $("#chatSuggestions").innerHTML = questions.map((q) => `<button type="button" class="chip small">${esc(q)}</button>`).join("");
  $("#chatSuggestions").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) ask(b.textContent);
  });

  list.addEventListener("click", (e) => {
    const b = e.target.closest(".cite");
    if (b) onCite(b.dataset.ref);
  });

  const add = (role, html, note = "", cls = "") => {
    const div = document.createElement("div");
    div.className = `msg ${role} ${cls}`;
    div.innerHTML = `<div class="bubble">${html}</div>${note ? `<div class="note">${esc(note)}</div>` : ""}`;
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
    return div;
  };

  async function ask(question) {
    const q = question.trim().slice(0, MAX_Q);
    if (!q) return;
    toggle(true);
    add("user", esc(q));
    history.push({ role: "user", content: q });
    input.value = "";
    counter.textContent = `0 / ${MAX_Q}`;

    const hit = pre.get(normalizeQuestion(q));
    if (hit) {
      add("assistant", formatAnswer(hit.reponse), `Réponse pré-enregistrée (instantanée, générée par ${hit.fournisseur})`);
      history.push({ role: "assistant", content: hit.reponse.slice(0, 2000) });
      return;
    }
    const pending = add("assistant", '<span class="typing">Réflexion en cours…</span>');
    try {
      const r = await backend.chat(history.slice(-8));
      pending.remove();
      add("assistant", formatAnswer(r.reponse), `${r.cached ? "Réponse en cache · " : ""}${r.fournisseur}`);
      history.push({ role: "assistant", content: r.reponse.slice(0, 2000) });
    } catch (err) {
      pending.remove();
      history.pop();
      add("assistant", `<p>${esc(err.message)}</p><p>Les questions d'exemple ci-dessous restent disponibles (réponses pré-enregistrées).</p>`, "", "error");
    }
  }

  input.addEventListener("input", () => { counter.textContent = `${input.value.length} / ${MAX_Q}`; });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input.value); }
  });
  $("#chatForm").addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
  return { ask, toggle };
}
