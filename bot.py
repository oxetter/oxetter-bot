#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import re
import telebot
from telebot import types
from flask import Flask, request
from threading import Thread
from supabase import create_client
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
import math

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

print("[DEBUG] Токен: " + str(len(BOT_TOKEN)))
print("[DEBUG] Supabase: " + str(len(SUPABASE_URL)))
print("[DEBUG] Admin: " + str(ADMIN_ID))

BG_COLOR = (10, 10, 10)
NODE_BG = (10, 10, 10)
BORDER_WHITE = (255, 255, 255)
BORDER_RED = (231, 76, 60)
TEXT_COLOR = (255, 255, 255)

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

# ============ БОТ ============
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# ============ ТАРИФЫ ============
TARIFFS = {
    "1day":    {"days": 1,    "stars": 15,  "label": "1 день"},
    "3days":   {"days": 3,    "stars": 25,  "label": "3 дня"},
    "week":    {"days": 7,    "stars": 50,  "label": "Неделя"},
    "month":   {"days": 30,   "stars": 100, "label": "Месяц"},
    "forever": {"days": 36500,"stars": 200, "label": "Навсегда"},
}


# ============ БАЗА ============
def get_user(user_id):
    try:
        res = sb.table("users").select("*").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0]
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
    try:
        dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


def give_subscription(user_id, days):
    u = get_user(user_id)
    if not u:
        create_user(user_id, "", "")
        u = get_user(user_id)
    now = datetime.now(timezone.utc)
    until = u.get("subscription_until") if u else None
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
    except Exception:
        pass
    return False


def use_key(key, user_id):
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


def create_mirror_request(user_id, bot_token):
    try:
        sb.table("mirrors").insert({
            "user_id": user_id,
            "bot_token": bot_token,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception as e:
        print("[ERROR] create_mirror_request: " + str(e))
        return False
      

# ============ УТИЛИТЫ ДЛЯ ПРОВЕРКИ ============
def clean_digits(s):
    return re.sub(r"[^\d]", "", str(s))


def check_passport(value):
    return len(clean_digits(value)) == 10


def check_inn(value):
    return len(clean_digits(value)) == 12


def check_snils(value):
    return len(clean_digits(value)) == 11


def check_phone(value):
    v = value.strip()
    codes = ["+7", "+380", "+998", "+49", "+57", "+91", "+95", "+888", "+777", "+228", "+234", "996"]
    has_code = False
    for c in codes:
        if v.startswith(c):
            has_code = True
            break
    if v.startswith("7") or v.startswith("8"):
        has_code = True
    if not has_code:
        return False
    digits = clean_digits(v)
    return 10 <= len(digits) <= 15


def check_vk(value):
    v = value.strip().lower()
    return v.startswith("https://vk.com/") or v.startswith("http://vk.com/") or v.startswith("vk.com/")


# ============ ПАРСЕР ============
def parse_input(text):
    data = {"target": {}, "relatives": []}
    current_role = None
    current_data = {}

    field_markers = {
        "фио": "name", "имя": "name", "name": "name",
        "др": "dob", "дата рождения": "dob", "dob": "dob",
        "паспорт": "passport", "passport": "passport",
        "инн": "inn", "inn": "inn",
        "снилс": "snils", "snils": "snils",
        "номер": "phone", "телефон": "phone", "phone": "phone",
        "tg": "telegram", "тг": "telegram", "telegram": "telegram",
        "tgid": "tgid", "айди": "tgid", "id": "tgid",
        "вк": "vk", "vk": "vk",
        "ок": "ok", "ok": "ok",
        "wa": "whatsapp", "whatsapp": "whatsapp",
        "max": "max", "макс": "max",
        "адрес": "address", "address": "address",
        "почта": "email", "email": "email",
    }

    role_markers = {
        "target": "TARGET", "цель": "TARGET",
        "мама": "МАМА", "mother": "МАМА", "mom": "МАМА", "mama": "МАМА", "мать": "МАМА",
        "папа": "ПАПА", "father": "ПАПА", "dad": "ПАПА", "papa": "ПАПА", "отец": "ПАПА",
        "брат": "БРАТ", "brother": "БРАТ",
        "сестра": "СЕСТРА", "sister": "СЕСТРА",
        "сын": "СЫН", "son": "СЫН",
        "дочь": "ДОЧЬ", "daughter": "ДОЧЬ",
        "жена": "ЖЕНА", "wife": "ЖЕНА",
        "муж": "МУЖ", "husband": "МУЖ",
        "бабушка": "БАБУШКА",
        "дедушка": "ДЕДУШКА",
        "дядя": "ДЯДЯ", "тётя": "ТЁТЯ",
        "родственник": "РОДСТВЕННИК",
    }

    def save_current():
        nonlocal current_role, current_data
        if current_role is not None:
            if current_role == "TARGET":
                data["target"] = current_data
            else:
                data["relatives"].append({"role": current_role, "data": current_data})
        current_data = {}

    lines = text.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        m = re.match(r"^([A-Za-zА-Яа-яЁё\s]+?)\s*:\s*(.*)$", stripped)
        if m:
            word = m.group(1).lower().strip()
            rest = m.group(2).strip()

            if word in role_markers:
                save_current()
                current_role = role_markers[word]
                current_data = {}
                if rest:
                    current_data["name"] = rest
                continue

            if word in field_markers and current_role is not None:
                ftype = field_markers[word]
                if rest:
                    if ftype == "passport" and not check_passport(rest):
                        continue
                    if ftype == "inn" and not check_inn(rest):
                        continue
                    if ftype == "snils" and not check_snils(rest):
                        continue
                    if ftype == "phone" and not check_phone(rest):
                        continue
                    if ftype == "vk" and not check_vk(rest):
                        continue
                    current_data[ftype] = rest
                continue

        if current_role is not None:
            if "name" not in current_data:
                current_data["name"] = stripped

    save_current()
    return data


# ============ РЕНДЕР ============
def render_graph(data):
    W, H = 2400, 1400
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    for x in range(0, W, 30):
        for y in range(0, H, 30):
            draw.point((x, y), fill=(26, 26, 26))

    font_title = None
    font_text = None
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except Exception:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()

    def text_size(text, font):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            return len(text) * 10, 20

    def draw_node(cx, cy, lines, is_target=False):
        max_w = 0
        for i, line in enumerate(lines):
            f = font_title if i == 0 else font_text
            w, h = text_size(line, f)
            if w > max_w:
                max_w = w
        box_w = max_w + 50
        box_h = len(lines) * 30 + 24

        x1 = cx - box_w // 2
        y1 = cy - box_h // 2
        x2 = cx + box_w // 2
        y2 = cy + box_h // 2

        border = BORDER_RED if is_target else BORDER_WHITE
        bw = 3 if is_target else 2

        draw.rounded_rectangle([x1, y1, x2, y2], radius=10, outline=border, width=bw, fill=NODE_BG)

        for i, line in enumerate(lines):
            f = font_title if i == 0 else font_text
            color = border if (is_target and i == 0) else TEXT_COLOR
            w, h = text_size(line, f)
            draw.text((cx - w // 2, y1 + 12 + i * 30), line, fill=color, font=f)

        return (cx, cy, box_w, box_h)

    def draw_arrow(x1, y1, x2, y2):
        draw.line([(x1, y1), (x2, y2)], fill=BORDER_WHITE, width=2)
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 14
        ax1 = x2 - size * math.cos(angle - math.pi / 6)
        ay1 = y2 - size * math.sin(angle - math.pi / 6)
        ax2 = x2 - size * math.cos(angle + math.pi / 6)
        ay2 = y2 - size * math.sin(angle + math.pi / 6)
        draw.polygon([(x2, y2), (ax1, ay1), (ax2, ay2)], fill=BORDER_WHITE)

    t = data["target"]
    rel = {}
    for r in data["relatives"]:
        rel[r["role"]] = r["data"]

    mother = rel.get("МАМА", {})
    father = rel.get("ПАПА", {})

    # ЮЗЕРНЕЙМ / АЙДИ
    if t.get("telegram") or t.get("tgid"):
        lines = []
        if t.get("telegram"):
            lines.append("ЮЗЕРНЕЙМ ТЕЛЕГРАММ")
        if t.get("tgid"):
            lines.append("АЙДИ ТЕЛЕГРАММ")
        draw_node(250, 620, lines, is_target=True)
        draw_arrow(450, 620, 580, 620)

    # НОМЕР ТЕЛЕФОНА
    if t.get("phone"):
        draw_node(720, 620, ["НОМЕР ТЕЛЕФОНА"], is_target=True)

    # ФИО И ДР
    if t.get("name") or t.get("dob"):
        lines = ["ФИО И ДАТА РОЖДЕНИЯ"]
        if t.get("name"): lines.append(t["name"][:25])
        if t.get("dob"): lines.append(t["dob"])
        draw_node(720, 400, lines, is_target=True)
        draw_arrow(720, 560, 720, 460)

    # ДОКУМЕНТЫ ЖЕРТВЫ
    if t.get("passport") or t.get("inn") or t.get("snils"):
        lines = ["ДОКУМЕНТЫ"]
        parts = []
        if t.get("passport"): parts.append("ПАСПОРТ")
        if t.get("inn"): parts.append("ИНН")
        if t.get("snils"): parts.append("СНИЛС")
        if parts: lines.append(", ".join(parts))
        draw_node(720, 180, lines, is_target=True)
        draw_arrow(720, 320, 720, 240)

    # СОЦ СЕТИ ЖЕРТВЫ
    socials = []
    if t.get("vk"): socials.append("ВК")
    if t.get("ok"): socials.append("ОК")
    if t.get("telegram"): socials.append("ТГ")
    if t.get("whatsapp"): socials.append("МАКС")
    if socials:
        draw_node(720, 850, ["СОЦ СЕТИ", ", ".join(socials)], is_target=True)
        draw_arrow(720, 700, 720, 780)

    # МАМА
    if mother:
        lines = ["МАМА (ФИО+ДР)"]
        if mother.get("name"): lines.append(mother["name"][:25])
        draw_node(1220, 400, lines)
        if t.get("name"):
            draw_arrow(900, 400, 1080, 400)

        if mother.get("phone"):
            draw_node(1220, 180, ["НОМЕР ТЕЛЕФОНА МАМЫ"])
            draw_arrow(1220, 320, 1220, 240)

            if mother.get("passport") or mother.get("inn") or mother.get("snils"):
                lines2 = ["ДОКУМЕНТЫ МАМЫ"]
                p = []
                if mother.get("snils"): p.append("СНИЛС")
                if mother.get("inn"): p.append("ИНН")
                if mother.get("passport"): p.append("ПАСПОРТ")
                if p: lines2.append(", ".join(p))
                draw_node(1700, 180, lines2)
                draw_arrow(1420, 180, 1560, 180)

        msoc = []
        if mother.get("vk"): msoc.append("ВК")
        if mother.get("ok"): msoc.append("ОК")
        if mother.get("telegram"): msoc.append("ТГ")
        if msoc:
            draw_node(1220, 620, ["СОЦ СЕТИ МАМЫ", ", ".join(msoc)])
            draw_arrow(1220, 470, 1220, 560)

        if t.get("address"):
            draw_node(1700, 400, ["АДРЕС", t["address"][:25]])
            draw_arrow(1420, 400, 1560, 400)

    # ПАПА
    if father:
        lines = ["ПАПА (ФИО+ДР)"]
        if father.get("name"): lines.append(father["name"][:25])
        draw_node(1700, 620, lines)
        if t.get("address"):
            draw_arrow(1700, 500, 1700, 570)

        if father.get("address"):
            draw_node(2150, 620, ["АДРЕС ПАПЫ", father["address"][:20]])
            draw_arrow(1890, 620, 2020, 620)

        if father.get("phone"):
            draw_node(1700, 850, ["НОМЕР ТЕЛЕФОНА ПАПЫ"])
            draw_arrow(1700, 700, 1700, 780)

            fsoc = []
            if father.get("vk"): fsoc.append("ВК")
            if father.get("ok"): fsoc.append("ОК")
            if father.get("telegram"): fsoc.append("ТГ")
            if fsoc:
                draw_node(2150, 850, ["СОЦ СЕТИ ПАПЫ", ", ".join(fsoc)])
                draw_arrow(1890, 850, 2020, 850)

            if father.get("passport") or father.get("inn") or father.get("snils"):
                lines2 = ["ДОКУМЕНТЫ ПАПЫ"]
                p = []
                if father.get("snils"): p.append("СНИЛС")
                if father.get("inn"): p.append("ИНН")
                if father.get("passport"): p.append("ПАСПОРТ")
                if p: lines2.append(", ".join(p))
                draw_node(1700, 1080, lines2)
                draw_arrow(1700, 930, 1700, 1010)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
  

# ============ КЛАВИАТУРЫ ============
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📝 Пример"))
    markup.add(types.KeyboardButton("⭐ Подписка"))
    markup.add(types.KeyboardButton("🔑 Ключ доступа"))
    markup.add(types.KeyboardButton("🔁 Создать зеркало"))
    return markup


def subscribe_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        label = t["label"] + " — " + str(t["stars"]) + " ⭐"
        cb = "buy_" + key
        markup.add(types.InlineKeyboardButton(label, callback_data=cb))
    return markup


EXAMPLE_TEXT = """TARGET: Смирнов Дмитрий Андреевич
ДАТА РОЖДЕНИЯ: 14.03.2003
НОМЕР: +79161234567
TG: @dmitry_s
TGID: 287654321
VK: https://vk.com/id567890
ПАСПОРТ: 4512789456
ИНН: 770987654321
СНИЛС: 14578932145
АДРЕС: МОСКВА, УЛ. ТВЕРСКАЯ 12

мама: Смирнова Елена Викторовна
ДАТА РОЖДЕНИЯ: 22.07.1978
НОМЕР: +79169876543
TG: @elena_v
VK: https://vk.com/id111222
ПАСПОРТ: 4513654987
ИНН: 770987654322
СНИЛС: 14578932146
АДРЕС: МОСКВА, УЛ. ТВЕРСКАЯ 12

папа: Смирнов Андрей Петрович
ДАТА РОЖДЕНИЯ: 09.11.1975
НОМЕР: +79165554433
VK: https://vk.com/id333444
ПАСПОРТ: 4514111222
ИНН: 770987654323
СНИЛС: 14578932147"""


# ============ ОБРАБОТЧИКИ ============
if bot:
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        uid = message.from_user.id
        if not get_user(uid):
            create_user(uid, message.from_user.username, message.from_user.first_name)
        text = (
            "OSINT ВИЗУАЛИЗАТОР\n\n"
            "Бот строит граф связей из данных.\n\n"
            "Кнопки:\n"
            "📝 Пример — образец данных\n"
            "⭐ Подписка — купить доступ\n"
            "🔑 Ключ доступа — активировать ключ\n"
            "🔁 Создать зеркало — +12ч подписки"
        )
        bot.send_message(message.chat.id, text, reply_markup=main_menu())

    @bot.message_handler(commands=["menu"])
    def cmd_menu(message):
        bot.send_message(message.chat.id, "Выбери действие:", reply_markup=main_menu())

    @bot.message_handler(commands=["help"])
    def cmd_help(message):
        cmd_start(message)

    @bot.message_handler(commands=["mykeys"])
    def cmd_mykeys(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "❌ Нет доступа")
            return
        try:
            res = sb.table("keys").select("key").is_("used_by", "null").execute()
            keys = [r["key"] for r in res.data] if res.data else []
            if not keys:
                bot.send_message(message.chat.id, "Свободных ключей нет")
                return
            text = "\n".join(keys)
            buf = io.BytesIO(text.encode("utf-8"))
            buf.name = "keys.txt"
            bot.send_document(message.chat.id, buf, caption="Свободных ключей: " + str(len(keys)))
        except Exception as e:
            bot.send_message(message.chat.id, "Ошибка: " + str(e)[:150])

    @bot.message_handler(func=lambda m: m.text == "📝 Пример")
    def btn_example(message):
        bot.send_message(message.chat.id, "Пример данных:\n\n" + EXAMPLE_TEXT)

    @bot.message_handler(func=lambda m: m.text == "⭐ Подписка")
    def btn_subscribe(message):
        uid = message.from_user.id
        if not get_user(uid):
            create_user(uid, message.from_user.username, message.from_user.first_name)
        text = (
            "Выбери тариф:\n\n"
            "⭐ 1 день — 15 звёзд\n"
            "⭐ 3 дня — 25 звёзд\n"
            "⭐ Неделя — 50 звёзд\n"
            "⭐ Месяц — 100 звёзд\n"
            "⭐ Навсегда — 200 звёзд"
        )
        bot.send_message(message.chat.id, text, reply_markup=subscribe_menu())

    @bot.message_handler(func=lambda m: m.text == "🔑 Ключ доступа")
    def btn_key(message):
        msg = bot.send_message(message.chat.id, "Введи ключ:")
        bot.register_next_step_handler(msg, process_key)

    def process_key(message):
        key = message.text.strip()
        uid = message.from_user.id
        if not check_key(key):
            bot.send_message(message.chat.id, "❌ Ключ неверный или использован")
            return
        if use_key(key, uid):
            give_subscription(uid, 36500)
            bot.send_message(message.chat.id, "✅ Ключ активирован! Подписка навсегда.")
        else:
            bot.send_message(message.chat.id, "❌ Ошибка активации")

    @bot.message_handler(func=lambda m: m.text == "🔁 Создать зеркало")
    def btn_mirror(message):
        text = (
            "🔁 СОЗДАНИЕ ЗЕРКАЛА\n\n"
            "За создание зеркала — +12 часов подписки.\n\n"
            "ИНСТРУКЦИЯ:\n"
            "1. Открой @BotFather\n"
            "2. Напиши /newbot\n"
            "3. Придумай имя и юзернейм\n"
            "4. Скопируй токен\n"
            "5. Отправь токен сюда\n\n"
            "⚠️ Токен от НОВОГО бота."
        )
        msg = bot.send_message(message.chat.id, text)
        bot.register_next_step_handler(msg, process_mirror)

    def process_mirror(message):
        token = message.text.strip()
        uid = message.from_user.id
        if not re.match(r"^\d{8,12}:[A-Za-z0-9_\-]{30,}$", token):
            bot.send_message(message.chat.id, "❌ Неверный формат токена")
            return
        if create_mirror_request(uid, token):
            give_subscription(uid, 0.5)
            bot.send_message(
                message.chat.id,
                "✅ Заявка принята! +12 часов подписки.\n"
                "Зеркало активирует администратор."
            )
            if ADMIN_ID:
                try:
                    bot.send_message(
                        ADMIN_ID,
                        "🔁 НОВОЕ ЗЕРКАЛО\n"
                        "От: " + str(uid) + " (@" + str(message.from_user.username) + ")\n"
                        "Токен: " + token[:20] + "..."
                    )
                except Exception:
                    pass
        else:
            bot.send_message(message.chat.id, "❌ Ошибка сохранения")

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
            bot.send_message(call.message.chat.id, "[!] Ошибка: " + str(e)[:150])

    @bot.pre_checkout_query_handler(func=lambda q: True)
    def process_pre_checkout(query):
        bot.answer_pre_checkout_query(query.id, ok=True)

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
            "✅ Оплата получена!\nПодписка активирована на " + t["label"] + "."
        )

    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/") and m.text not in ["📝 Пример", "⭐ Подписка", "🔑 Ключ доступа", "🔁 Создать зеркало"])
    def handle_data(message):
        uid = message.from_user.id
        if not has_subscription(uid):
            bot.send_message(
                message.chat.id,
                "❌ Нет активной подписки.\nКупи подписку или активируй ключ.",
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
            bot.send_photo(message.chat.id, buf)
        except Exception as e:
            bot.send_message(message.chat.id, "[!] Ошибка: " + str(e)[:200])


# ============ WEBHOOK ============
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("utf-8")
        print("[DEBUG] Получен update: " + json_str[:150])
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print("[ERROR] webhook: " + str(e))
    return "OK", 200


# ============ УСТАНОВКА WEBHOOK ============
def set_webhook():
    try:
        import requests as rq
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if not render_url:
            print("[!] RENDER_EXTERNAL_URL не задан")
            return False
        webhook_url = render_url + "/webhook"
        resp = rq.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": ["message", "callback_query", "pre_checkout_query"]
            }
        )
        print("[+] Webhook: " + str(resp.json()))
        return True
    except Exception as e:
        print("[ERROR] set_webhook: " + str(e))
        return False


if __name__ == "__main__":
    print("[+] Запускаю Flask...")
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

    if bot:
        import time
        time.sleep(3)
        print("[+] Устанавливаю webhook...")
        set_webhook()
        print("[+] Бот запущен через webhook")
        while True:
            time.sleep(60)
    else:
        print("[ERROR] Нет токена")
        import time
        while True:
            time.sleep(60)
