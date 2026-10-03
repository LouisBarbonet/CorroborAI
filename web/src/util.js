export const $ = (s, el = document) => el.querySelector(s);

export const esc = (v) => (v === null || v === undefined || v === "" ? "∅" : String(v))
  .replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
