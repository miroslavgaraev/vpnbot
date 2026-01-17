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
            "ref_free_keys": 0,            # сразу добавим поле из п.3 (чтобы не делать потом ещё раз)
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
        url="https://telegra.ph/Gajd-na-podklyuchenie-Void-Link-11-27"
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

    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )


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

    bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
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
    

    bot.edit_message_text(
        "Выберите действие:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
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
    free_keys = users[uid].get("ref_free_keys", 0)

    text = (
        f"Ваш ID: <code>{uid}</code>\n\n"
        "Если человек введет его при покупке любого из тарифов, "
        "то вам будут начислены бесплатные 14 дней.\n\n"
        f"Бесплатных ключей за приведенных людей: {free_keys}"
    )

    keyboard = types.InlineKeyboardMarkup()
    btn_get_key = types.InlineKeyboardButton(
        text="🗝 Получить бесплатный ключ",
        callback_data="ref_get_key"
    )
    btn_back = types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="promo_trial_menu"
    )
    keyboard.add(btn_get_key)
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

    free_keys = users[uid].get("ref_free_keys", 0)

    if free_keys <= 0:
        bot.answer_callback_query(call.id, "❌ У вас нет бесплатных ключей")
        bot.send_message(
            call.message.chat.id,
            "❌ У вас нет бесплатных ключей за приведенных людей."
        )
        return

    # уменьшаем счётчик
    users[uid]["ref_free_keys"] = free_keys - 1
    save_users_data(users)

    # выдаем VPN-ключ как бонус на 14 дней (или другое кол-во дней)
    give_vpn_access(user.id, 14, "бесплатный ключ за реферала")
    users = get_users_data()
    free_keys_after = users[uid].get("ref_free_keys", 0)

    # собираем новый текст и клавиатуру, как в ref_system
    text = (
        f"Ваш ID: <code>{uid}</code>\n\n"
        "Если человек введет его при покупке любого из тарифов, "
        "то вам будут начислены бесплатные 14 дней.\n\n"
        f"Бесплатных ключей за приведенных людей: {free_keys_after}"
    )

    keyboard = types.InlineKeyboardMarkup()
    btn_get_key = types.InlineKeyboardButton(
        text="🗝 Получить бесплатный ключ",
        callback_data="ref_get_key"
    )
    btn_back = types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="promo_trial_menu"
    )
    keyboard.add(btn_get_key)
    keyboard.add(btn_back)

    # обновляем то же сообщение, по которому нажата кнопка
    try:
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        print("Ошибка обновления сообщения реферального меню:", e)

    bot.answer_callback_query(call.id, "✅ Бесплатный ключ выдан")




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
    """Шаг 1: выбор тарифа и вопрос про реферальный ID"""

    tariff = call.data.replace('buy_', '')

    if tariff not in PRICES:
        bot.answer_callback_query(call.id, "❌ Неизвестный тариф")
        return

    # сохраним выбранный тариф во временное поле message (хак)
    msg = bot.send_message(
        call.message.chat.id,
        "Вы хотите ввести ID человека, который вас привёл? Он получит бесплатные 14 дней.\n\n"
        "Если да, отправьте его ID в следующем сообщении.\n"
        "Если нет — отправьте 0."
    )
    bot.register_next_step_handler(msg, partial(process_referral_step, tariff=tariff))
def process_referral_step(message, tariff):
    """Шаг 2: обработка введённого реферального ID и создание счёта"""

    user_id = message.from_user.id
    uid = str(user_id)

    # достаём тариф, выбранный на предыдущем шаге
    print(tariff)
    if not tariff or tariff not in PRICES:
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, выберите тариф заново.")
        return

    text = message.text.strip()

    # пытаемся разобрать ID
    try:
        ref_id = int(text)
    except ValueError:
        bot.send_message(message.chat.id, "ID должен быть числом. Отправьте команду /start и выберите тариф заново.")
        return

    referrer_id = None
    if ref_id != 0:
        # нельзя указать самого себя
        if ref_id == user_id:
            bot.send_message(message.chat.id, "❌ Нельзя указывать свой собственный ID. Попробуйте снова.")
            # повторный запрос
            msg = bot.send_message(
                message.chat.id,
                "Введите ID пригласившего или 0, если без реферала:"
            )
            msg._tariff_key = tariff
            bot.register_next_step_handler(msg, process_referral_step)
            return

        # проверяем, что такой пользователь существует в users_data.json
        users = get_users_data()
        if str(ref_id) not in users:
            bot.send_message(message.chat.id, "❌ Пользователь с таким ID не найден. Введите ID ещё раз или 0, если без реферала.")
            msg = bot.send_message(
                message.chat.id,
                "Введите ID пригласившего или 0, если без реферала:"
            )
            msg._tariff_key = tariff
            bot.register_next_step_handler(msg, process_referral_step)
            return

        referrer_id = ref_id

    # если дошли сюда — ID валиден (или 0)
    pending_referrer_by_user[uid] = referrer_id

    price_info = PRICES[tariff]

    prices = [types.LabeledPrice(
        label=price_info['title'],
        amount=price_info['price'] * 100  # Цена в копейках!
    )]

    bot.send_invoice(
        chat_id=message.chat.id,
        title=f"VoidLink - {price_info['title']}",
        description=price_info['description'],
        invoice_payload=f"{tariff}_{user_id}",  # как и было
        provider_token=YOOKASSA_TOKEN,
        currency='RUB',
        prices=prices,
        start_parameter='servers-payment',
    )

    bot.send_message(message.chat.id, "✅ Счёт создан! Оплатите его через встроенную форму.")


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
        referrer_id = pending_referrer_by_user.pop(uid, None)
        if referrer_id:
            ref_uid = str(referrer_id)
            if ref_uid in users:
                current = users[ref_uid].get("ref_free_keys", 0)
                users[ref_uid]["ref_free_keys"] = current + 1
                bot.send_message(
                    referrer_id,
                    "🎉 Вам начислен новый бесплатный ключ за приглашённого пользователя!\n"
                    "Зайдите в раздел «Бонусы» → «Реферальная система», чтобы активировать его."
            )

        save_users_data(users)


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
    btn_legal = types.InlineKeyboardButton(
    text="📄 Юр. информация",
    callback_data="legal_info"
    )
    btn_promo_trial = types.InlineKeyboardButton(
        text="🎁 Промокод / пробный период",
        callback_data="promo_trial_menu"
    )

    keyboard.add(btn_buy)
    keyboard.add(btn_support)
    keyboard.add(btn_channel)
    keyboard.add(btn_legal)
    keyboard.add(btn_promo_trial)

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
