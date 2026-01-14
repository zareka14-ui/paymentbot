import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
# Render автоматически передает порт в переменную PORT, если нет - используем 8080
PORT = int(os.getenv("PORT", 8080))
OFFER_LINK = "https://disk.yandex.ru/i/b3lgPjPheWM14w"

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования (важно для отладки в Render)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


# --- МАШИНА СОСТОЯНИЙ ---
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    confirm_data = State()
    waiting_for_payment_proof = State()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать регистрацию")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_progress(step):
    steps = ["⬜", "⬜", "⬜"]
    for i in range(min(step, 3)):
        steps[i] = "✅"
    return "".join(steps)


# --- ХЭНДЛЕРЫ БОТА ---


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "✨ **Трансформационная игра «СИЛА РОДА»**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Добро пожаловать. Чтобы записаться на игру, "
        "заполните короткую анкету.\n\n"
        "Нажмите кнопку ниже, чтобы начать"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_start_kb())


@dp.message(F.text == "🚀 Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer(
        f"{get_progress(0)}\n**Шаг 1:** Введите ваше **ФИО** полностью:",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    await state.set_state(Registration.waiting_for_name)


@dp.message(Registration.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"{get_progress(1)}\n**Шаг 2:** Напишите ваш **номер телефона** или @username:",
        parse_mode="Markdown",
    )
    await state.set_state(Registration.waiting_for_contact)


@dp.message(Registration.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    data = await state.get_data()

    # Сразу переходим к проверке
    summary = (
        f"{get_progress(2)}\n**ПРОВЕРЬТЕ ВАШИ ДАННЫЕ:**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 **ФИО:** {data.get('name')}\n"
        f"📞 **Связь:** {data.get('contact')}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Если всё верно — подтвердите оферту."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📜 Читать оферту", url=OFFER_LINK)],
            [InlineKeyboardButton(text="✅ Все верно, согласен", callback_data="confirm_ok")],
            [InlineKeyboardButton(text="❌ Заполнить заново", callback_data="restart")],
        ]
    )
    await message.answer(summary, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Registration.confirm_data)


@dp.callback_query(F.data == "restart")
async def restart_form(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_form(callback.message, state)


@dp.callback_query(F.data == "confirm_ok", Registration.confirm_data)
async def process_confirm(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    pay_text = (
        "✅ **ДАННЫЕ ПРИНЯТЫ**\n\n"
        "Для бронирования места переведите депозит **5000 руб.**\n\n"
        "📌 **Реквизиты:**\n"
        "`+79124591439` (Сбер / Т-Банк)\n"
        "👤 Получатель: Екатерина Б.\n\n"
        "📎 **После оплаты пришлите скриншот чека сюда.**"
    )
    await callback.message.edit_text(pay_text, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_payment_proof)


@dp.message(Registration.waiting_for_payment_proof, F.photo | F.document)
async def process_payment_proof(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    admin_report = (
        "🔥 <b>НОВАЯ ЗАЯВКА НА ИГРУ!!!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>ФИО:</b> {user_data.get('name')}\n"
        f"📞 <b>Связь:</b> {user_data.get('contact')}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"🔗 Профиль: {message.from_user.mention_html()}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_report, parse_mode="HTML")
            await message.copy_to(ADMIN_ID)
        except Exception as e:
            logging.error(f"Ошибка отправки админу: {e}")

    await message.answer(
        "✨ **БЛАГОДАРИМ!**\n\nВаша бронь принята. Мы свяжемся с вами в ближайшее время.",
        reply_markup=get_start_kb(),
        parse_mode="Markdown",
    )
    await state.clear()


# --- ВЕБ-СЕРВЕР (ДЛЯ RENDER) ---

# Простая функция, которая отвечает на запросы (нужна для keep-alive)
async def handle_health_check(request):
    return web.Response(text="Bot is alive")


async def start_web_server():
    """Запускает aiohttp сервер в фоне."""
    app = web.Application()
    app.router.add_get("/", handle_health_check)  # Роут для ping-запросов
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Слушаем на всех интерфейсах (0.0.0.0) и порту PORT
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")


# --- ЗАПУСК ---
async def main():
    # Удаляем вебхук, если был, и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(
        [BotCommand(command="start", description="Начать")]
    )

    # Запускаем и бота, и веб-сервер параллельно
    # start_web_server запустится и будет работать в фоне,
    # а start_polling заблокирует выполнение, пока бот работает.
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server(),
    )


if __name__ == "__main__":
    try:
        logging.info("Starting bot...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
