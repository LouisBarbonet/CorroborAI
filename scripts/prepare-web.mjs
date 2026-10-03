// Prépare les fichiers servis à côté du site statique (web/public/, ignoré par git) :
// - py/bundle.json : sources du paquet Python « corroborai » + prompts/prompts.json, chargés dans Pyodide ;
// - data/ : extractions du défi (lecture seule) + manifest.json pour le contrôle d'intégrité dans le navigateur.
import { cpSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const pub = join(root, "web", "public");
const files = {};
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { if (name !== "__pycache__") walk(p); }
    else if (name.endsWith(".py")) files[relative(root, p).replaceAll("\\", "/")] = readFileSync(p, "utf8");
  }
};
walk(join(root, "corroborai"));
files["prompts/prompts.json"] = readFileSync(join(root, "prompts", "prompts.json"), "utf8");
mkdirSync(join(pub, "py"), { recursive: true });
writeFileSync(join(pub, "py", "bundle.json"), JSON.stringify({ files }));

const DATA_FILES = ["Employe_Source_Anonymise_VF.xlsx", "Employe_Destination_Anonymise_VF.xlsx", "détail_du_poste.xlsx",
  "Motif de la situation d'emploi.xlsx", "Mapping.xlsx", "manifest.json"];
const src = join(root, "corroborai-participants");
mkdirSync(join(pub, "data"), { recursive: true });
for (const f of DATA_FILES) cpSync(join(src, f), join(pub, "data", f));
writeFileSync(join(pub, "data", "index.json"), JSON.stringify(DATA_FILES));
console.log(`prepare-web : ${Object.keys(files).length} fichiers Python, ${DATA_FILES.length} fichiers de données → web/public/`);
