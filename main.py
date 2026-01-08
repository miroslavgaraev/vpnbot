import telebot
from telebot import types

# Токен бота (замени на свой)
TOKEN = '8576212987:AAFLdEqQBHoqARtMZoWEL00Oz9dWcuVEqYg'

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""

    # Текст приветствия с информацией о VPN
    welcome_text = """
🔐 <b>VoidLink VPN - Надежная защита вашего интернета</b>

🚀 <b>Что вы получаете:</b>

• Высокая скорость подключения
• Неограниченный трафик
• Защита личных данных
• Обход блокировок
• Стабильное соединение 24/7
• Поддержка всех устройств

💎 <b>Тарифы:</b>

1 месяц - 200₽


⚡️ Подключение мгновенное после оплаты!

🛒 <b>Оплата:</b>
Пока покупка происходит только через FunPay
    """

    # Создание клавиатуры с кнопками
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    btn_buy = types.InlineKeyboardButton(
        text="🛍 Купить на FunPay",
        url="https://funpay.com/lots/offer?id=61621013"
    )
    btn_support = types.InlineKeyboardButton(
        text="💬 Поддержка",
        url="https://t.me/Sefdorrr"
    )
    btn_channel = types.InlineKeyboardButton(
        text="📱 Наш канал",
        url="https://t.me/voidlinkvpn"
    )

    keyboard.add(btn_buy)
    keyboard.add(btn_support)
    keyboard.add(btn_channel)

    # Отправка сообщения
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

# Запуск бота
if __name__ == '__main__':
    print("🚀 Бот запущен и работает!")
    bot.infinity_polling()