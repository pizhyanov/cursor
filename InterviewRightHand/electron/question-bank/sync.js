/**
 * Question-bank sync: ONLY questions go to the GitHub repo.
 * Answers must never be written here or uploaded.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { app } = require('electron');

function queuePath() {
  return path.join(app.getPath('userData'), 'question-queue.jsonl');
}

function normalizeQuestion(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[«»"'.,!?:;()\[\]{}]/g, '')
    .trim();
}

function hashQuestion(text) {
  return crypto.createHash('sha256').update(normalizeQuestion(text)).digest('hex').slice(0, 16);
}

function readQueue() {
  const file = queuePath();
  if (!fs.existsSync(file)) return [];
  return fs
    .readFileSync(file, 'utf8')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

function writeQueue(items) {
  const file = queuePath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(
    file,
    items.map((i) => JSON.stringify(i)).join('\n') + (items.length ? '\n' : ''),
    'utf8'
  );
}

async function enqueueQuestion(payload, settings) {
  if (!settings?.sendQuestionsToRepo) return;
  const text = String(payload.text || '').trim();
  if (text.length < 12) return;

  // Hard guard: never accept answer-like fields
  const item = {
    text,
    normalized: normalizeQuestion(text),
    hash: hashQuestion(text),
    ts: new Date().toISOString(),
    tags: guessTags(text),
    stack: String(payload.stack || '').slice(0, 200),
    installId: String(payload.installId || 'unknown'),
    appVersion: String(payload.appVersion || '0'),
  };

  const queue = readQueue();
  const recent = queue.filter(
    (q) => q.hash === item.hash && Date.now() - Date.parse(q.ts || 0) < 6 * 3600 * 1000
  );
  if (recent.length) return;
  queue.push(item);
  writeQueue(queue);
}

function guessTags(text) {
  const t = text.toLowerCase();
  const tags = [];
  const map = [
    ['c#', 'csharp'],
    ['csharp', 'csharp'],
    ['.net', 'dotnet'],
    ['sql', 'sql'],
    ['postgres', 'sql'],
    ['oracle', 'sql'],
    ['javascript', 'js'],
    ['js ', 'js'],
    ['angular', 'angular'],
    ['creatio', 'creatio'],
    ['bpmsoft', 'creatio'],
    ['rabbit', 'rabbit'],
    ['redis', 'cache'],
    ['iis', 'iis'],
    ['git', 'git'],
  ];
  for (const [needle, tag] of map) {
    if (t.includes(needle) && !tags.includes(tag)) tags.push(tag);
  }
  return tags;
}

async function flushQuestionQueue(settings) {
  if (!settings?.sendQuestionsToRepo) return { flushed: 0 };
  const token = settings.githubToken;
  if (!token) return { flushed: 0, reason: 'no-token' };

  const repo = settings.githubRepo || 'pizhyanov/cursor';
  const basePath =
    settings.githubQuestionBankPath ||
    'InterviewRightHand/question-bank/inbox';
  const queue = readQueue();
  if (!queue.length) return { flushed: 0 };

  const remaining = [];
  let flushed = 0;

  for (const item of queue) {
    try {
      // Never upload fields beyond the allowlist
      const safe = {
        text: item.text,
        normalized: item.normalized,
        hash: item.hash,
        ts: item.ts,
        tags: item.tags || [],
        stack: item.stack || '',
        installId: item.installId,
        appVersion: item.appVersion,
      };
      await appendJsonlLine({
        token,
        repo,
        filePath: `${basePath}/${(item.ts || '').slice(0, 10) || 'unknown'}.jsonl`,
        line: JSON.stringify(safe),
      });
      flushed += 1;
    } catch (err) {
      remaining.push(item);
      console.error('question-bank flush failed', err?.message || err);
      break;
    }
  }

  writeQueue(remaining);
  return { flushed, remaining: remaining.length };
}

async function appendJsonlLine({ token, repo, filePath, line }) {
  const [owner, name] = repo.split('/');
  const api = `https://api.github.com/repos/${owner}/${name}/contents/${encodeURI(filePath)
    .replace(/%2F/g, '/')}`;

  let sha = null;
  let content = '';
  const getRes = await fetch(api, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'InterviewRightHand',
    },
  });

  if (getRes.status === 200) {
    const body = await getRes.json();
    sha = body.sha;
    content = Buffer.from(body.content, 'base64').toString('utf8');
    if (content && !content.endsWith('\n')) content += '\n';
  } else if (getRes.status !== 404) {
    const t = await getRes.text();
    throw new Error(`GitHub GET ${getRes.status}: ${t.slice(0, 200)}`);
  }

  // Skip if identical hash already in file
  if (content.includes(`"hash":"${JSON.parse(line).hash}"`)) {
    return;
  }

  const next = content + line + '\n';
  const putRes = await fetch(api, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
      'User-Agent': 'InterviewRightHand',
    },
    body: JSON.stringify({
      message: `question-bank: append question ${JSON.parse(line).hash}`,
      content: Buffer.from(next, 'utf8').toString('base64'),
      sha: sha || undefined,
    }),
  });

  if (!putRes.ok) {
    const t = await putRes.text();
    throw new Error(`GitHub PUT ${putRes.status}: ${t.slice(0, 200)}`);
  }
}

module.exports = {
  enqueueQuestion,
  flushQuestionQueue,
  normalizeQuestion,
  hashQuestion,
};
