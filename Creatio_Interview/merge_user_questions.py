#!/usr/bin/env python3
"""Merge uploaded interview Excels into Creatio_Interview workbook."""

from __future__ import annotations

import glob
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
OUTPUTS = [
    ROOT / "Creatio_Interview_QA_Pyzhyanov.xlsx",
    ROOT / "Собеседование_Creatio_Ответы_Владислав_Пыжьянов.xlsx",
]

HEADER = ["Тема", "Вопрос", "Ответ простыми словами", "Источник", "Статус"]


def norm(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def simplify_existing(answer: str) -> str:
    """Keep user's answer, add a short lead-in if missing."""
    a = (answer or "").strip()
    if not a:
        return a
    if a.startswith("Простыми словами") or "Что сказать:" in a:
        return a
    # Keep original content — it is the user's own notes — but make readable
    return a


# Keyword -> beginner answer for questions without answers in source files
ANSWER_BANK: list[tuple[str, str]] = [
    (
        "стратегия",
        "Паттерн Strategy: выносим алгоритм в отдельные классы с общим интерфейсом и подменяем их.\n"
        "Пример: разные способы расчёта скидки. В Creatio — разные обработчики/сервисы вместо гигантского if.\n"
        "Что сказать: «Взаимозаменяемые алгоритмы за общим интерфейсом».",
    ),
    (
        "singleton",
        "Singleton — в системе один экземпляр класса.\n"
        "В многопотоке нужна потокобезопасная инициализация (Lazy<T>, lock).\n"
        "В веб/Creatio осторожно: static на сервере общий для всех запросов.\n"
        "Что сказать: «Один экземпляр + потокобезопасность; в web static — риск».",
    ),
    (
        "abstract factory",
        "Abstract Factory — фабрика фабрик: семейства связанных объектов без указания конкретных классов.\n"
        "Что сказать: «Создаём набор связанных продуктов через абстрактную фабрику».",
    ),
    (
        "factory method",
        "Factory Method — метод создания объекта вынесен в наследников.\n"
        "В Creatio похожий дух у ClassFactory / создания Entity по имени схемы.\n"
        "Что сказать: «Создание объекта делегируем методу/фабрике, а не new по всему коду».",
    ),
    (
        "builder",
        "Builder — пошаговая сборка сложного объекта (цепочка SetX().SetY().Build()).\n"
        "Что сказать: «Строим сложный объект по шагам, чтобы конструктор не раздувался».",
    ),
    (
        "ссылочным и значимым",
        "Значимые: int, bool, DateTime, struct, enum.\n"
        "Ссылочные: class, string, массивы, делегаты.\n"
        "Что сказать: value копируется, reference передаёт ссылку на объект в куче.",
    ),
    (
        "что такое класс",
        "Класс — чертёж объекта: поля + поведение. Экземпляр — конкретный объект по этому чертежу.\n"
        "Что сказать: «Шаблон для объектов с данными и методами».",
    ),
    (
        "обязаны использовать модификатор abstract",
        "Когда в базовом классе есть члены без реализации — класс обязан быть abstract, "
        "иначе компилятор не даст «недоделанный» обычный класс.\n"
        "Что сказать: «Есть abstract-члены → класс abstract».",
    ),
    (
        "модификатор virtual",
        "virtual — метод можно переопределить в наследнике через override (полиморфизм).\n"
        "Что сказать: «Разрешает полиморфное переопределение».",
    ),
    (
        "разница между абстрактными и виртуальными",
        "abstract — обязательно переопределить, реализации в базе нет.\n"
        "virtual — реализация есть, переопределение по желанию.\n"
        "Что сказать именно так.",
    ),
    (
        "модификатор protected",
        "protected — видно в классе и наследниках, снаружи «как private».\n"
        "Что сказать: «Для иерархии наследования».",
    ),
    (
        "модификатор internal",
        "internal — видно внутри этой же сборки (assembly).\n"
        "Что сказать: «Доступ на уровне проекта/сборки».",
    ),
    (
        "модификатор private",
        "private — только внутри этого класса.\n"
        "Что сказать: «Максимальная инкапсуляция».",
    ),
    (
        "наследуются ли члены класса с модификатором private",
        "Формально поля есть в объекте наследника, но доступа к ним из кода наследника нет. "
        "Наследник их «не видит».\n"
        "Что сказать: «Недоступны наследнику, хотя физически в объекте присутствуют».",
    ),
    (
        "модификатор new",
        "new на методе — скрывает одноимённый метод базы (не полиморфизм). Лучше virtual/override.\n"
        "Что сказать: «Скрытие имени, не override».",
    ),
    (
        "extension",
        "Метод расширения: static-класс + this Type у первого параметра: "
        "public static int WordCount(this string s).\n"
        "Вызов как у обычного метода: \"hi\".WordCount().\n"
        "Что сказать: «Синтаксический сахар для static-метода с this».",
    ),
    (
        "delegate и multicast",
        "Delegate — ссылка на метод. Multicast — несколько методов в одной цепочке (+=).\n"
        "Что сказать: «Тип для колбэка; multicast вызывает всех подписчиков».",
    ),
    (
        "delegate принимать значение null",
        "Да, делегат может быть null. Перед вызовом проверяйте или используйте ?.Invoke().\n"
        "Что сказать: «Может быть null — проверяем перед вызовом».",
    ),
    (
        "анонимного метода, lambda",
        "Анонимный метод / lambda — функция без имени: x => x * 2, удобно для LINQ и событий.\n"
        "Что сказать: «Короткий безымянный обработчик/функция».",
    ),
    (
        "перекрытый метод отличается от перегруженного",
        "Перегрузка (overload) — одно имя, разные параметры.\n"
        "Переопределение (override) — новая реализация virtual/abstract в наследнике.\n"
        "Перекрытие (new) — скрытие метода базы.\n"
        "Что сказать: overload ≠ override ≠ new.",
    ),
    (
        "множественное наследование классов",
        "Классов — нет (только один родитель). Интерфейсов — да, сколько угодно.\n"
        "Что сказать именно так.",
    ),
    (
        "запретить перекрытие метода",
        "sealed override — наследник не сможет дальше override.\n"
        "Класс можно оставить не-sealed.\n"
        "Что сказать: «sealed на override-методе».",
    ),
    (
        "readonly полями и контстантами",
        "const — значение на этапе компиляции, только примитивы/строка.\n"
        "readonly — можно задать в конструкторе, потом не менять.\n"
        "Что сказать: const compile-time, readonly runtime в конструкторе.",
    ),
    (
        "куча и стек",
        "Стек — быстрая память кадров методов (локальные value, ссылки).\n"
        "Куча — объекты reference-типов, чистит GC.\n"
        "Что сказать: стек = кадры вызовов, куча = объекты под GC.",
    ),
    (
        "проблему решали обобщенные коллекции",
        "До generics был ArrayList на object → касты, boxing, ошибки типов в runtime.\n"
        "List<T> даёт типобезопасность и скорость.\n"
        "Что сказать: «Убрали касты/boxing, сделали безопаснее и быстрее».",
    ),
    (
        "исключительная ситуация",
        "Exception — сигнал ошибки, который можно поймать и обработать, а не молча получить неверные данные.\n"
        "Что сказать: «Объект ошибки с типами и стеком вызовов».",
    ),
    (
        "процесс перехвата исключительных",
        "try { опасное } catch (SpecificEx) { обработка } finally { уборка }.\n"
        "Ловите конкретное, логируйте, не глотайте Exception без нужды.\n"
        "Что сказать: try/catch/finally + конкретные типы.",
    ),
    (
        "несколько блоков catch для одного",
        "Да, несколько catch подряд от частного к общему. Сработает один подходящий.\n"
        "Что сказать: «Несколько catch, один сработает».",
    ),
    (
        "выполнен блок finally, если не было",
        "Да, finally почти всегда выполняется (и при успехе, и при ошибке), кроме жёсткого убийства процесса.\n"
        "Что сказать: «finally выполняется в любом случае».",
    ),
    (
        "return 3",
        "Если в finally есть return — он перебивает return из try/catch (плохой стиль, так не пишите).\n"
        "Что сказать: «return в finally перекрывает предыдущий; на практике return в finally не используют».",
    ),
    (
        "перегрузки методов",
        "Одно имя метода, разные наборы параметров. Компилятор выбирает подходящую перегрузку.\n"
        "Что сказать: «Одно имя — разные сигнатуры».",
    ),
    (
        "сборка мусора в .net",
        "GC ищет объекты без ссылок и освобождает память. Поколения 0/1/2, есть LOH для больших объектов.\n"
        "Что сказать: «Автоматическая очистка недостижимых объектов поколений».",
    ),
    (
        "вызвать сборщик мусора из кода",
        "GC.Collect() вручную почти никогда не нужно — только в редких диагностических случаях.\n"
        "Что сказать: «Обычно не вызываю; доверяю runtime».",
    ),
    (
        "статический конструктор класса",
        "Перед первым обращением к типу (создание или static-член), ровно один раз, потокобезопасно.\n"
        "Что сказать: «Один раз до первого использования типа».",
    ),
    (
        "опишите fcl",
        "FCL — библиотека классов .NET (коллекции, IO, сеть, и т.д.), то на чём пишем каждый день.\n"
        "Что сказать: «Стандартная библиотека классов Framework/BCL».",
    ),
    (
        "опишите cls",
        "CLS — правила, чтобы разные .NET-языки могли дружить в одной экосистеме.\n"
        "Что сказать: «Общий набор правил совместимости языков».",
    ),
    (
        "опишите cil",
        "CIL/IL — промежуточный код, в который компилируется C#. Потом JIT делает машинный код.\n"
        "Что сказать: «Промежуточный язык .NET до JIT».",
    ),
    (
        "что такое сборка (assembly)",
        "Assembly — dll/exe с кодом и метаданными, единица развёртывания .NET.\n"
        "Что сказать: «Скомпилированный модуль с типами и манифестом».",
    ),
    (
        "boxing",
        "Boxing — упаковать value type в object (аллокация в куче). Unboxing — обратно с кастом.\n"
        "Пример: object o = 5; int x = (int)o;\n"
        "Что сказать: «Упаковка значимого типа в object; лучше generics без boxing».",
    ),
    (
        "модификатор sealed",
        "sealed на классе — нельзя наследовать. sealed override — нельзя дальше переопределять метод.\n"
        "Что сказать: «Запрет наследования/дальнейшего override».",
    ),
    (
        "asbtract и sealed",
        "Нет, abstract и sealed одновременно на классе нельзя — противоречие.\n"
        "Что сказать: «Нельзя».",
    ),
    (
        "абстрактного класса",
        "Класс-заготовка: может иметь реализацию и abstract-методы. Экземпляр напрямую не создают.\n"
        "Что сказать: «Частично реализованный базовый тип».",
    ),
    (
        "дополнительную обработку при подписывании",
        "Можно обернуть add/remove у event (custom event accessors) и добавить логику.\n"
        "Что сказать: «Кастомные add/remove у event».",
    ),
    (
        "возвращено в случае возникновения исключительной",
        "В коде try { DoWork(); return 1; } catch { return 2; } finally { return 3; } "
        "вернётся 3 — return в finally перекрывает. Так писать нельзя.\n"
        "Что сказать: «finally с return перебивает; на практике return в finally не используют».",
    ),
    (
        "dowork отработает без ошибок",
        "При том же коде с return в finally снова вернётся 3, даже если DoWork успешен.\n"
        "Что сказать: «Снова 3 из finally; это плохой стиль».",
    ),
    (
        "public class node",
        "Дерево узлов Parent/Children. Корень — Parent == null.\n"
        "Уровень: идём вверх по Parent, считаем шаги.\n"
        "Обход: печатаем уровень+имя, рекурсивно дети.\n"
        "Что сказать: «Self-reference Parent + рекурсия по Children».",
    ),
    (
        "дополнительная обработка при подписывании",
        "Можно обернуть add/remove у event (custom event accessors) и добавить логику.\n"
        "Что сказать: «Кастомные add/remove у event».",
    ),
    (
        "abstract и sealed",
        "Нет, abstract и sealed одновременно на классе нельзя — противоречие.\n"
        "Что сказать: «Нельзя».",
    ),
    (
        "protected internal",
        "Видно: внутри сборки ИЛИ наследникам (даже из другой сборки).\n"
        "Что сказать: «internal ИЛИ protected».",
    ),
    (
        "понимание event",
        "event — обёртка над делегатом: снаружи только +=/-=, вызвать чужой event нельзя.\n"
        "Что сказать: «Безопасная подписка на уведомления».",
    ),
    (
        "event принимать значение null",
        "Поле делегата события может быть null, если никто не подписан.\n"
        "Что сказать: «Да, если нет подписчиков».",
    ),
    (
        "понимание интерфейса",
        "Контракт: что уметь, без как. Класс может реализовать много интерфейсов.\n"
        "Что сказать: «Договор о поведении».",
    ),
    (
        "интерфейс содержать делегаты",
        "Интерфейс может объявлять events; обычные instance-поля — нет.\n"
        "Что сказать: «Events да; instance-поля нет».",
    ),
    (
        "интерфейс содержать события",
        "Да, интерфейс может объявлять event.\n"
        "Что сказать: «Да».",
    ),
    (
        "множественное наследование интерфейсов",
        "Да, класс/интерфейс может наследовать много интерфейсов.\n"
        "Что сказать: «Да».",
    ),
    (
        "iworkera",
        "Если два интерфейса с одинаковым методом — один общий метод или explicit-реализация.\n"
        "Что сказать: «Общий метод или explicit».",
    ),
    (
        "инструкций is и as",
        "is — проверка типа. as — безопасный cast для reference (иначе null).\n"
        "Что сказать: «is = проверка, as = null при неудаче».",
    ),
    (
        "(ttype)value",
        "Жёсткий cast (T)x при неудаче → InvalidCastException. as → null.\n"
        "Что сказать: «(T) — exception; as — null».",
    ),
    (
        "value as ttype",
        "as обычно для reference types. Не тот тип → null без exception.\n"
        "Что сказать: «as → null при неудаче».",
    ),
    (
        "обобщенных (generic)",
        "Generics — типы с параметром T: List<int>. Типобезопасность без кастов.\n"
        "Что сказать: «Переиспользование кода с сохранением типов».",
    ),
    (
        "ограничений параметров обобщенных",
        "where T : class, new(), IDisposable — ограничения на T.\n"
        "Что сказать: «where ограничивает допустимые T».",
    ),
    (
        "аргумента в конструкции foreach",
        "Тип с GetEnumerator() / IEnumerable.\n"
        "Что сказать: «IEnumerable или подходящий GetEnumerator».",
    ),
    (
        "ienumerable, ienumerator",
        "IEnumerable — можно перебрать. IEnumerator — Current/MoveNext.\n"
        "Что сказать: «Последовательность и её перечислитель».",
    ),
    (
        "понимание array",
        "Массив — фиксированная длина, доступ по индексу.\n"
        "Что сказать: «Фиксированная длина, быстрый индекс».",
    ),
    (
        "copyto() и system.array.clone()",
        "Clone — новый массив (поверхностная копия). CopyTo — копирует в уже существующий.\n"
        "Что сказать: «Clone создаёт новый, CopyTo пишет в целевой».",
    ),
    (
        "коллекций и списков",
        "Коллекции — List, Dictionary, HashSet… List — динамический массив.\n"
        "Что сказать: «Готовые структуры данных под задачу».",
    ),
    (
        "idictionary",
        "Словарь ключ→значение с быстрым поиском.\n"
        "Что сказать: «Ассоциативный массив».",
    ),
    (
        "idictionary.add",
        "Add — если ключ есть, exception. indexer[] = — вставит или перезапишет.\n"
        "Что сказать именно так.",
    ),
    (
        "foreach(var item in dictionary)",
        "Во время foreach нельзя менять состав словаря (Add/Remove).\n"
        "Что сказать: «Не модифицировать коллекцию в foreach».",
    ),
    (
        "операций ? и ??",
        "?: тернарный if. ?? — если null, взять справа. ?. — безопасный доступ.\n"
        "Что сказать: «?? и ?. для null-безопасности».",
    ),
    (
        "понимание рекурсии",
        "Функция вызывает себя + условие выхода.\n"
        "Что сказать: «Самовызов + база рекурсии».",
    ),
    (
        "рекурсивного обхода дерева",
        "Печатаем уровень+имя, затем рекурсивно дети с level+1.\n"
        "Что сказать: «Обход: узел → дети».",
    ),
    (
        "юнит-тест",
        "Автопроверка маленького куска логики. Ловит регрессии.\n"
        "Что сказать: «Быстрый изолированный тест единицы кода».",
    ),
    (
        "создать юнит-тест",
        "Test-проект (xUnit/NUnit) + Arrange-Act-Assert.\n"
        "Что сказать: «Отдельный test-проект и AAA».",
    ),
    (
        "структуры (struct) имплементировать интерфейсы",
        "Да, struct может реализовывать интерфейсы (но будет boxing при приведении к интерфейсу).\n"
        "Что сказать: «Да, с оговоркой про boxing».",
    ),
    (
        "структуры (struct) иметь статический конструктор",
        "Да, static constructor у struct допустим.\n"
        "Что сказать: «Да».",
    ),
    (
        "структуры (struct) содержать события",
        "Да, могут объявлять event, но mutable struct + event — осторожно.\n"
        "Что сказать: «Технически да».",
    ),
    (
        "только конструкторы с параметрами",
        "У struct всегда есть неявный конструктор по умолчанию (обнуление). Явный безпараметровый historically ограничен версиями.\n"
        "Что сказать: «Есть default-инициализация нулями; детали зависят от версии C#».",
    ),
    (
        "iqueryable",
        "IQueryable — выражение для провайдера (часто SQL). IEnumerable — уже в памяти CLR.\n"
        "Where на IQueryable может уйти в SQL; на IEnumerable фильтрует в процессе.\n"
        "Что сказать: «IQueryable строится в запрос к источнику; IEnumerable — локально».",
    ),
    (
        "момент применяется условие отбора",
        "У IEnumerable — при перечислении (лениво). У IQueryable — когда запрос материализуется "
        "(ToList/foreach), и условие может уйти на сервер.\n"
        "Что сказать: «Deferred execution до материализации».",
    ),
    (
        "понимание linq",
        "Удобный язык запросов к коллекциям/провайдерам: Where, Select, Join…\n"
        "Что сказать: «Запросы к данным в коде».",
    ),
    (
        "понимание expression",
        "Expression Tree — дерево выражения, которое можно разобрать (EF/SQL), а не сразу выполнить как делегат.\n"
        "Что сказать: «Данные о коде, а не сам выполняемый код».",
    ),
    (
        "func<string> от expression",
        "Func — готовый делегат для выполнения.\n"
        "Expression<Func> — описание выражения для анализа провайдером.\n"
        "Что сказать именно так.",
    ),
    (
        "понимание idisposable",
        "Контракт «закрой ресурс»: файлы, соединения. using вызовет Dispose.\n"
        "Что сказать: «Освобождение ресурсов детерминированно».",
    ),
    (
        "секции using (var value",
        "using создаёт область и гарантирует Dispose в finally.\n"
        "Что сказать: «Авто-Dispose даже при ошибке».",
    ),
    (
        "разворачивается using",
        "try { ... } finally { if (x != null) x.Dispose(); } (упрощённо).\n"
        "Что сказать: «try/finally + Dispose».",
    ),
    (
        "dispose от finalize",
        "Dispose — явный/быстрый. Finalizer (~Class) — запасной путь от GC, момент непредсказуем; "
        "после Dispose вызывают GC.SuppressFinalize.\n"
        "Что сказать: Dispose сейчас, Finalizer — страховка GC.",
    ),
    (
        "объявить деструктор класса",
        "Да, ~MyClass() — это finalizer. Наследовать «вызов цепочки» особенный; руками обычно не пишут без нужды.\n"
        "Что сказать: «Деструктор = finalizer, лучше IDisposable».",
    ),
    (
        "деструктор класса принудительно",
        "Напрямую вызвать нельзя. GC.Collect/WaitForPendingFinalizers — почти антипаттерн.\n"
        "Что сказать: «Принудительно не вызывают».",
    ),
    (
        "деструктор структур",
        "Нет, у struct деструктора/finalizer нет.\n"
        "Что сказать: «Нельзя».",
    ),
    (
        "разницу между нитью (thread) и процессом",
        "Процесс — изолированная программа с памятью. Потоки — исполнители внутри процесса, делят память.\n"
        "Что сказать: процесс = изоляция, потоки = параллельность внутри.",
    ),
    (
        "потокобезопасность",
        "Корректная работа при одновременном доступе нескольких потоков (без гонок и битых данных).\n"
        "Что сказать: «Нет гонок за общее состояние».",
    ),
    (
        "gac",
        "GAC — Global Assembly Cache: общие сборки для машины (сильнее актуально для старого .NET Framework).\n"
        "Что сказать: «Общий кэш сборок машины; в .NET Core/5+ почти не используют».",
    ),
    (
        "частные и общие сборки",
        "Частная — рядом с приложением. Общая — в GAC/shared, версия сильным именем.\n"
        "Что сказать: private vs shared/GAC.",
    ),
    # SQL
    (
        "типы индексов существуют",
        "Кластерный / некластерный, составные, покрывающие, уникальные; в разных СУБД ещё hash/GIN…\n"
        "Что сказать: «Как минимум clustered/nonclustered + unique/composite».",
    ),
    (
        "типы соединений таблиц",
        "INNER, LEFT, RIGHT, FULL, CROSS.\n"
        "Что сказать и кратко объяснить каждый.",
    ),
    (
        "временная таблица",
        "Таблица на время сессии/пакета: #temp в SQL Server или TABLE variable.\n"
        "Что сказать: «#temp для промежуточных данных в сессии».",
    ),
    (
        "что такое курсор",
        "Построчный обход результата. Обычно медленнее set-based SQL — используют редко.\n"
        "Что сказать: «Построчная обработка; предпочитаю наборные запросы».",
    ),
    (
        "truncate отличается от delete",
        "DELETE — строки, можно WHERE, логируется детально.\n"
        "TRUNCATE — быстрая очистка всей таблицы, почти без построчного лога.\n"
        "Что сказать именно так.",
    ),
    (
        "select top 0",
        "Получить структуру результата без данных (метаданные/пустой набор) — удобно в ETL/временных таблицах.\n"
        "Что сказать: «Схема без строк».",
    ),
    (
        "основного ключа",
        "Часто surrogate: IDENTITY/int или uniqueidentifier(Guid). В Creatio — Guid.\n"
        "Что сказать: «Стабильный surrogate key; в Creatio Guid».",
    ),
    (
        "datareader",
        "Прямой быстрый forward-only ридер строк из БД в ADO.NET.\n"
        "Что сказать: «Потоковое чтение результата SQL».",
    ),
    (
        "групповой символ",
        "В LIKE: % (любая длина), _ (один символ). В некоторых СУБД [] и т.п.\n"
        "Что сказать: «% и _ в LIKE».",
    ),
    (
        "правиле acid",
        "Atomicity Consistency Isolation Durability — всё или ничего, правила целостности, изоляция, сохранность.\n"
        "Что сказать расшифровку четырёх букв.",
    ),
    (
        "initial catalog",
        "Имя базы данных в connection string.\n"
        "Что сказать: «К какой БД подключаемся».",
    ),
    (
        "виды операторов вы знаете",
        "DDL (CREATE), DML (SELECT/INSERT/UPDATE/DELETE), DCL (GRANT), TCL (COMMIT/ROLLBACK).\n"
        "Что сказать этот список.",
    ),
    (
        "что такое having",
        "Фильтр групп после GROUP BY (можно с агрегатами). WHERE — до группировки.\n"
        "Что сказать: «WHERE строки, HAVING группы».",
    ),
    (
        "inner join от left join",
        "INNER — только совпадения. LEFT — все слева + совпадения справа (иначе NULL).\n"
        "Что сказать именно так.",
    ),
    (
        "full join минус inner",
        "Строки, которые есть только слева или только справа: FULL OUTER JOIN … WHERE a.key IS NULL OR b.key IS NULL "
        "(эмуляция через UNION LEFT/RIGHT тоже возможна).\n"
        "Что сказать: «FULL OUTER с фильтром IS NULL с одной из сторон».",
    ),
    (
        "уровни изоляции транзакций",
        "Read Uncommitted, Read Committed, Repeatable Read, Serializable (+ Snapshot в SQL Server).\n"
        "Что сказать список + dirty/non-repeatable/phantom.",
    ),
    (
        "отношения n:n",
        "Три: две сущности + таблица связи.\n"
        "Что сказать: «Две таблицы + link-таблица».",
    ),
    (
        "сотрудники и должности",
        "Таблица Employee (Id, ManagerId self-FK, PositionId FK) и Position. Иерархия — self-reference ManagerId.\n"
        "Что сказать: «Справочник должностей + self-FK руководителя».",
    ),
    (
        "нормализацию и денормализацию",
        "Нормализация убирает дубли. Денормализация ускоряет чтение ценой дублирования.\n"
        "Что сказать: trade-off целостность vs скорость чтения.",
    ),
    (
        "нормальные формы",
        "1NF атомарность, 2NF нет частичных зависимостей, 3NF нет транзитивных. Дальше BCNF…\n"
        "Что сказать кратко 1–3 NF.",
    ),
    (
        "какие субд существуют",
        "Реляционные: SQL Server, PostgreSQL, Oracle, MySQL. Документные/ключ-значение: Mongo, Redis.\n"
        "Что сказать: реляционные + NoSQL примеры.",
    ),
    (
        "список выполняющихся запросов",
        "В SQL Server: DMV sys.dm_exec_requests + sys.dm_exec_sql_text / Activity Monitor.\n"
        "Что сказать: «DMV / Activity Monitor».",
    ),
    (
        "большим объемом данных",
        "Индексы, партиции, пагинация, не SELECT *, архивация, batch-обработка, правильная статистика.\n"
        "Что сказать этот чеклист.",
    ),
    (
        "не закоммиченая",
        "Держит блокировки, данные не видны другим (зависит от изоляции), при обрыве — rollback.\n"
        "Что сказать: «Долгая незакрытая транзакция = блокировки и риск отката».",
    ),
    (
        "recovery model",
        "SQL Server: Simple, Full, Bulk-logged — разный объём лога и возможности point-in-time restore.\n"
        "Что сказать три модели и зачем Full для PITR.",
    ),
    (
        "иерархия классов (a, b: a",
        "Варианты: Table Per Hierarchy / Type / Concrete. Часто одна таблица с типом-дискриминатором или отдельные таблицы + связь.\n"
        "Что сказать: «TPH/TPT; выбираю по запросам и простоте».",
    ),
    (
        "классов-поставщиков данных",
        "SqlClient и др.: плюс — нативно и быстро под СУБД; минус — привязка к провайдеру, больше кода vs ORM.\n"
        "Что сказать: контроль/скорость vs удобство.",
    ),
    (
        "соединения поддерживаются microsoft sql server",
        "TCP/IP, Named Pipes, Shared Memory (локально).\n"
        "Что сказать эти три.",
    ),
    (
        "аутентификацию windows и sql server",
        "Windows auth — доверенная (через ОС/домен). SQL auth — логин/пароль SQL (не «trusted»).\n"
        "Что сказать: Windows = trusted, SQL login = нет.",
    ),
    (
        "пагинацию в raw sql",
        "ORDER BY + OFFSET/FETCH (SQL Server) или LIMIT/OFFSET (PostgreSQL).\n"
        "Что сказать: «ORDER BY обязателен + OFFSET/FETCH».",
    ),
    (
        "принципа acid",
        "То же: атомарность, согласованность, изоляция, долговечность.\n"
        "Что сказать расшифровку.",
    ),
    (
        "миграци схемы бд",
        "Версионирование изменений схемы: EF Migrations, FluentMigrator, SQL-скрипты в CI, в Creatio — через пакеты/схемы объектов.\n"
        "Что сказать: «Миграции кодом/скриптами + на Creatio через конфигурацию».",
    ),
    # Creatio empty
    (
        "основных компонентов состоит creatio",
        "Обязательно: приложение Creatio (.NET), веб-сервер (IIS), СУБД.\n"
        "Часто рядом: Redis (сессии/кэш), файловое хранилище, почта; опционально очереди, поиск.\n"
        "Что сказать: «IIS + app + БД; Redis почти всегда на боевых стендах».",
    ),
    (
        "ldap ad",
        "Интеграция с Active Directory/LDAP для пользователей и входа: синхронизация оргструктуры/учёток и SSO-подобная корпоративная аутентификация (настройка в админке Creatio).\n"
        "Что сказать: «Синхронизация пользователей/групп из AD + корпоративный вход».",
    ),
    (
        "dataservice",
        "DataService — серверный API Creatio для работы с данными (CRUD сущностей) извне/интеграций, наряду с OData.\n"
        "Что сказать: «Сервис доступа к данным конфигурации Creatio».",
    ),
    # WEB empty
    (
        "viewstate",
        "ViewState в WebForms хранит состояние контролов между постбэками (часто в hidden field). Плюс — удобство; минус — раздувает страницу.\n"
        "Что сказать: «Состояние страницы WebForms; тяжёлый трафик».",
    ),
    (
        "sessionstate и applicationstate",
        "Session — на пользователя. Application — на всё приложение. Session можно в InProc/StateServer/SQL/Redis.\n"
        "Что сказать: Session per user, Application global.",
    ),
    (
        "хранить состояние сессии",
        "InProc, State Server, SQL Server, Redis/distributive cache. В ферме — не InProc.\n"
        "Что сказать: «Для нескольких серверов — out-of-proc (часто Redis)».",
    ),
    (
        "static свойства классов доступны",
        "Да, static общие на AppDomain/процесс — видны разным запросам. Это опасно для user-данных.\n"
        "Что сказать: «Static общий; user-данные туда не класть».",
    ),
    (
        "validateinput",
        "Проверка входящих данных запроса на потенциально опасный HTML/script (защита от XSS в старых ASP.NET).\n"
        "Что сказать: «Валидация входа против XSS».",
    ),
    (
        "работают cookies",
        "Куки — кусочки данных в браузере, уходят с запросами на домен. Злоупотребление: кража сессии, XSS → cookie steal.\n"
        "Что сказать: «HttpOnly/Secure; не хранить секреты в обычной куке».",
    ),
    (
        "что такое ajax",
        "Запросы к серверу без полной перезагрузки страницы.\n"
        "Что сказать: «Асинхронный обмен данными с сервером в фоне».",
    ),
    (
        "контекст ? что такое this",
        "this — текущий контекст вызова функции в JS. В ASP.NET «контекст» часто HttpContext текущего запроса.\n"
        "Что сказать: различать JS this и HttpContext.",
    ),
    (
        "каков результат ?    function a(x)",
        "Из-за var/подъёма и локальной переменной ответ определяется правилами scope. Готовьтесь объяснить hoisting на примере из билета.\n"
        "Что сказать: «Разберу построчно: параметры, var hoist, return».",
    ),
    (
        "каков результат ?    var x = 10",
        "Из-за hoisting var x внутри a будет undefined до присваивания — классический вопрос.\n"
        "Что сказать: «Hoisting var → undefined до строки присваивания».",
    ),
    (
        "наследование в js",
        "Прототипы / class extends / Object.create. В Creatio — Ext.define / extend схем.\n"
        "Что сказать: «Прототипное наследование или class sugar».",
    ),
    (
        "работают замыкания",
        "Функция помнит внешние переменные lexical scope.\n"
        "Что сказать: «Функция + её окружение».",
    ),
    (
        "обмен данных между двумя окнами",
        "postMessage, shared localStorage events, BroadcastChannel, cookies (редко).\n"
        "Что сказать: «postMessage — безопасный стандарт».",
    ),
    (
        "жизненый цикл страницы в asp.net",
        "Init → Load → обработчики событий postback → PreRender → Render → Unload (упрощённо).\n"
        "Что сказать этапы WebForms lifecycle.",
    ),
    (
        "методы аутентификации есть в iis",
        "Anonymous, Basic, Windows/NTLM/Kerberos, Forms (на уровне app), сертификаты и т.д.\n"
        "Что сказать несколько основных.",
    ),
    (
        "динамические контролы",
        "Создавать на Init/Load каждый запрос заново с теми же ID, иначе ViewState/события сломаются.\n"
        "Что сказать: «Пересоздавать рано и стабильно по ID».",
    ),
    (
        "постбэк",
        "Postback — повторная отправка страницы на сервер (WebForms). SPA/AJAX могут обойтись без полного постбэка.\n"
        "Что сказать: «Полный round-trip страницы; можно заменить AJAX».",
    ),
    (
        "нити (threads) asp.net",
        "Потоки из пула переиспользуются между запросами. Поэтому нельзя оставлять «грязное» Thread-static/культурное состояние.\n"
        "Что сказать: «Пул потоков переиспользуется; контекст запроса изолируйте».",
    ),
    (
        "httphandler",
        "Лёгкий обработчик под специальный путь (.ashx) без тяжёлой страницы — отдача файлов, webhook.\n"
        "Что сказать: «Точечный endpoint без page lifecycle».",
    ),
    (
        "безопасности web-приложений",
        "HTTPS, валидация входа, параметризация SQL, защита XSS/CSRF, authZ, безопасные cookies, обновления.\n"
        "Что сказать этот чеклист.",
    ),
    (
        "forms-auth",
        "Логин-форма → cookie аутентификации → модуль проверяет на каждый запрос; роли отдельно.\n"
        "Что сказать: «Ticket/cookie после логина».",
    ),
    (
        "membership провайдер",
        "Абстракция ASP.NET для пользователей/паролей (провайдерная модель). Сейчас чаще Identity.\n"
        "Что сказать: «Провайдер учёток старого ASP.NET».",
    ),
    (
        "mvc routing",
        "Сопоставление URL шаблонам → controller/action.\n"
        "Что сказать: «Маршрутизация URL на действия».",
    ),
    (
        "виртуальных саб-доменов",
        "Да, через route constraints / middleware, читая Host и мапя на параметр tenant.\n"
        "Что сказать: «Да, по Host header».",
    ),
    (
        "mvc areas",
        "Зоны большого приложения (Admin/Shop) со своими контроллерами/вьюхами.\n"
        "Что сказать: «Модульное деление MVC».",
    ),
    (
        "mvc filters",
        "Атрибуты/фильтры вокруг action: auth, log, exception. Пример Authorize.\n"
        "Что сказать: «Cross-cutting до/после action».",
    ),
    (
        "кеширование результата action",
        "OutputCache / Response Caching / IMemoryCache вокруг результата action с ключом и TTL.\n"
        "Что сказать: «Кэш ответа или серверный cache с TTL».",
    ),
]


def lookup_answer(question: str) -> str:
    nq = norm(question)
    best = ""
    best_len = 0
    for key, ans in ANSWER_BANK:
        k = norm(key)
        if k in nq and len(k) > best_len:
            best = ans
            best_len = len(k)
    return best


def load_user_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(UPLOADS.glob("*.xlsx")):
        wb = openpyxl.load_workbook(path, data_only=True)
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            src = sheet
            for r in range(1, ws.max_row + 1):
                topic = ws.cell(r, 1).value
                q = ws.cell(r, 2).value
                a = ws.cell(r, 3).value
                if not q or not str(q).strip():
                    continue
                topic_s = str(topic).strip().replace("С#", "C#") if topic else "Разное"
                if topic_s in {"None", "none"}:
                    topic_s = "Разное"
                rows.append(
                    {
                        "topic": topic_s,
                        "question": str(q).strip(),
                        "answer": str(a).strip() if a else "",
                        "source": src,
                        "nq": norm(str(q)),
                    }
                )
    # dedupe: prefer longer non-empty answer
    by: dict[str, dict] = {}
    for row in rows:
        prev = by.get(row["nq"])
        if not prev:
            by[row["nq"]] = row
            continue
        sources = {prev["source"], row["source"]}
        chosen = row if len(row["answer"]) > len(prev["answer"]) else prev
        chosen = dict(chosen)
        chosen["source"] = " + ".join(sorted(sources))
        by[row["nq"]] = chosen
    return list(by.values())


TOPIC_SHEET = {
    "C#": "Ваши_C#",
    "SQL": "Ваши_SQL",
    "БД": "Ваши_SQL",
    "CR": "Ваши_Creatio",
    "АВ": "Ваши_Creatio_админ",
    "WEB": "Ваши_WEB",
    "JS": "Ваши_JS",
}


def style_sheet(ws) -> None:
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="1F4E79")
    cat_fill = PatternFill("solid", fgColor="D6E3F0")
    thin = Border(
        left=Side(style="thin", color="B0B0B0"),
        right=Side(style="thin", color="B0B0B0"),
        top=Side(style="thin", color="B0B0B0"),
        bottom=Side(style="thin", color="B0B0B0"),
    )
    wrap = Alignment(wrap_text=True, vertical="top")
    widths = [14, 42, 88, 22, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    if ws.max_row >= 1:
        ws.auto_filter.ref = f"A1:E{ws.max_row}"
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=5):
        for idx, cell in enumerate(row):
            cell.border = thin
            cell.alignment = wrap
            if idx == 0:
                cell.fill = cat_fill
                cell.font = Font(bold=True)
        ans = str(row[2].value or "")
        h = 60 + 12 * ans.count("\n") + len(ans) // 90 * 8
        ws.row_dimensions[row[0].row].height = max(55, min(200, h))


def enrich(row: dict) -> dict:
    answer = row["answer"]
    note = ""
    if answer:
        answer = simplify_existing(answer)
        # If answer looks wrong for DI question in one file (immutable text) — keep as-is but user had mixed notes
    else:
        generated = lookup_answer(row["question"])
        if generated:
            answer = generated
            note = "ответ дополнен"
        else:
            answer = (
                "Кратко своими словами: вспомните определение из учебника/документации и добавьте 1 пример. "
                "Если тема Creatio — свяжите с пакетами/ESQ/процессами.\n"
                "Что сказать: термин + зачем нужен + маленький пример."
            )
            note = "заготовка — допишите"
    if note and note not in answer:
        answer = answer + f"\n\n[{note}]"
    return {**row, "answer": answer}


def merge_into_workbook(path: Path, groups: dict[str, list[dict]]) -> None:
    wb = openpyxl.load_workbook(path)
    # remove old merged sheets if re-run
    for name in list(wb.sheetnames):
        if name.startswith("Ваши_"):
            del wb[name]

    # update overview
    if "Содержание" in wb.sheetnames:
        ov = wb["Содержание"]
        # find first empty-ish area after existing meta
        start = ov.max_row + 2
        ov.cell(start, 1).value = "Добавлено из ваших файлов"
        ov.cell(start, 1).font = Font(bold=True, color="1F4E79")
        ov.cell(start + 1, 1).value = "Лист"
        ov.cell(start + 1, 2).value = "Откуда"
        ov.cell(start + 1, 3).value = "Q&A"
        r = start + 2
        for sheet, rows in groups.items():
            ov.cell(r, 1).value = sheet
            ov.cell(r, 2).value = "Собес имени меня + Собеседование (уникальные)"
            ov.cell(r, 3).value = len(rows)
            r += 1
        ov.cell(r + 1, 1).value = "Как пользоваться"
        ov.cell(r + 1, 2).value = (
            "Сначала листы C#/SQL/… (учебные ответы «для чайников»), "
            "затем листы «Ваши_*» — ваши билеты. Пустые ответы заполнены простым текстом; "
            "где было «[заготовка]» — допишите по резюме."
        )
        ov.cell(r + 1, 2).alignment = Alignment(wrap_text=True)
        ov.row_dimensions[r + 1].height = 60

    for sheet_name, rows in groups.items():
        ws = wb.create_sheet(sheet_name)
        ws.append(HEADER)
        for row in sorted(rows, key=lambda x: (x["topic"], x["question"].lower())):
            ws.append([row["topic"], row["question"], row["answer"], row["source"], ""])
        style_sheet(ws)

    wb.save(path)


def main() -> None:
    # Ensure base workbook exists
    gen = ROOT / "generate_interview_prep.py"
    if gen.exists():
        import runpy

        runpy.run_path(str(gen), run_name="__main__")

    raw = load_user_rows()
    enriched = [enrich(r) for r in raw]

    groups: dict[str, list[dict]] = {}
    for row in enriched:
        sheet = TOPIC_SHEET.get(row["topic"], "Ваши_прочее")
        groups.setdefault(sheet, []).append(row)

    for out in OUTPUTS:
        if not out.exists():
            raise SystemExit(f"missing {out}")
        merge_into_workbook(out, groups)
        print(f"Updated {out.name}: +{sum(len(v) for v in groups.values())} user Q&A across {len(groups)} sheets")
        for k, v in groups.items():
            emptyish = sum(1 for x in v if "[заготовка" in x["answer"])
            filled = sum(1 for x in v if "[ответ дополнен]" in x["answer"])
            print(f"  {k}: {len(v)} (generated {filled}, stubs {emptyish})")


if __name__ == "__main__":
    main()
