"""
ОГЭ Подготовка — Telegram Bot
Бот для подготовки к ОГЭ по нескольким предметам.
Поддерживает: Физика, Математика, Русский язык, Информатика.

Для запуска:
1. pip install python-telegram-bot==20.7
2. Вставь свой токен в config.py
3. python bot.py
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from config import BOT_TOKEN
from subjects import physics, math_oge, russian, informatics

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Состояния диалога ───────────────────────────────────────────
(
    CHOOSE_SUBJECT,
    CHOOSE_ACTION,
    CHOOSE_TASK_NUM,
    WAITING_ANSWER,
    READING_CONSPECT,
    SEARCH_DEFINITION,
) = range(6)

# ─── Реестр предметов ────────────────────────────────────────────
SUBJECTS = {
    "physics": {
        "name": "🔬 Физика",
        "module": physics,
    },
    "math": {
        "name": "📐 Математика",
        "module": math_oge,
    },
    "russian": {
        "name": "📖 Русский язык",
        "module": russian,
    },
    "informatics": {
        "name": "💻 Информатика",
        "module": informatics,
    },
}


# ─── /start ──────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Приветствие и выбор предмета."""
    context.user_data.clear()

    text = (
        "👋 Привет! Я бот для подготовки к *ОГЭ*.\n\n"
        "Выбери предмет, к которому хочешь готовиться:"
    )
    keyboard = []
    for key, subj in SUBJECTS.items():
        keyboard.append(
            [InlineKeyboardButton(subj["name"], callback_data=f"subj_{key}")]
        )

    await _send(update, text, InlineKeyboardMarkup(keyboard))
    return CHOOSE_SUBJECT


# ─── Выбор предмета ──────────────────────────────────────────────
async def choose_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    subj_key = query.data.replace("subj_", "")
    context.user_data["subject"] = subj_key
    module = SUBJECTS[subj_key]["module"]
    name = SUBJECTS[subj_key]["name"]

    if not module.is_ready():
        await query.edit_message_text(
            f"{name}\n\n⚠️ Этот предмет пока в разработке.\n"
            "Задания скоро будут добавлены!\n\n"
            "Нажми /start чтобы выбрать другой предмет."
        )
        return ConversationHandler.END

    text = f"*{name}*\n\nЧто хочешь делать?"
    keyboard = [
        [InlineKeyboardButton("✏️ Решать задания", callback_data="action_solve")],
        [InlineKeyboardButton("📚 Конспекты", callback_data="action_conspect")],
        [InlineKeyboardButton("📖 Обозначения", callback_data="action_defs")],
        [InlineKeyboardButton("🔙 Сменить предмет", callback_data="action_back")],
    ]
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    return CHOOSE_ACTION


# ─── Выбор действия ──────────────────────────────────────────────
async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.replace("action_", "")

    # Если состояние слетело (нет выбранного предмета) — на старт
    subj_key = context.user_data.get("subject")
    if not subj_key:
        return await start(update, context)

    module = SUBJECTS[subj_key]["module"]

    if action == "back":
        return await start(update, context)

    # ── Возврат в меню предмета (после решения / после конспекта) ──
    if action == "back_menu":
        return await back_to_menu(update, context)

    # ── Конспекты ──
    if action == "conspect":
        topics = module.get_conspect_topics()
        if not topics:
            await query.edit_message_text(
                "📚 Конспекты для этого предмета пока не добавлены.\n\n"
                "Нажми /start чтобы вернуться."
            )
            return ConversationHandler.END

        keyboard = []
        for topic_key, topic_name in topics.items():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        topic_name, callback_data=f"conspect_{topic_key}"
                    )
                ]
            )
        keyboard.append(
            [InlineKeyboardButton("🔙 Назад", callback_data="action_back_menu")]
        )

        await query.edit_message_text(
            "📚 *Конспекты*\n\nВыбери тему:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return READING_CONSPECT

    # ── Обозначения ──
    if action == "defs":
        get_cats = getattr(module, "get_definition_categories", None)
        if not callable(get_cats):
            await query.edit_message_text(
                "📖 Обозначения для этого предмета пока не добавлены.\n\n"
                "Нажми /start чтобы вернуться.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="action_back_menu")]
                ]),
            )
            return READING_CONSPECT

        categories = get_cats()
        if not categories:
            await query.edit_message_text(
                "📖 Обозначения для этого предмета пока не добавлены."
            )
            return ConversationHandler.END

        keyboard = []
        for cat_key, cat_name in categories.items():
            keyboard.append([
                InlineKeyboardButton(cat_name, callback_data=f"def_{cat_key}")
            ])
        # Кнопка поиска (только если у модуля есть search_definitions)
        if callable(getattr(module, "search_definitions", None)):
            keyboard.append([
                InlineKeyboardButton("🔎 Найти символ", callback_data="action_defsearch")
            ])
        keyboard.append(
            [InlineKeyboardButton("🔙 Назад", callback_data="action_back_menu")]
        )

        await query.edit_message_text(
            "📖 *Обозначения*\n\n"
            "Здесь — расшифровка букв в формулах: что значит каждый символ, "
            "в каких единицах измеряется и где встречается.\n\n"
            "Выбери раздел или нажми «Найти символ», чтобы искать по букве:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return READING_CONSPECT

    # ── Запуск поиска по символу ──
    if action == "defsearch":
        await query.edit_message_text(
            "🔎 *Поиск обозначения*\n\n"
            "Введи букву или часть слова. Я найду все определения по этому "
            "запросу — в том числе одинаковые буквы в разных разделах "
            "(например, *Q* — это и теплота, и заряд).\n\n"
            "Примеры запросов:\n"
            "• `Q` — найти все Q\n"
            "• `λ` — все «лямбды»\n"
            "• `теплота` — все обозначения, связанные с теплотой\n"
            "• `дискриминант` — найти D\n\n"
            "Нажми /cancel для отмены.",
            parse_mode="Markdown",
        )
        return SEARCH_DEFINITION

    # ── Решать задания ──
    if action == "solve":
        task_numbers = module.get_task_numbers()
        keyboard = []
        row = []
        for num in task_numbers:
            row.append(
                InlineKeyboardButton(str(num), callback_data=f"task_{num}")
            )
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append(
            [InlineKeyboardButton("🔙 Назад", callback_data="action_back_menu")]
        )

        await query.edit_message_text(
            "✏️ *Выбери номер задания:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return CHOOSE_TASK_NUM

    return CHOOSE_ACTION


# ─── Возврат в меню предмета ─────────────────────────────────────
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    subj_key = context.user_data["subject"]
    name = SUBJECTS[subj_key]["name"]

    text = f"*{name}*\n\nЧто хочешь делать?"
    keyboard = [
        [InlineKeyboardButton("✏️ Решать задания", callback_data="action_solve")],
        [InlineKeyboardButton("📚 Конспекты", callback_data="action_conspect")],
        [InlineKeyboardButton("📖 Обозначения", callback_data="action_defs")],
        [InlineKeyboardButton("🔙 Сменить предмет", callback_data="action_back")],
    ]
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    return CHOOSE_ACTION


# ─── Показать конспект ───────────────────────────────────────────
async def show_conspect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    topic_key = query.data.replace("conspect_", "")
    subj_key = context.user_data["subject"]
    module = SUBJECTS[subj_key]["module"]

    text = module.get_conspect(topic_key)

    keyboard = [
        [InlineKeyboardButton("📚 Другие темы", callback_data="action_conspect")],
        [InlineKeyboardButton("🔙 В меню", callback_data="action_back_menu")],
    ]

    # Telegram ограничивает сообщения 4096 символами — разбиваем
    chunks = _split_text(text, 4000)
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=chunk,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=chunk,
                parse_mode="Markdown",
            )

    return CHOOSE_ACTION


# ─── Показать обозначения раздела ────────────────────────────────
async def show_definitions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat_key = query.data.replace("def_", "")
    subj_key = context.user_data.get("subject")
    if not subj_key:
        return await start(update, context)

    module = SUBJECTS[subj_key]["module"]
    get_defs = getattr(module, "get_definitions", None)
    if not callable(get_defs):
        await query.edit_message_text("⚠️ Обозначения недоступны.")
        return ConversationHandler.END

    text = get_defs(cat_key)

    keyboard = [
        [InlineKeyboardButton("📖 Другие разделы", callback_data="action_defs")],
        [InlineKeyboardButton("🔙 В меню", callback_data="action_back_menu")],
    ]

    chunks = _split_text(text, 4000)
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=chunk,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=chunk,
                parse_mode="Markdown",
            )

    return CHOOSE_ACTION


# ─── Поиск обозначения по символу ────────────────────────────────
async def search_definition_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает текстовый запрос пользователя для поиска обозначения."""
    query_text = update.message.text.strip()
    subj_key = context.user_data.get("subject")
    if not subj_key:
        await update.message.reply_text("⚠️ Сессия истекла. Нажми /start")
        return ConversationHandler.END

    module = SUBJECTS[subj_key]["module"]
    search = getattr(module, "search_definitions", None)
    if not callable(search):
        await update.message.reply_text("⚠️ Поиск недоступен для этого предмета.")
        return ConversationHandler.END

    if len(query_text) > 50:
        await update.message.reply_text("⚠️ Слишком длинный запрос. Введи букву или короткое слово.")
        return SEARCH_DEFINITION

    results = search(query_text)

    keyboard = [
        [InlineKeyboardButton("🔎 Искать ещё", callback_data="action_defsearch")],
        [InlineKeyboardButton("📖 К разделам", callback_data="action_defs")],
        [InlineKeyboardButton("🔙 В меню", callback_data="action_back_menu")],
    ]

    if not results:
        text = (
            f"❌ По запросу `{query_text}` ничего не найдено.\n\n"
            "Попробуй:\n"
            "• ввести только символ (например, `Q` или `λ`)\n"
            "• ввести часть русского названия (например, `теплота`)"
        )
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSE_ACTION

    # Форматируем результаты
    safe_query = query_text.replace("_", "\\_").replace("*", "\\*").replace("`", "")
    lines = [f"🔎 По запросу `{safe_query}` найдено: *{len(results)}*\n"]

    # ограничим вывод до 15 результатов, чтобы не упереться в лимит Telegram
    shown = results[:15]
    for cat_name, item in shown:
        if len(item) == 5:
            symbol, name, unit, formula, mistake = item
        else:
            symbol, name, unit, formula = item
            mistake = None

        safe_sym = symbol.replace("_", "\\_").replace("*", "\\*")
        unit_part = f"[{unit}]" if unit else ""
        lines.append(f"\n📂 _{cat_name}_")
        lines.append(f"• *{safe_sym}* — {name} {unit_part}")
        if formula and formula != "—":
            lines.append(f"  ↳ `{formula}`")
        if mistake:
            safe_mistake = mistake.replace("_", "\\_")
            lines.append(f"  ⚠️ _{safe_mistake}_")

    if len(results) > 15:
        lines.append(f"\n_…и ещё {len(results) - 15} результатов. Уточни запрос._")

    text = "\n".join(lines)

    chunks = _split_text(text, 4000)
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await update.message.reply_text(
                chunk,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await update.message.reply_text(chunk, parse_mode="Markdown")

    return CHOOSE_ACTION


# ─── Выбор номера задания → показать задание ─────────────────────
async def choose_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # action_back_menu / action_solve обрабатываются choose_action (через pattern "^action_")
    # сюда приходят только callback'и вида "task_N"

    task_num = int(query.data.replace("task_", ""))
    context.user_data["task_num"] = task_num
    subj_key = context.user_data["subject"]
    module = SUBJECTS[subj_key]["module"]

    task = module.get_random_task(task_num)
    context.user_data["current_task"] = task

    text = (
        f"📝 *Задание №{task_num}*\n\n"
        f"{task['question']}\n\n"
        f"✍️ Напиши свой ответ:"
    )

    await query.edit_message_text(text, parse_mode="Markdown")
    return WAITING_ANSWER


# ─── Проверка ответа ─────────────────────────────────────────────
async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_answer = update.message.text.strip()
    task = context.user_data.get("current_task")
    task_num = context.user_data.get("task_num")
    subj_key = context.user_data.get("subject")

    if not task or not subj_key:
        await update.message.reply_text("⚠️ Задание не найдено. Нажми /start")
        return ConversationHandler.END

    module = SUBJECTS[subj_key]["module"]

    is_correct, feedback = module.check_answer(task, user_answer)

    if is_correct:
        text = "✅ *Правильно!*\n\n"
    else:
        text = "❌ *Неправильно.*\n\n"
        text += f"Твой ответ: `{user_answer}`\n"
        text += f"Правильный ответ: `{task['answer']}`\n\n"

    if feedback:
        text += f"📖 *Пояснение:*\n{feedback}\n\n"

    if task.get("best_answer"):
        text += f"🏆 *Лучший вариант ответа:*\n{task['best_answer']}\n\n"

    keyboard = [
        [
            InlineKeyboardButton(
                "▶️ Следующее задание", callback_data=f"task_{task_num}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔢 Другой номер", callback_data="action_solve"
            )
        ],
        [InlineKeyboardButton("🔙 В меню", callback_data="action_back_menu")],
    ]

    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_TASK_NUM


# ─── Вспомогательные функции ─────────────────────────────────────
async def _send(update: Update, text: str, markup=None):
    """Отправка сообщения и через message, и через callback_query."""
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=markup, parse_mode="Markdown"
        )
    elif update.message:
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="Markdown"
        )


def _split_text(text: str, max_len: int = 4000) -> list[str]:
    """Разбить длинный текст на части по абзацам."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current)
    return chunks


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("👋 До встречи! Нажми /start чтобы начать заново.")
    return ConversationHandler.END


# ─── Запуск бота ─────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_SUBJECT: [
                CallbackQueryHandler(choose_subject, pattern=r"^subj_"),
            ],
            CHOOSE_ACTION: [
                CallbackQueryHandler(choose_action, pattern=r"^action_"),
                CallbackQueryHandler(show_conspect, pattern=r"^conspect_"),
                CallbackQueryHandler(show_definitions, pattern=r"^def_"),
            ],
            CHOOSE_TASK_NUM: [
                CallbackQueryHandler(choose_task, pattern=r"^task_\d+"),
                CallbackQueryHandler(choose_action, pattern=r"^action_"),
            ],
            WAITING_ANSWER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer),
            ],
            READING_CONSPECT: [
                CallbackQueryHandler(show_conspect, pattern=r"^conspect_"),
                CallbackQueryHandler(show_definitions, pattern=r"^def_"),
                CallbackQueryHandler(choose_action, pattern=r"^action_"),
            ],
            SEARCH_DEFINITION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_definition_handler),
                CallbackQueryHandler(choose_action, pattern=r"^action_"),
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)

    logger.info("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
