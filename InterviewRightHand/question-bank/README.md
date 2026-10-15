# Question bank

Сюда клиенты InterviewRightHand отправляют **только вопросы** с интервью.

## Правила

- Можно: текст вопроса, теги, анонимный `installId`, версия приложения, стек из настроек.
- Нельзя: ответы ассистента, речь кандидата с микрофона, ФИО, API-ключи, записи звонков.

## Формат

Файлы `inbox/YYYY-MM-DD.jsonl` — одна JSON-строка на вопрос:

```json
{
  "text": "Что такое EntitySchemaQuery?",
  "normalized": "что такое entityschemaquery",
  "hash": "a1b2c3d4e5f60718",
  "ts": "2026-10-15T12:00:00.000Z",
  "tags": ["creatio"],
  "stack": "Creatio / BPMSoft, C#",
  "installId": "uuid",
  "appVersion": "0.1.0"
}
```

Агрегацию частых вопросов для улучшения knowledge pack делайте скриптом `scripts/aggregate-questions.py` (опционально).
