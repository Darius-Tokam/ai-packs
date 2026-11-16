// Run the three Code nodes of workflow.json outside n8n, case by case.
// node harness.js workflow.json cases.json settings.json > results.json
const fs = require('fs');
const [wfPath, casesPath, settingsPath] = process.argv.slice(2);
const wf = JSON.parse(fs.readFileSync(wfPath, 'utf8'));
const codeOf = name => wf.nodes.find(n => n.name === name).parameters.jsCode;
const lire = new Function('$input', '$', codeOf("Lire l'entrée"));
const lignesRailway = new Function('$input', '$', codeOf('Lignes Railway'));
const nommer = new Function('$input', '$', codeOf('Nommer la cause'));
const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
const base = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
const one = json => ({ all: () => [{ json }], first: () => ({ json }) });
const out = [];
for (const c of cases) {
  const settings = { ...base, ...c.settings };
  // Réglages keeps the trigger output (includeOtherFields) and adds the settings.
  const reglages = { headers: {}, params: {}, query: {}, body: c.body, ...settings };
  const nodes = { 'Réglages': { json: reglages } };
  const $ = name => {
    if (!(name in nodes)) throw new Error('unknown node ' + name);
    return { first: () => nodes[name] };
  };
  const ev = lire(one(reglages), $)[0];
  nodes["Lire l'entrée"] = ev;
  const r = { case: c.case, entree: ev.json };
  if (ev.json.suivre) {
    const toName = ev.json.source === 'railway' ? lignesRailway(one(c.logs || {}), $)[0].json : ev.json;
    r.lignes = toName.lignes;
    r.cause = nommer(one(toName), $)[0].json;
  }
  out.push(r);
}
process.stdout.write(JSON.stringify(out, null, 1));
