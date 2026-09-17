#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import re
import telebot
from telebot import types
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from flask import Flask
from threading import Thread
from supabase import create_client

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

print("[DEBUG] Токен: " + str(len(BOT_TOKEN)) + " знаков")
print("[DEBUG] Supabase URL: " + str(len(SUPABASE_URL)) + " знаков")
print("[DEBUG] Supabase KEY: " + str(len(SUPABASE_KEY)) + " знаков")

BG_COLOR = "#0a0a0a"
NODE_FACE = "#0a0a0a"
BORDER_WHITE = "#ffffff"
BORDER_RED = "#e74c3c"
TEXT_COLOR = "#ffffff"

# ============ FLASK ============
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/health")
def health():
    return "OK"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============ SUPABASE ============
sb = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[+] Supabase подключён")
    except Exception as e:
        print("[ERROR] Supabase: " + str(e))
else:
    print("[ERROR] Нет SUPABASE_URL или SUPABASE_KEY")

# ============ БОТ ============
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# ============ ТАРИФЫ ============
TARIFFS = {
    "1day":   {"days": 1,   "stars": 15,  "label": "1 день"},
    "3days":  {"days": 3,   "stars": 25,  "label": "3 дня"},
    "week":   {"days": 7,   "stars": 50,  "label": "Неделя"},
    "month":  {"days": 30,  "stars": 100, "label": "Месяц"},
    "forever":{"days": 36500,"stars": 200, "label": "Навсегда"},
}


# ============ БАЗА ============
def get_user(user_id):
    try:
        res = sb.table("users").select("*").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        print("[ERROR] get_user: " + str(e))
        return None


def create_user(user_id, username, first_name):
    try:
        sb.table("users").insert({
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
        }).execute()
    except Exception as e:
        print("[ERROR] create_user: " + str(e))


def has_subscription(user_id):
    u = get_user(user_id)
    if not u:
        return False
    until = u.get("subscription_until")
    if not until:
        return False
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


def give_subscription(user_id, days):
    from datetime import datetime, timezone, timedelta
    u = get_user(user_id)
    if not u:
        return
    now = datetime.now(timezone.utc)
    until = u.get("subscription_until")
    base = now
    if until:
        try:
            dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
            if dt > now:
                base = dt
        except Exception:
            pass
    new_until = base + timedelta(days=days)
    try:
        sb.table("users").update({
            "subscription_until": new_until.isoformat()
        }).eq("user_id", user_id).execute()
    except Exception as e:
        print("[ERROR] give_subscription: " + str(e))


def check_key(key):
    try:
        res = sb.table("keys").select("*").eq("key", key).execute()
        if res.data and not res.data[0].get("used_by"):
            return True
        return False
    except Exception:
        return False


def use_key(key, user_id):
    from datetime import datetime, timezone
    try:
        sb.table("keys").update({
            "used_by": user_id,
            "used_at": datetime.now(timezone.utc).isoformat()
        }).eq("key", key).execute()
        return True
    except Exception:
        return False


def log_payment(user_id, stars, days):
    try:
        sb.table("payments").insert({
            "user_id": user_id,
            "amount": stars,
            "days": days,
        }).execute()
    except Exception as e:
        print("[ERROR] log_payment: " + str(e))
      

# ============ МАРКЕРЫ РОДСТВЕННИКОВ ============
ROLE_MARKERS = {
    "мама": "МАМА", "mother": "МАМА", "mom": "МАМА", "mama": "МАМА", "мать": "МАМА",
    "папа": "ПАПА", "father": "ПАПА", "dad": "ПАПА", "papa": "ПАПА", "отец": "ПАПА",
    "брат": "БРАТ", "brother": "БРАТ", "brat": "БРАТ",
    "сестра": "СЕСТРА", "sister": "СЕСТРА", "sestra": "СЕСТРА",
    "сын": "СЫН", "son": "СЫН",
    "дочь": "ДОЧЬ", "daughter": "ДОЧЬ",
    "жена": "ЖЕНА", "wife": "ЖЕНА",
    "муж": "МУЖ", "husband": "МУЖ",
    "бабушка": "БАБУШКА", "grandmother": "БАБУШКА",
    "дедушка": "ДЕДУШКА", "grandfather": "ДЕДУШКА",
}


def detect_field(value):
    """Определяет тип поля по значению."""
    v = value.strip()
    l = v.lower()

    if not v:
        return None

    if re.match(r"^\+?[\d\s\-\(\)]{10,}$", v):
        return "phone"

    if re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$", v):
        return "email"

    if "vk.com" in l or "vk.ru" in l:
        return "vk"

    if "ok.ru" in l:
        return "ok"

    if "wa.me" in l or "whatsapp" in l:
        return "whatsapp"

    if "t.me" in l:
        return "telegram"

    if v.startswith("@") and len(v) < 40:
        return "telegram"

    if "max.ru" in l:
        return "max"

    if re.match(r"^\d{4}\s?\d{6}$", v):
        return "passport"

    if re.match(r"^\d{12}$", v):
        return "inn"

    if re.match(r"^\d{3}-\d{3}-\d{3}\s?\d{2}$", v):
        return "snils"

    if any(w in l for w in ["ул.", "улица", "г.", "город", "обл.", "область", "пр.", "проспект", "д.", "дом", "street", "avenue"]):
        return "address"

    if re.match(r"^\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4}$", v):
        return "dob"

    if re.match(r"^\d{8,12}$", v):
        return "tgid"

    if re.match(r"^[А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z][а-яёa-z]+", v):
        return "name"

    return "other"


def parse_input(text):
    """Парсит входной текст."""
    data = {
        "target": {},
        "relatives": []
    }

    current_relative = None

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines:
        m = re.match(r"^([A-Za-zА-Яа-яЁё]+)\s*[:\-]\s*(.*)$", line)
        if m:
            marker = m.group(1).lower()
            rest = m.group(2).strip()

            if marker in ROLE_MARKERS:
                role_label = ROLE_MARKERS[marker]
                current_relative = {
                    "role": role_label,
                    "data": {}
                }
                data["relatives"].append(current_relative)

                if rest:
                    ftype = detect_field(rest)
                    if ftype:
                        current_relative["data"][ftype] = rest
                continue

        ftype = detect_field(line)
        if not ftype:
            continue

        if current_relative:
            current_relative["data"][ftype] = line
        else:
            data["target"][ftype] = line

    return data


# ============ РЕНДЕР ============
def render_graph(data):
    fig, ax = plt.subplots(figsize=(20, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 10)
    ax.axis("off")

    for x in [i * 0.5 for i in range(41)]:
        for y in [i * 0.5 for i in range(21)]:
            ax.plot(x, y, marker=".", color="#1a1a1a", markersize=1.5, zorder=0)

    def draw_node(x, y, w, h, lines, is_target=False):
        border = BORDER_RED if is_target else BORDER_WHITE
        lw = 2.5 if is_target else 1.2

        box = FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.1",
            linewidth=lw, edgecolor=border, facecolor=NODE_FACE, zorder=2
        )
        ax.add_patch(box)

        for i, line in enumerate(lines):
            color = BORDER_RED if (is_target and i == 0) else TEXT_COLOR
            weight = "bold" if i == 0 else "normal"
            fs = 9 if i == 0 else 8
            ax.text(x, y + h / 2 - 0.25 - i * 0.22, line, ha="center", va="top",
                    color=color, fontsize=fs, fontweight=weight, zorder=3)

    def draw_arrow(x1, y1, x2, y2):
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>", mutation_scale=15,
            linewidth=1.2, color=BORDER_WHITE, zorder=1
        )
        ax.add_patch(arrow)

    t = data["target"]

    tg_user = t.get("telegram", "")
    tg_id = t.get("tgid", "")
    if tg_user or tg_id:
        lines = []
        if tg_user:
            lines.append("ЮЗЕРНЕЙМ ТГ: " + tg_user)
        if tg_id:
            lines.append("АЙДИ ТГ: " + tg_id)
        h = 0.35 + len(lines) * 0.25
        draw_node(1.5, 5.5, 2.5, h, lines, is_target=True)
        draw_arrow(2.75, 5.5, 4.5, 4.5)

    phone = t.get("phone", "")
    if phone:
        draw_node(5, 4.5, 2.5, 0.6, ["НОМЕР ТЕЛЕФОНА", phone], is_target=True)
        socials = []
        if t.get("vk"): socials.append("VK")
        if t.get("ok"): socials.append("OK")
        if t.get("telegram"): socials.append("TG")
        if t.get("whatsapp"): socials.append("WA")
        if t.get("max"): socials.append("MAX")
        if socials:
            draw_node(5, 2.5, 2.5, 0.7, ["СОЦ СЕТИ", ", ".join(socials)], is_target=True)
            draw_arrow(5, 4.2, 5, 2.85)
        name = t.get("name", "")
        dob = t.get("dob", "")
        if name:
            lines = ["ФИО И ДАТА РОЖДЕНИЯ"]
            if name: lines.append(name)
            if dob: lines.append(dob)
            h = 0.35 + len(lines) * 0.25
            draw_node(5, 6.8, 2.8, h, lines, is_target=True)
            draw_arrow(5, 4.8, 5, 6.5)
            docs = []
            if t.get("passport"): docs.append("ПАСПОРТ: " + t["passport"])
            if t.get("snils"): docs.append("СНИЛС: " + t["snils"])
            if t.get("inn"): docs.append("ИНН: " + t["inn"])
            if docs:
                h_d = 0.35 + (len(docs) + 1) * 0.25
                draw_node(5, 8.5, 2.8, h_d, ["ДОКУМЕНТЫ"] + docs, is_target=True)
                draw_arrow(5, 7.2, 5, 8.2)

    rel_y_positions = [7.5, 5.5, 3.5, 1.5]

    for i, rel in enumerate(data["relatives"][:4]):
        rx = 9
        ry = rel_y_positions[i] if i < len(rel_y_positions) else 1.5
        role = rel["role"]
        rdata = rel["data"]

        rname = rdata.get("name", "?")
        rdob = rdata.get("dob", "")
        lines = [role + ": " + rname]
        if rdob:
            lines.append(rdob)
        h = 0.35 + len(lines) * 0.25
        draw_node(rx + 2, ry, 3, h, lines)

        rphone = rdata.get("phone", "")
        if rphone:
            draw_node(rx + 2, ry + 2, 3, 0.6, ["ТЕЛЕФОН", rphone])
            draw_arrow(rx + 2, ry + 0.4, rx + 2, ry + 1.7)

            rdocs = []
            if rdata.get("passport"): rdocs.append("ПАСПОРТ: " + rdata["passport"])
            if rdata.get("snils"): rdocs.append("СНИЛС: " + rdata["snils"])
            if rdata.get("inn"): rdocs.append("ИНН: " + rdata["inn"])
            if rdocs:
                h_d = 0.35 + (len(rdocs) + 1) * 0.25
                draw_node(rx + 6, ry + 2, 3, h_d, ["ДОКУМЕНТЫ"] + rdocs)
                draw_arrow(rx + 3.5, ry + 2, rx + 4.5, ry + 2)

        rsocials = []
        if rdata.get("vk"): rsocials.append("VK")
        if rdata.get("ok"): rsocials.append("OK")
        if rdata.get("telegram"): rsocials.append("TG")
        if rsocials:
            draw_node(rx + 2, ry - 1.5, 3, 0.6, ["СОЦ СЕТИ", ", ".join(rsocials)])
            draw_arrow(rx + 2, ry - 0.4, rx + 2, ry - 1.2)

        if t.get("name"):
            draw_arrow(6.5, 6.8, rx - 0.5, ry)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=BG_COLOR, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf
  

# ============ КЛАВИАТУРЫ ============
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📝 Пример"))
    markup.add(types.KeyboardButton("⭐ Подписка"))
    markup.add(types.KeyboardButton("🔑 Ключ"))
    return markup


def subscribe_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        label = t["label"] + " — " + str(t["stars"]) + " ⭐"
        cb = "buy_" + key
        markup.add(types.InlineKeyboardButton(label, callback_data=cb))
    return markup


# ============ ПРИМЕР ДАННЫХ ============
EXAMPLE_TEXT = """Иванов Иван Иванович
01.01.2000
+79963132197
@ivan
123456789
vk.com/id123456
4515 123456
770123456789
123-456-789 00
мама: Иванова Мария Петровна
15.05.1970
+79963132198
4515 654321
770123456788
vk.com/id999
папа: Иванов Пётр Сергеевич
20.03.1965
+79963132199
4516 111111
770123456787"""


# ============ ОБРАБОТЧИКИ ============
if bot:
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        uid = message.from_user.id
        uname = message.from_user.username
        fname = message.from_user.first_name

        if not get_user(uid):
            create_user(uid, uname, fname)

        text = (
            "OSINT ВИЗУАЛИЗАТОР\n"
            "\n"
            "Этот бот строит граф связей из данных человека.\n"
            "\n"
            "Требуется подписка. Нажми /menu для доступа.\n"
            "\n"
            "Кнопки:\n"
            "📝 Пример — образец данных\n"
            "⭐ Подписка — купить доступ\n"
            "🔑 Ключ — активировать ключ"
        )
        bot.send_message(message.chat.id, text, reply_markup=main_menu())

    @bot.message_handler(commands=["menu"])
    def cmd_menu(message):
        bot.send_message(message.chat.id, "Выбери действие:", reply_markup=main_menu())

    @bot.message_handler(commands=["help"])
    def cmd_help(message):
        cmd_start(message)

    # ============ КНОПКА ПРИМЕР ============
    @bot.message_handler(func=lambda m: m.text == "📝 Пример")
    def btn_example(message):
        bot.send_message(message.chat.id, "Пример данных для ввода:\n\n" + EXAMPLE_TEXT)

    # ============ КНОПКА ПОДПИСКА ============
    @bot.message_handler(func=lambda m: m.text == "⭐ Подписка")
    def btn_subscribe(message):
        uid = message.from_user.id
        if not get_user(uid):
            create_user(uid, message.from_user.username, message.from_user.first_name)

        text = (
            "Выбери тариф:\n"
            "\n"
            "⭐ 1 день — 15 звёзд\n"
            "⭐ 3 дня — 25 звёзд\n"
            "⭐ Неделя — 50 звёзд\n"
            "⭐ Месяц — 100 звёзд\n"
            "⭐ Навсегда — 200 звёзд"
        )
        bot.send_message(message.chat.id, text, reply_markup=subscribe_menu())

    # ============ КНОПКА КЛЮЧ ============
    @bot.message_handler(func=lambda m: m.text == "🔑 Ключ")
    def btn_key(message):
        msg = bot.send_message(message.chat.id, "Введи ключ:")
        bot.register_next_step_handler(msg, process_key)

    def process_key(message):
        key = message.text.strip()
        uid = message.from_user.id

        if not check_key(key):
            bot.send_message(message.chat.id, "❌ Ключ неверный или уже использован")
            return

        if use_key(key, uid):
            give_subscription(uid, 36500)
            bot.send_message(message.chat.id, "✅ Ключ активирован! Подписка навсегда.")
        else:
            bot.send_message(message.chat.id, "❌ Ошибка активации")

    # ============ ОПЛАТА (INLINE) ============
    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
    def process_buy(call):
        key = call.data.replace("buy_", "")
        t = TARIFFS.get(key)
        if not t:
            return

        uid = call.from_user.id
        if not get_user(uid):
            create_user(uid, call.from_user.username, call.from_user.first_name)

        prices = [types.LabeledPrice(label=t["label"], amount=t["stars"])]

        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title="Подписка " + t["label"],
                description="Доступ к OSINT боту на " + t["label"],
                invoice_payload="sub_" + key,
                provider_token="",
                currency="XTR",
                prices=prices,
                start_parameter="sub"
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, "[!] Ошибка оплаты: " + str(e)[:150])

    # ============ PRE-CHECKOUT ============
    @bot.pre_checkout_query_handler(func=lambda q: True)
    def process_pre_checkout(query):
        bot.answer_pre_checkout_query(query.id, ok=True)

    # ============ УСПЕШНАЯ ОПЛАТА ============
    @bot.message_handler(content_types=["successful_payment"])
    def process_successful_payment(message):
        payload = message.successful_payment.invoice_payload
        key = payload.replace("sub_", "")
        t = TARIFFS.get(key)
        if not t:
            return

        uid = message.from_user.id
        give_subscription(uid, t["days"])
        log_payment(uid, t["stars"], t["days"])

        bot.send_message(
            message.chat.id,
            "✅ Оплата получена!\n"
            "Подписка активирована на " + t["label"] + "."
        )

    # ============ ОБРАБОТКА ДАННЫХ ============
    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/") and m.text not in ["📝 Пример", "⭐ Подписка", "🔑 Ключ"])
    def handle_data(message):
        uid = message.from_user.id

        if not has_subscription(uid):
            bot.send_message(
                message.chat.id,
                "❌ Нет активной подписки.\n"
                "Купи подписку или активируй ключ.",
                reply_markup=main_menu()
            )
            return

        text = message.text.strip()
        if not text:
            return

        bot.send_message(message.chat.id, "[*] Строю граф...")

        try:
            data = parse_input(text)

            if not data["target"]:
                bot.send_message(message.chat.id, "[!] Не нашёл данных. Смотри /help")
                return

            buf = render_graph(data)

            caption = (
                "OSINT ЦЕПОЧКА\n"
                "\n"
                "Цель: " + str(data["target"].get("name", "?")) + "\n"
                "Родственников: " + str(len(data["relatives"]))
            )

            bot.send_photo(message.chat.id, buf, caption=caption)

        except Exception as e:
            bot.send_message(message.chat.id, "[!] Ошибка: " + str(e)[:200])


# ============ ГЕНЕРАЦИЯ 100 КЛЮЧЕЙ ============
def generate_keys(count=100):
    import secrets
    print("[+] Генерация " + str(count) + " ключей...")
    for i in range(count):
        k = "OX-" + secrets.token_hex(8).upper()
        try:
            sb.table("keys").insert({"key": k}).execute()
            print("[+] " + k)
        except Exception as e:
            print("[!] Ошибка: " + str(e))
    print("[+] Готово")


# ============ ЗАПУСК ============
if __name__ == "__main__":
    print("[+] Запускаю Flask...")
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

    if bot:
        print("[+] Запускаю бота...")
        bot.infinity_polling()
    else:
        print("[ERROR] Нет токена")
        import time
        while True:
            time.sleep(60)
