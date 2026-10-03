import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import data from "../worker/src/data.generated.json";
import { extractCitations, normalizeQuestion } from "../shared/normalize.js";

const questions = JSON.parse(readFileSync(new URL("../data/chat-questions.json", import.meta.url), "utf8"));
const pre = JSON.parse(readFileSync(new URL("../data/precomputed/chat.json", import.meta.url), "utf8"));
const reperes = new Set(data.reperes);

describe("réponses pré-enregistrées", () => {
  it("chaque question d'exemple a une réponse", () => {
    const answered = new Set(pre.reponses.map((r) => normalizeQuestion(r.question)));
    for (const q of questions) expect(answered.has(normalizeQuestion(q)), q).toBe(true);
  });

  it("chaque citation pointe vers un repère réel (règle ou constat)", () => {
    const invalid = [];
    for (const r of pre.reponses) {
      for (const c of extractCitations(r.reponse)) if (!reperes.has(c)) invalid.push(`${r.question} → ${c}`);
    }
    expect(invalid).toEqual([]);
  });

  it("les matricules cités existent dans les résultats", () => {
    const mats = new Set(data.reperes.filter((r) => r.includes("/")).map((r) => r.slice(1).split("/")[0]));
    for (const r of pre.reponses) {
      for (const m of r.reponse.match(/\b\d{7}\b/g) ?? []) expect(mats.has(m), `${r.question} → ${m}`).toBe(true);
    }
  });
});
