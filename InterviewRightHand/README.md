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

## Сборка

```bash
npm run build:knowledge
npm run build:renderer
set CSC_IDENTITY_AUTO_DISCOVERY=false
npx electron-builder --win dir
```

Запуск собранного приложения: `dist-electron/win-unpacked/InterviewRightHand.exe`.

NSIS/portable могут требовать режим разработчика Windows (symlink при распаковке winCodeSign). Для раздачи на другой ПК достаточно zip-папки `win-unpacked` или включить Developer Mode и собрать `npm run build`.

## Настройки в приложении

1. API key + base URL + модель  
2. Стек и язык  
3. GitHub token + тумблер «Отправлять вопросы в репозиторий»

На чужом ПК достаточно установить exe и ввести свои ключи — Cursor и ваши Desktop-пути не нужны.

## Проверка скрытия от шаринга

Перед интервью сделайте тестовый звонок (Zoom / Meet / Teams) и убедитесь, что окно ассистента не попадает в демонстрацию экрана.
