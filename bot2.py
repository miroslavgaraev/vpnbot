import telebot
from telebot import types

# Токен бота
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

    # Создаем инлайн-клавиатуру
    markup = types.InlineKeyboardMarkup()
    
    # Создаем саму кнопку. 
    # callback_data — это скрытый триггер. Когда пользователь нажмет кнопку, 
    # бот получит сигнал 'connect' и сможет на него отреагировать.
    btn_connect = types.InlineKeyboardButton(text="⚡️ Подключить", callback_data='connect')
    
    # Добавляем кнопку в клавиатуру
    markup.add(btn_connect)

    # Отправка сообщения вместе с кнопкой (reply_markup=markup)
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML',
        reply_markup=markup
    )

# (Опционально) Обработчик нажатия на кнопку
@bot.callback_query_handler(func=lambda call: call.data == 'connect')
def callback_connect(call):
    """Этот код сработает, когда пользователь нажмет кнопку 'Подключить'"""
    # Всплывающее уведомление в Telegram
    bot.answer_callback_query(call.id, text="Запрос на подключение принят!")
    
    # Отправляем новое сообщение (например, ссылку на оплату или инструкцию)
    bot.send_message(call.message.chat.id, "Отлично! Для оплаты перейдите по ссылке: ссылка на юкассу")

# Запуск бота
if __name__ == '__main__':
    print("🚀 Бот запущен и работает!")
    bot.infinity_polling()