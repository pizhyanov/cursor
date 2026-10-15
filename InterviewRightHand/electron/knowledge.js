const fs = require('fs');
const path = require('path');
const { app } = require('electron');

let cache = null;

function packDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'knowledge', 'pack');
  }
  return path.join(__dirname, '..', 'knowledge', 'pack');
}

function loadPack() {
  if (cache) return cache;
  const dir = packDir();
  const indexPath = path.join(dir, 'index.json');
  if (!fs.existsSync(indexPath)) {
    cache = { chunks: [] };
    return cache;
  }
  try {
    cache = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
  } catch {
    cache = { chunks: [] };
  }
  return cache;
}

function tokenize(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s.+#]/gu, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 2);
}

function retrieveKnowledge(question, limit = 6) {
  const pack = loadPack();
  const qTokens = new Set(tokenize(question));
  if (!qTokens.size || !pack.chunks?.length) return [];

  const scored = pack.chunks.map((chunk) => {
    const tokens = tokenize(`${chunk.title || ''} ${chunk.text || ''}`);
    let score = 0;
    for (const t of tokens) {
      if (qTokens.has(t)) score += 1;
    }
    // boost completeness
    if (chunk.completeness === 'full') score *= 1.25;
    if (chunk.completeness === 'partial') score *= 0.9;
    return { chunk, score };
  });

  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((s) => s.chunk);
}

function reloadKnowledge() {
  cache = null;
  return loadPack();
}

module.exports = { retrieveKnowledge, reloadKnowledge, loadPack };
