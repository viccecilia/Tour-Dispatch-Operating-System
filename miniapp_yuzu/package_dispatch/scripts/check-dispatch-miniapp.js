const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const errors = [];

function walk(dir, matcher, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const stat = fs.statSync(full);
    if (stat.isDirectory()) walk(full, matcher, out);
    else if (matcher(full)) out.push(full);
  }
  return out;
}

function rel(file) {
  return path.relative(root, file).replace(/\\/g, '/');
}

function fail(file, message) {
  errors.push(`${rel(file)}: ${message}`);
}

function checkJs(file) {
  const result = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' });
  if (result.status !== 0) fail(file, (result.stderr || result.stdout || 'node --check failed').trim());
}

function checkWxml(file) {
  const source = fs.readFileSync(file, 'utf8');
  const brokenClose = source.match(/[^<]\/(view|text|strong|button|scroll-view|picker)>/g);
  if (brokenClose) fail(file, `suspect broken closing tag: ${brokenClose.slice(0, 5).join(', ')}`);

  const stack = [];
  const voidTags = new Set(['input', 'image', 'import', 'include', 'icon', 'progress']);
  const tagRe = /<\/?([A-Za-z][\w-]*)(?=[\s>/])[^>]*(\/?)>/g;
  let match;
  while ((match = tagRe.exec(source))) {
    const raw = match[0];
    const tag = match[1];
    const selfClosing = raw.endsWith('/>') || match[2] === '/' || voidTags.has(tag);
    if (raw.startsWith('</')) {
      const last = stack.pop();
      if (last !== tag) {
        fail(file, `tag mismatch near offset ${match.index}: expected </${last || 'none'}>, found </${tag}>`);
        return;
      }
    } else if (!selfClosing) {
      stack.push(tag);
    }
  }
  if (stack.length) fail(file, `unclosed tags: ${stack.slice(-8).join(' > ')}`);
}

function main() {
  const jsFiles = walk(root, (file) => file.endsWith('.js'));
  const wxmlFiles = walk(root, (file) => file.endsWith('.wxml'));

  jsFiles.forEach(checkJs);
  wxmlFiles.forEach(checkWxml);

  if (errors.length) {
    console.error('[dispatch-miniapp-check] failed');
    errors.forEach((err) => console.error(`- ${err}`));
    process.exit(1);
  }
  console.log(`[dispatch-miniapp-check] ok: ${jsFiles.length} js, ${wxmlFiles.length} wxml`);
}

main();
