import telebot
from telebot import types

# Токен бота (замени на свой)
TOKEN = '8576731269:AAGapz9nZM5RfTTTvWnq16jt6po_VdUs81Y'

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""

    welcome_text = """
🔐 <b>VoidLink Servers - Надежные сервера для вас</b>

🚀 <b>Что вы получаете:</b>

• Стабильное соединение 24/7
• Много памяти

💎 <b>Тарифы:</b>

1 месяц - 200₽


⚡️ Подключение мгновенное после оплаты!


    """

    

    # Отправка сообщения
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML'
    )

# Запуск бота
if __name__ == '__main__':
    print("🚀 Бот запущен и работает!")
    bot.infinity_polling()