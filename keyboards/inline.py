from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="run_analysis")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="open_settings")],
        [InlineKeyboardButton(text="📅 Расписание", callback_data="open_schedule")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="open_help")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📄 Формат отчета", callback_data="settings_format")],
        [InlineKeyboardButton(text="⏱ Период анализа", callback_data="settings_period")],
        [InlineKeyboardButton(text="🌐 Источники", callback_data="settings_sources")],
        [InlineKeyboardButton(text="📈 Графики", callback_data="settings_charts")],
        [InlineKeyboardButton(text="🈯 Язык", callback_data="settings_language")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="PDF", callback_data="format_pdf"),
         InlineKeyboardButton(text="Excel", callback_data="format_excel"),
         InlineKeyboardButton(text="HTML", callback_data="format_html")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sources_keyboard(sources: dict | None = None) -> InlineKeyboardMarkup:
    sources = sources or {"reddit": True, "freelance": True, "trends": True}
    def mark(name: str) -> str:
        return "✅" if sources.get(name, True) else "❌"
    buttons = [
        [InlineKeyboardButton(text=f"Reddit {mark('reddit')}", callback_data="src_reddit")],
        [InlineKeyboardButton(text=f"Freelance {mark('freelance')}", callback_data="src_freelance")],
        [InlineKeyboardButton(text=f"Trends {mark('trends')}", callback_data="src_trends")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="open_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def schedule_management_keyboard(schedules: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in schedules:
        buttons.append([InlineKeyboardButton(text=f"🕐 {s}", callback_data=f"schedule_{s}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить", callback_data="schedule_add")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm:{callback_data}"),
         InlineKeyboardButton(text="❌ Нет", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
