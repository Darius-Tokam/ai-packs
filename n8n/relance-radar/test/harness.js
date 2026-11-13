// Run the "Choisir les relances" Code node of workflow.json outside n8n.
// node harness.js workflow.json threads.json settings.json > decisions.json
const fs = require('fs');
const [wfPath, itemsPath, settingsPath] = process.argv.slice(2);
const wf = JSON.parse(fs.readFileSync(wfPath, 'utf8'));
const code = wf.nodes.find(n => n.name === 'Choisir les relances').parameters.jsCode;
const items = JSON.parse(fs.readFileSync(itemsPath, 'utf8'));
const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
const $input = { all: () => items };
const $ = name => {
  if (name !== 'Réglages') throw new Error('unknown node ' + name);
  return { first: () => ({ json: settings }) };
};
const run = new Function('$input', '$', code);
process.stdout.write(JSON.stringify(run($input, $).map(i => i.json), null, 1));
