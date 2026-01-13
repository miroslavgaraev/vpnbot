import telebot
from telebot import types
import requests
import time
import json

# Токен бота (замени на свой)
TOKEN = '8576212987:AAFLdEqQBHoqARtMZoWEL00Oz9dWcuVEqYg'

# Токен ЮKassa (получи через @BotFather -> Payments -> ЮKassa)
YOOKASSA_TOKEN = '381764678:TEST:160239'  # Формат: 381764678:TEST:100037
ADMIN_IDS = [1000649034, 1835304379]


MARZBAN_URL = "https://zalupatigra.duckdns.org:8000"  # без / в конце
MARZBAN_ADMIN_USERNAME = "root"
MARZBAN_ADMIN_PASSWORD = "toor"



bot = telebot.TeleBot(TOKEN)

# Цены на тарифы (в рублях)
PRICES = {
    '1-month': {'price': 150, 'title': '1 месяц', 'description': 'VoidLink VPN на 1 месяц'},
    '2-months': {'price': 250, 'title': '2 месяца', 'description': 'VoidLink VPN на 2 месяца'},
    '4-months': {'price': 400, 'title': '4 месяца', 'description': 'VoidLink VPN на 4 месяца'},
    '6-months': {'price': 500, 'title': '6 месяцев', 'description': 'VoidLink VPN на 6 месяцев'}
}


def get_marzban_token():
    url = f"{MARZBAN_URL}/api/admin/token"
    
    # ВАЖНО: form-data (x-www-form-urlencoded), grant_type=password
    data = {
        "grant_type": "password",
        "username": MARZBAN_ADMIN_USERNAME,
        "password": MARZBAN_ADMIN_PASSWORD,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    resp = requests.post(url, data=data, headers=headers, timeout=10, verify=False)
    print("TOKEN STATUS:", resp.status_code, resp.text)  # для отладки
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_marzban_user(username: str, days: int = 30,) -> str:
    token = get_marzban_token()
    url = f"{MARZBAN_URL}/api/user"

    expire = None
    if days > 0:
        # Marzban ждёт expire как UTC timestamp (секунды) [web:107]
        import time, datetime
        expire_dt = datetime.datetime.utcnow() + datetime.timedelta(days=days)
        expire = int(expire_dt.timestamp())

    body = {
        "username": username,
        "proxies": {
            "vless": {}  # пустой объект → Marzban сам сгенерит uuid/пароль [web:108]
        },
        "expire": expire,
        "status": "active",
        "inbounds": {
        "vless": ["VLESS TCP REALITY"]  # ← ID или имя твоего инбаунда
    },
    }

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(url, json=body, headers=headers, timeout=10)
    resp.raise_for_status()


    url = f"{MARZBAN_URL}/api/user/{username}"
    resp = requests.get(url, headers=headers, timeout=10, verify=False)
    resp.raise_for_status()
    data = resp.json()


    # В ответе обычно есть links и/или subscription_url [web:107]
    return data




@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""

    welcome_text = """
👋 Добро пожаловать в <b>VoidLink</b>, пользователь!

💨 Высокая скорость
👾 Доступ ко всем сайтам
🗓️ Неделя бесплатно!

👫 Пригласите друзей в наш сервис!

📌 <b>Обязательно (!!)</b>
Подпишитесь на наш канал

⚡️ Подключение мгновенное после оплаты!
    """

    # Создание клавиатуры с кнопками
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    btn_buy = types.InlineKeyboardButton(
        text="💳 Купить VPN",
        callback_data="show_tariffs"
    )
   
    btn_support = types.InlineKeyboardButton(
        text="💬 Поддержка",
        url="https://t.me/suppVoidLink"
    )
    btn_channel = types.InlineKeyboardButton(
        text="📱 Наш канал",
        url="https://t.me/voidlinkvpn"
    )
    btn_legal_offer = types.InlineKeyboardButton(
        text="📜 Договор оферты",
        url="https://telegra.ph/Dogovor-oferty-01-09-4"  
    )
    btn_legal_policy = types.InlineKeyboardButton(
        text="🔒 Политика конфиденциальности",
        url="https://telegra.ph/Politika-konfidencialnosti-01-09-56" 
    )

    keyboard.add(btn_buy)
    keyboard.add(btn_support)
    keyboard.add(btn_channel)
    keyboard.add(btn_legal_offer)
    keyboard.add(btn_legal_policy)

    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == 'show_tariffs')
def show_tariffs(call):
    """Показать тарифы для выбора"""

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    for key, value in PRICES.items():
        btn = types.InlineKeyboardButton(
            text=f"💎 {value['title']} - {value['price']}₽",
            callback_data=f"buy_{key}"
        )
        keyboard.add(btn)

    btn_back = types.InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="back_to_start"
    )
    keyboard.add(btn_back)

    bot.edit_message_text(
        "💳 <b>Выберите тариф:</b>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_payment(call):
    """Создание платежа"""

    tariff = call.data.replace('buy_', '')

    if tariff not in PRICES:
        bot.answer_callback_query(call.id, "❌ Ошибка выбора тарифа")
        return

    price_info = PRICES[tariff]

    # Создание счета для оплаты
    prices = [types.LabeledPrice(
        label=price_info['title'],
        amount=price_info['price'] * 100  # Цена в копейках!
    )]

    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"VoidLink - {price_info['title']}",
        description=price_info['description'],
        invoice_payload=f"{tariff}_{call.from_user.id}",  # Полезная нагрузка для идентификации
        provider_token=YOOKASSA_TOKEN,
        currency='RUB',
        prices=prices,
        start_parameter='servers-payment',
    )

    bot.answer_callback_query(call.id, "✅ Счет создан!")

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    """Обработка перед оплатой"""

    bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True
    )

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    """Обработка успешной оплаты"""

    VLESS_TEMPLATE = (
    "vless://{uuid}@150.241.80.64:443"
    "?security=reality&type=tcp&headerType=&path=&host="
    "&sni=github.com&fp=chrome"
    "&pbk=x2J3YWBFpEnYr_EMxYXxvfVw57gsyjTEIkTBW8lcTQ8"
    "&sid=3ab57f27db18f735"
    "#🚀 VoidLink ({label}) [VLESS - tcp]"
)


    payment_info = message.successful_payment
    print("INVOICE PAYLOAD:", payment_info.invoice_payload)

    # Извлекаем информацию о платеже
    tariff_key = payment_info.invoice_payload.split('_')[0]
    print("TARIFF KEY:", tariff_key)
    amount = payment_info.total_amount / 100



    username = f"user_{message.from_user.id}_{int(time.time())}"

    # подбираем срок по тарифу
    days_map = {
        "1-month": 30,
        "2-months": 60,
        "4-months": 120,
        "6-months": 180,
    }
    days = days_map.get(tariff_key, 30)
    user = create_marzban_user(username, days=days)
    
    uuid = user["proxies"]["vless"]["id"]
    try:
        vless_link = VLESS_TEMPLATE.format(
    uuid=uuid,
    label=username  # или что ты хочешь в названии
)
    except Exception as e:
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при выдаче ключа. Напишите в поддержку: @suppVoidLink",
        )
        print("MARZBAN ERROR:", e)
        return


    success_text = f"""
✅ <b>Оплата прошла успешно!</b>

💎 Тариф: {PRICES[tariff_key]['title']}
💰 Сумма: {amount}₽

⚡️ Ваш VPN-ключ:

<code>{vless_link}</code>


💬 Возникли вопросы? Пишите в поддержку
    """

    keyboard = types.InlineKeyboardMarkup()
    btn_support = types.InlineKeyboardButton(
        text="💬 Поддержка",
        url="https://t.me/suppVoidLink"
    )
    btn_guide = types.InlineKeyboardButton(
        text="📱 Инструкция по подключению",
        url="https://telegra.ph/Gajd-na-podklyuchenie-Void-Link-11-27"
    )
    keyboard.add(btn_support)
    keyboard.add(btn_guide)

    bot.send_message(
        message.chat.id,
        success_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )
    for admin_id in ADMIN_IDS:
        bot.send_message(
        admin_id,
        f"✅ Новая оплата: User {message.from_user.id}, тариф {tariff_key}, сумма {amount}₽",
        parse_mode='HTML',)

    # Здесь можно добавить логику:
    # - Генерацию реального VPN-ключа
    # - Сохранение в базу данных
    # - Отправку уведомления админу
    print(f"✅ Новая оплата: User {message.from_user.id}, тариф {tariff_key}, сумма {amount}₽")

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_start')
def back_to_start(call):
    """Вернуться в начало"""

    welcome_text = """
👋 Добро пожаловать в <b>VoidLink</b>, пользователь!

💨 Высокая скорость
👾 Доступ ко всем сайтам
🗓️ Неделя бесплатно!

👫 Пригласите друзей в наш сервис!

📌 <b>Обязательно (!!)</b>
Подпишитесь на наш канал

⚡️ Подключение мгновенное после оплаты!
    """

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    btn_buy = types.InlineKeyboardButton(
        text="💳 Купить VPN",
        callback_data="show_tariffs"
    )

    btn_support = types.InlineKeyboardButton(
        text="💬 Поддержка",
        url="https://t.me/voidlinkvpn"
    )
    btn_channel = types.InlineKeyboardButton(
        text="📱 Наш канал",
        url="https://t.me/voidlinkvpn"
    )

    keyboard.add(btn_buy)
    keyboard.add(btn_support)
    keyboard.add(btn_channel)

    bot.edit_message_text(
        welcome_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )


@bot.message_handler(commands=['notify_expiry'])
def notify_expiry(message):
    # Проверка админа
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Доступ запрещён")
        return
    
    try:
        # /notify_expiry user_id тариф
        parts = message.text.split()
        user_id = int(parts[1])
        tariff = "подписка" if len(parts) < 3 else " ".join(parts[2:])

        text = f"""
❌ <b> Ваша подписка на {tariff} закончилась!</b>

🔄 Вы можете продлить доступ, выбрав тариф ниже.
        """

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        btn_renew = types.InlineKeyboardButton(
            text="🔄 Продлить подписку",
            callback_data="show_tariffs"  # та же коллбэк-данные, что и в твоей кнопке "Купить VPN"
        )
        btn_support = types.InlineKeyboardButton(
            text="💬 Поддержка",
            url="https://t.me/suppVoidLink"
        )
        keyboard.add(btn_renew)
        keyboard.add(btn_support)

        bot.send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)
        bot.reply_to(message, f"✅ Уведомление отправлено user {user_id}")

    except Exception as e:
        bot.reply_to(message, "❌ Используй: /notify_expiry 123456789 1 месяц")

# Запуск бота
if __name__ == '__main__':
    print("🚀 Бот запущен и работает!")
    print("💳 Платежи через ЮKassa подключены!")
    bot.infinity_polling()
