import { useEffect, useMemo, useState } from 'react';
import type { AnswerDelta, IrhSettings, TranscriptPayload } from './vite-env';
import { DualCapture } from './audio/capture';

const defaultSettings: IrhSettings = {
  openaiApiKey: '',
  openaiBaseUrl: 'https://api.openai.com/v1',
  openaiChatModel: 'gpt-4o-mini',
  openaiTranscribeModel: 'gpt-4o-mini-transcribe',
  githubToken: '',
  githubRepo: 'pizhyanov/cursor',
  githubQuestionBankPath: 'InterviewRightHand/question-bank/inbox',
  sendQuestionsToRepo: true,
  stack:
    'Creatio / BPMSoft, C#, .NET, JS, Angular, SQL, IIS, RabbitMQ, cache, Git',
  language: 'ru',
  opacity: 0.92,
  installId: '',
};

export function App() {
  const [settings, setSettings] = useState<IrhSettings>(defaultSettings);
  const [showSettings, setShowSettings] = useState(false);
  const [listening, setListening] = useState(false);
  const [interviewerPartial, setInterviewerPartial] = useState('');
  const [youPartial, setYouPartial] = useState('');
  const [question, setQuestion] = useState('');
  const [brief, setBrief] = useState('');
  const [detailed, setDetailed] = useState('');
  const [status, setStatus] = useState('Готов');
  const [error, setError] = useState('');
  const [manual, setManual] = useState('');
  const [draft, setDraft] = useState<IrhSettings>(defaultSettings);

  const capture = useMemo(
    () =>
      new DualCapture({
        onTranscript: (payload) => {
          window.irh.sendPcmChunk({ type: 'transcript', ...payload });
          if (payload.role === 'interviewer') {
            setInterviewerPartial(payload.text);
          } else {
            setYouPartial(payload.text);
          }
        },
        onError: (message) => setError(message),
      }),
    []
  );

  useEffect(() => {
    void window.irh.getSettings().then((s) => {
      setSettings(s);
      setDraft(s);
      capture.setLang(s.language);
      if (!s.openaiApiKey) setShowSettings(true);
    });
    void window.irh.getListening().then(setListening);

    const offs = [
      window.irh.on('listening:changed', (v) => setListening(Boolean(v))),
      window.irh.on('transcript:partial', (data) => {
        const p = data as TranscriptPayload;
        if (p.role === 'interviewer') setInterviewerPartial(p.text);
        else setYouPartial(p.text);
      }),
      window.irh.on('transcript:final', (data) => {
        const p = data as TranscriptPayload;
        if (p.role === 'interviewer') {
          setInterviewerPartial(p.text);
          setQuestion(p.text);
        } else setYouPartial(p.text);
      }),
      window.irh.on('answer:start', (data) => {
        const q = (data as { question?: string }).question || '';
        setQuestion(q);
        setBrief('');
        setDetailed('');
        setStatus('Думаю…');
        setError('');
      }),
      window.irh.on('answer:delta', (data) => {
        const d = data as AnswerDelta;
        if (d.brief) setBrief(d.brief);
        if (d.detailed) setDetailed(d.detailed);
      }),
      window.irh.on('answer:done', () => setStatus('Готово')),
      window.irh.on('answer:error', (data) => {
        setError((data as { message?: string }).message || 'Ошибка ответа');
        setStatus('Ошибка');
      }),
    ];

    return () => {
      offs.forEach((off) => off());
      void capture.stop();
    };
  }, [capture]);

  async function toggleListen() {
    setError('');
    const next = !listening;
    capture.setLang(settings.language);
    if (next) await capture.start();
    else await capture.stop();
    const value = await window.irh.setListening(next);
    setListening(value);
    setStatus(value ? 'Слушаю' : 'Пауза');
  }

  async function saveSettings() {
    const saved = await window.irh.setSettings(draft);
    setSettings(saved);
    capture.setLang(saved.language);
    setShowSettings(false);
    setStatus('Настройки сохранены');
  }

  async function askManual() {
    const text = manual.trim();
    if (!text) return;
    setManual('');
    setQuestion(text);
    await window.irh.askManual(text);
  }

  return (
    <div className="app">
      <div className="titlebar">
        <div className="brand">InterviewRightHand</div>
        <div className="spacer" />
        <button type="button" onClick={() => setShowSettings((v) => !v)}>
          Настройки
        </button>
        <button type="button" onClick={() => void window.irh.minimize()}>
          —
        </button>
        <button type="button" className="danger" onClick={() => void window.irh.close()}>
          ✕
        </button>
      </div>

      <div className="toolbar">
        <button type="button" className="primary" onClick={() => void toggleListen()}>
          {listening ? 'Стоп' : 'Слушать'}
        </button>
        <span className="pill">
          <span className={`dot ${listening ? 'on' : ''}`} />
          {status}
        </span>
        <span className="pill">Ctrl+Shift+Space — слушать</span>
        <span className="pill">Ctrl+Shift+H — скрыть</span>
      </div>

      <div className="content">
        <div className="block question">
          <h3>Запрос</h3>
          <div className="body">
            {question || interviewerPartial || 'Ожидание вопроса интервьюера…'}
          </div>
          {youPartial ? (
            <div className="meta">Вы (микрофон): {youPartial}</div>
          ) : null}
        </div>

        <div className="block brief">
          <h3>Кратко</h3>
          <div className="body">{brief || '—'}</div>
        </div>

        <div className="block detailed">
          <h3>Подробно</h3>
          <div className="body">{detailed || '—'}</div>
        </div>

        {error ? <div className="error">{error}</div> : null}
        <div className="hint">
          Ответы не сохраняются. Вопросы (без ответов) могут уходить в question-bank
          репозитория, если включено в настройках.
        </div>
      </div>

      <div className="manual">
        <label>
          Ручной вопрос (если STT недоступен)
          <input
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void askManual();
            }}
            placeholder="Вставьте вопрос и Enter"
          />
        </label>
        <button type="button" onClick={() => void askManual()}>
          Спросить
        </button>
      </div>

      {showSettings ? (
        <div className="settings">
          <div className="row">
            <label>
              OpenAI API key
              <input
                type="password"
                value={draft.openaiApiKey}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, openaiApiKey: e.target.value }))
                }
              />
            </label>
            <label>
              Base URL
              <input
                value={draft.openaiBaseUrl}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, openaiBaseUrl: e.target.value }))
                }
              />
            </label>
          </div>
          <div className="row">
            <label>
              Chat model
              <input
                value={draft.openaiChatModel}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, openaiChatModel: e.target.value }))
                }
              />
            </label>
            <label>
              Язык
              <select
                value={draft.language}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, language: e.target.value }))
                }
              >
                <option value="ru">Русский</option>
                <option value="en">English</option>
              </select>
            </label>
          </div>
          <label>
            Стек / контекст
            <textarea
              rows={2}
              value={draft.stack}
              onChange={(e) => setDraft((d) => ({ ...d, stack: e.target.value }))}
            />
          </label>
          <div className="row">
            <label>
              GitHub token (question-bank)
              <input
                type="password"
                value={draft.githubToken}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, githubToken: e.target.value }))
                }
              />
            </label>
            <label>
              Repo
              <input
                value={draft.githubRepo}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, githubRepo: e.target.value }))
                }
              />
            </label>
          </div>
          <label>
            <span>
              <input
                type="checkbox"
                checked={draft.sendQuestionsToRepo}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    sendQuestionsToRepo: e.target.checked,
                  }))
                }
              />{' '}
              Отправлять вопросы в репозиторий (ответы никогда не отправляются)
            </span>
          </label>
          <div className="row">
            <button type="button" className="primary" onClick={() => void saveSettings()}>
              Сохранить
            </button>
            <button type="button" onClick={() => setShowSettings(false)}>
              Закрыть
            </button>
          </div>
          <div className="hint">
            Install ID: {settings.installId || '—'} · ключи хранятся локально на этом ПК
          </div>
        </div>
      ) : null}
    </div>
  );
}
