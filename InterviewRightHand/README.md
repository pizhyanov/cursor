# InterviewRightHand

Windows-оверлей для помощи на техническом собеседовании (Creatio / BPMSoft и общий стек: C#, .NET, JS, Angular, SQL, IIS, RabbitMQ, cache, Git).

По духу близок к [interview-assistant.ru](https://interview-assistant.ru): слушает системный звук и микрофон, показывает вопрос и ответ **Кратко → Подробно**, окно скрыто от захвата экрана (`setContentProtection`).

## Важно про данные

- **Ответы не сохраняются** и **не отправляются** никуда.
- **Вопросы** (без ответов) могут отправляться в `question-bank/inbox/` этого репозитория, чтобы видеть, что спрашивают у разных людей.
- Стартовые знания — встроенный `knowledge/pack` (сборка из `Creatio_Interview` и опционально локальной папки CREATIO при билде).

## Требования

- Windows 10 2004+ / Windows 11
- Node.js 20+
- OpenAI-compatible API key (для ответов)
- Опционально: GitHub fine-grained token с `contents:write` только на `InterviewRightHand/question-bank/**`

## Разработка

```bash
cd InterviewRightHand
npm install
copy knowledge\sources.example.json knowledge\sources.local.json
python scripts/build-knowledge-pack.py
npm run dev
```

Горячие клавиши:

- `Ctrl+Shift+Space` — старт/стоп слушания
- `Ctrl+Shift+H` — скрыть/показать окно
- `Ctrl+Shift+Up/Down` — прозрачность

## Сборка установщика

```bash
npm run build:knowledge
npm run build
```

Артефакты: `dist-electron/` (NSIS Setup + portable).

## Настройки в приложении

1. API key + base URL + модель  
2. Стек и язык  
3. GitHub token + тумблер «Отправлять вопросы в репозиторий»

На чужом ПК достаточно установить exe и ввести свои ключи — Cursor и ваши Desktop-пути не нужны.

## Проверка скрытия от шаринга

Перед интервью сделайте тестовый звонок (Zoom / Meet / Teams) и убедитесь, что окно ассистента не попадает в демонстрацию экрана.
