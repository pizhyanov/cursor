/**
 * Streaming LLM client. Answers are never persisted — caller streams to UI only.
 */

async function* answerQuestion({ question, knowledgeChunks, settings }) {
  const apiKey = settings.openaiApiKey;
  const baseUrl = (settings.openaiBaseUrl || 'https://api.openai.com/v1').replace(
    /\/$/,
    ''
  );
  const model = settings.openaiChatModel || 'gpt-4o-mini';
  const language = settings.language === 'en' ? 'English' : 'Russian';
  const stack = settings.stack || 'Creatio / BPMSoft';

  if (!apiKey) {
    yield {
      section: 'brief',
      text: 'Укажите API-ключ в настройках (OpenAI-compatible), чтобы получать ответы.',
    };
    return;
  }

  const knowledgeBlock =
    knowledgeChunks && knowledgeChunks.length
      ? knowledgeChunks
          .map(
            (c, i) =>
              `[${i + 1}] ${c.title || c.source || 'chunk'}\n${c.text}`
          )
          .join('\n\n')
      : '(локальных фрагментов не найдено — опирайся на общий стек, не выдумывай несуществующие Creatio API)';

  const system = `Ты помощник на техническом собеседовании разработчика Terrasoft Creatio / BPMSoft.
Стек кандидата: ${stack}.
Отвечай на ${language}.
Формат строго:
КРАТКО:
- 2-4 коротких тезиса, с которых можно сразу начать говорить вслух
ПОДРОБНО:
- развёрнутое объяснение, примеры, нюансы

Не упоминай, что ты ИИ-помощник на собеседовании.
Если в базе знаний мало данных по Creatio — честно опирайся на общий .NET/SQL/JS и отметь неопределённость по платформе.
Контекст из базы знаний:
${knowledgeBlock}`;

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      stream: true,
      temperature: 0.4,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: question },
      ],
    }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => '');
    throw new Error(`LLM HTTP ${response.status}: ${errText.slice(0, 300)}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let full = '';
  let emittedBrief = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) continue;
      const data = trimmed.slice(5).trim();
      if (data === '[DONE]') continue;
      let json;
      try {
        json = JSON.parse(data);
      } catch {
        continue;
      }
      const delta = json.choices?.[0]?.delta?.content || '';
      if (!delta) continue;
      full += delta;

      const parsed = splitSections(full);
      if (parsed.brief && !emittedBrief) {
        // stream brief as it stabilizes
      }
      yield {
        section: 'raw',
        text: delta,
        brief: parsed.brief,
        detailed: parsed.detailed,
      };
      if (parsed.brief) emittedBrief = true;
    }
  }

  const finalParsed = splitSections(full);
  yield {
    section: 'final',
    brief: finalParsed.brief || full.slice(0, 400),
    detailed: finalParsed.detailed || full,
  };
}

function splitSections(text) {
  const briefMatch = text.match(
    /КРАТКО\s*:\s*([\s\S]*?)(?=ПОДРОБНО\s*:|$)/i
  );
  const detailedMatch = text.match(/ПОДРОБНО\s*:\s*([\s\S]*)$/i);
  return {
    brief: briefMatch ? briefMatch[1].trim() : '',
    detailed: detailedMatch ? detailedMatch[1].trim() : '',
  };
}

module.exports = { answerQuestion, splitSections };
