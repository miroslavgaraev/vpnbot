import telebot
from telebot import types
import requests
import time
import json
import os
from datetime import datetime, timedelta, timezone
from functools import partial 


BOT_TOKEN = os.getenv("BOT_TOKEN")
YOOKASSA_TOKEN = os.getenv("YOOKASSA_TOKEN")
MARZBAN_URL = os.getenv("MARZBAN_URL")

ADMIN_IDS = [1000649034, 1835304379]

DATA_FILE = "data/users_data.json"
PROMOCODES_FILE = "data/promocodes.json"

MARZBAN_ADMIN_USERNAME = "root"
MARZBAN_ADMIN_PASSWORD = "toor"



bot = telebot.TeleBot(BOT_TOKEN)

# Цены на тарифы (в рублях)
PRICES = {
    '1-month': {'price': 150, 'title': '1 месяц', 'description': 'VoidLink VPN на 1 месяц'},
    '2-months': {'price': 250, 'title': '2 месяца', 'description': 'VoidLink VPN на 2 месяца'},
    '4-months': {'price': 400, 'title': '4 месяца', 'description': 'VoidLink VPN на 4 месяца'},
    '6-months': {'price': 500, 'title': '6 месяцев', 'description': 'VoidLink VPN на 6 месяцев'},
}

pending_referrer_by_user = {}

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_users_data():
    return load_json(DATA_FILE, {})


def save_users_data(data):
    save_json(DATA_FILE, data)


def get_promocodes():
    # пример: {"MELL": {"days": 14, "active": True}}
    return load_json(PROMOCODES_FILE, {
        "MELL": {"days": 14, "active": True}
    })


def save_promocodes(data):
    save_json(PROMOCODES_FILE, data)

def get_or_create_user(user):
    users = get_users_data()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "telegram_username": user.username,
            "trial_used": False,
            "promo_used": [],
            "tariff_expire": "",           # новое поле
            "ref_free_keys": 0,
            "balance": 0.0,  
            "referred_by": None,
            "ref_bonus_paid": False,                      
        }
        save_users_data(users)
    else:
        changed = False
        if users[uid].get("telegram_username") != user.username:
            users[uid]["telegram_username"] = user.username
            changed = True
        if "tariff_expire" not in users[uid]:
            users[uid]["tariff_expire"] = ""
            changed = True
        if "ref_free_keys" not in users[uid]:
            users[uid]["ref_free_keys"] = 0
            changed = True
        if changed:
            save_users_data(users)
    return users[uid]


def process_promo_input(message):
    code = message.text.strip().upper()

    promocodes = get_promocodes()
    if code not in promocodes or not promocodes[code].get("active", True):
        bot.send_message(message.chat.id, "❌ Неверный или неактивный промокод")
        return

    user = message.from_user
    user_record = get_or_create_user(user)
    uid = str(user.id)

    used_codes = user_record.get("promo_used", [])

    if code in used_codes:
        bot.send_message(message.chat.id, "❌ Этот промокод уже был активирован на вашем аккаунте")
        return

    days = int(promocodes[code].get("days", 14))
    user_id = message.from_user.id
    give_vpn_access(user_id, days, f"промокод {code}")

    users = get_users_data()
    users[uid]["promo_used"].append(code)
    save_users_data(users)

    bot.send_message(
        message.chat.id,
        f"✅ Промокод {code} активирован. Доступ выдан на {days} дней."
    )



def give_vpn_access(user_id: int, days: int, reason: str):
    VLESS_TEMPLATE = (
    "vless://{uuid}@150.241.80.64:443"
    "?security=reality&type=tcp&headerType=&path=&host="
    "&sni=github.com&fp=chrome"
    "&pbk=x2J3YWBFpEnYr_EMxYXxvfVw57gsyjTEIkTBW8lcTQ8"
    "&sid=3ab57f27db18f735"
    "#🚀 VoidLink ({label}) [VLESS - tcp]"
)

    username = f"{user_id}_{int(time.time())}"

    # подбираем срок по тарифу
    user = create_marzban_user(username, days=days)
    
    uuid = user["proxies"]["vless"]["id"]
    try:
        vless_link = VLESS_TEMPLATE.format(
    uuid=uuid,
    label=username.split('_')[0]  # или что ты хочешь в названии
)
    except Exception as e:
        bot.send_message(
            user_id,
            "❌ Ошибка при выдаче ключа. Напишите в поддержку: @suppVoidLink",
        )
        print("MARZBAN ERROR:", e)
        return

    success_text = f"""
✅ Доступ к VPN выдан ({reason})
Срок: {days} дней

Ваш ключ:

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
        url="https://telegra.ph/Gajd-na-podklyuchenie-k-VoidLink-02-01"
    )

    keyboard.add(btn_support)
    keyboard.add(btn_guide)

    bot.send_message(
        user_id,
        success_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

    for admin_id in ADMIN_IDS:
        bot.send_message(
            admin_id,
            f"✅ Новая выдача доступа: User {user_id}, причина: {reason}, срок {days} дней",
            parse_mode='HTML',
        )

    print(f"✅ Новая выдача: User {user_id}, причина {reason}, срок {days} дней")
    # --------- КОНЕЦ: твой существующий код ---------




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
    user_id = str(message.from_user.id)
    user_record = get_or_create_user(message.from_user)
    
    # Проверяем, есть ли в команде /start ID пригласившего
    args = message.text.split()
    if len(args) > 1:
        referrer_id = args[1]
        users = get_users_data()
        
        # Если пользователь новый и не сам себя пригласил
        if users[user_id].get("referred_by") is None and referrer_id != user_id:
            if referrer_id in users:
                users[user_id]["referred_by"] = referrer_id
                save_users_data(users)
                bot.send_message(user_id, "🎁 Вы перешли по реферальной ссылке!")
    

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
    btn_promo_trial = types.InlineKeyboardButton(
        text="🎁 Бонусы",
        callback_data="promo_trial_menu"
    )
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
    btn_legal = types.InlineKeyboardButton(
    text="📄 Юр. информация",
    callback_data="legal_info"
    )


    keyboard.add(btn_buy)
    keyboard.add(btn_support)
    keyboard.add(btn_channel)
    keyboard.add(btn_legal)
    keyboard.add(btn_promo_trial)

    with open('banner.jpg', 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=welcome_text, parse_mode='HTML', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data == "legal_info")
def legal_info(call):
    text = (
        "Продолжая пользоваться нашим ботом, вы соглашаетесь с нашей "
        "политикой конфиденциальности и договором оферты."
    )

    keyboard = types.InlineKeyboardMarkup()
    btn_policy = types.InlineKeyboardButton(
        text="🔐 Политика конфиденциальности",
        url="https://telegra.ph/Politika-konfidencialnosti-01-09-56"  # поставь реальные ссылки
    )
    btn_offer = types.InlineKeyboardButton(
        text="📃 Договор оферты",
        url="https://telegra.ph/Dogovor-oferty-01-09-4"
    )
    btn_back = types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_start"
    )

    keyboard.add(btn_policy)
    keyboard.add(btn_offer)
    keyboard.add(btn_back)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"Ошибка удаления: {e}")
    bot.send_message(
        call.message.chat.id,
        text,
        reply_markup=keyboard
    )




@bot.callback_query_handler(func=lambda call: call.data == "promo_trial_menu")
def promo_trial_menu(call):
    keyboard = types.InlineKeyboardMarkup()

    btn_free_trial = types.InlineKeyboardButton(
        text="🎁 Бесплатный пробный период",
        callback_data="promo_free_trial"
    )
    btn_enter_promo = types.InlineKeyboardButton(
        text="🏷 Ввести промокод",
        callback_data="promo_enter"
    )
    btn_referral = types.InlineKeyboardButton(
        text="👥 Реферальная система",
        callback_data="ref_system"
    )
    btn_back = types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_start"
    )

    keyboard.add(btn_free_trial)
    keyboard.add(btn_enter_promo)
    keyboard.add(btn_referral)
    keyboard.add(btn_back)
    

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    bot.send_message(
        call.message.chat.id,
        "Выберите дейтсвие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "promo_free_trial")
def handle_free_trial(call):
    user = call.from_user
    user_record = get_or_create_user(user)

    if user_record.get("trial_used"):
        bot.answer_callback_query(call.id, "❌ Пробный период уже использован")
        bot.send_message(
            call.message.chat.id,
            "❌ Вы уже активировали бесплатный период. Выберите платный тариф."
        )
        return

    users = get_users_data()
    uid = str(user.id)
    users[uid]["trial_used"] = True
    save_users_data(users)
    
    give_vpn_access(user.id, 3, "бесплатный пробный период 3 дня")

    bot.answer_callback_query(call.id, "✅ Бесплатный доступ выдан на 3 дня")

@bot.callback_query_handler(func=lambda call: call.data == "promo_enter")
def promo_enter(call):
    msg = bot.send_message(
        call.message.chat.id,
        "Введите промокод:"
    )
    bot.register_next_step_handler(msg, process_promo_input)

@bot.callback_query_handler(func=lambda call: call.data == "ref_system")
def ref_system(call):
    user = call.from_user
    user_record = get_or_create_user(user)
    uid = str(user.id)
    users = get_users_data()
    balance = users[uid].get("balance", 0)
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={uid}"

    text = (
        f"👥 <b>Реферальная система</b>\n\n"
        f"Ваш баланс: <b>{balance} руб.</b>\n"
        f"Для вывода средств напишите нашему саппорту, либо обменяйте 100р на месяц нашего VPN\n"
        f"Ваша доля: <b>60%</b> от каждой покупки друга\n\n"
        f"Ваша ссылка для приглашения:\n<code>{ref_link}</code>"
    )

    

    keyboard = types.InlineKeyboardMarkup()
    btn_support = types.InlineKeyboardButton(
        text="💸 Вывести деньги",
        url="https://t.me/suppVoidLink"
    )
    btn_get_key = types.InlineKeyboardButton(
        text="🗝 Обменять 100р на подписку",
        callback_data="ref_get_key"
    )
    btn_back = types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="promo_trial_menu"
    )
    keyboard.add(btn_get_key)
    keyboard.add(btn_support)
    keyboard.add(btn_back)

    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard
    )
@bot.callback_query_handler(func=lambda call: call.data == "ref_get_key")
def ref_get_key(call):
    user = call.from_user
    uid = str(user.id)
    users = get_users_data()
    user_record = get_or_create_user(user)
    balance = users[uid].get("balance", 0.0)
    exchange_cost = 100.0  # Цена обмена

    if balance < exchange_cost:
        bot.answer_callback_query(call.id, f"❌ Недостаточно средств (нужно {exchange_cost} руб.)", show_alert=True)
        return
    users[uid]["balance"] = round(balance - exchange_cost, 2)
    save_users_data(users)
    # Выдаем 30 дней (месяц)
    give_vpn_access(call.from_user.id, 30, "обмен баланса на 1 месяц")

    bot.answer_callback_query(call.id, "✅ Успешно! Вам начислен 1 месяц VPN.", show_alert=True)
    
    # Сразу обновляем текст меню рефералки, чтобы увидеть новый баланс
    ref_system(call)




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

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    bot.send_message(
        call.message.chat.id,
        "Выберите подходящий тариф:",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_payment(call):
    tariff = call.data.replace('buy_', '')

    if tariff not in PRICES:
        bot.answer_callback_query(call.id, "❌ Неизвестный тариф")
        return

    price_info = PRICES[tariff]
    user_id = call.from_user.id

    prices = [types.LabeledPrice(
        label=price_info['title'],
        amount=price_info['price'] * 100  # Копейки
    )]

    # Удаляем старое меню с тарифами
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"VoidLink - {price_info['title']}",
        description=price_info['description'],
        invoice_payload=f"{tariff}_{user_id}",
        provider_token=YOOKASSA_TOKEN,
        currency='RUB',
        prices=prices,
        start_parameter='servers-payment',
    )
    bot.send_message(call.message.chat.id, "✅ Счёт создан! Оплатите его через встроенную форму.")


@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    """Обработка перед оплатой"""

    bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True
    )

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    payment_info = message.successful_payment
    tariff_key = payment_info.invoice_payload.split('_')[0]
    total_amount = payment_info.total_amount / 100
    days_map = {
        "1-month": 30,
        "2-months": 60,
        "4-months": 120,
        "6-months": 180,
    }
    days = days_map.get(tariff_key)

    # получаем/создаём запись пользователя
    user_record = get_or_create_user(message.from_user)
    uid_int = message.from_user.id  # int
    uid = str(uid_int)
    users = get_users_data()

    if days:
        give_vpn_access(uid_int, days, f'подписка {days} дней')

        expire_dt = datetime.now(timezone.utc) + timedelta(days=days)
        users[uid]["tariff_expire"] = expire_dt.isoformat()

        # реферальный бонус
        referrer_id = users[uid].get("referred_by")
        if referrer_id and not users[uid].get("ref_bonus_paid", False):
            ref_uid = str(referrer_id)
            if ref_uid in users:
                reward = round(total_amount * 0.6, 2)  # Считаем 60%
                users[str(referrer_id)]["balance"] = users[str(referrer_id)].get("balance", 0.0) + reward
                users[uid]["ref_bonus_paid"] = True
                bot.send_message(
                    referrer_id,
                    f"💰 Вам начислено <b>{reward} руб.</b> за покупку вашего реферала!\n"
                    f"Проверить баланс можно в разделе «Бонусы».",
                    parse_mode="HTML"
            )

        save_users_data(users)


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_start')
def back_to_start(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    # Вызываем функцию start, которую мы изменили в предыдущем шаге
    start(call.message)


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
