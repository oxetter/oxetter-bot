#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import re
import json
import socket
import time
import requests
import telebot
from telebot import types
from flask import Flask, request
from threading import Thread
from supabase import create_client
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS, GPSTAGS
import math

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

CHANNEL_USERNAME = "worksoxetter"
CHANNEL_LINK = "https://t.me/worksoxetter"
TRIAL_LIMIT = 5
KEY_SUB_DAYS = 30

print("[DEBUG] Токен: " + str(len(BOT_TOKEN)))
print("[DEBUG] Supabase: " + str(len(SUPABASE_URL)))

BG_COLOR = (10, 10, 10)
NODE_BG = (10, 10, 10)
BORDER_WHITE = (255, 255, 255)
BORDER_RED = (231, 76, 60)
TEXT_COLOR = (255, 255, 255)

ROLE_COLORS = {
    "TARGET": (231, 76, 60),
    "МАМА": (52, 152, 219),
    "ПАПА": (46, 204, 113),
    "БРАТ": (230, 126, 34),
    "СЕСТРА": (231, 76, 160),
    "СЫН": (155, 89, 182),
    "ДОЧЬ": (241, 196, 15),
    "ЖЕНА": (231, 76, 160),
    "МУЖ": (52, 152, 219),
    "БАБУШКА": (149, 165, 166),
    "ДЕДУШКА": (127, 140, 141),
    "ДЯДЯ": (192, 57, 43),
    "ТЁТЯ": (142, 68, 173),
    "РОДСТВЕННИК": (255, 255, 255),
    "ДРУГ": (241, 196, 15),
}


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
bot._last_graph = {}
bot._last_canvas = {}
bot._last_data = {}

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
        sb.table("users").update({"subscription_until": new_until.isoformat()}).eq("user_id", user_id).execute()
    except Exception:
        pass


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
        sb.table("keys").update({"used_by": user_id, "used_at": datetime.now(timezone.utc).isoformat()}).eq("key", key).execute()
        return True
    except Exception:
        return False


def log_payment(user_id, stars, days):
    try:
        sb.table("payments").insert({"user_id": user_id, "amount": stars, "days": days}).execute()
    except Exception:
        pass


def create_mirror_request(user_id, bot_token):
    try:
        sb.table("mirrors").insert({"user_id": user_id, "bot_token": bot_token, "status": "pending"}).execute()
        return True
    except Exception:
        return False


def get_trial_count(user_id):
    u = get_user(user_id)
    if not u:
        return 0
    return u.get("trial_used", 0) or 0


def use_trial(user_id):
    count = get_trial_count(user_id)
    if count >= TRIAL_LIMIT:
        return False
    try:
        sb.table("users").update({"trial_used": count + 1}).eq("user_id", user_id).execute()
        return True
    except Exception:
        return False


def has_trial_left(user_id):
    return get_trial_count(user_id) < TRIAL_LIMIT
  

# ============ ПАРСЕР ============
def parse_input(text):
    """Умный парсер. TARGET не обязателен — первый блок = цель."""
    data = {"target": {}, "relatives": []}
    current_role = None
    current_data = {}
    first_block_saved = False

    field_markers = {
        "фио": "name", "имя": "name", "name": "name", "ф.и.о": "name",
        "др": "dob", "дата рождения": "dob", "dob": "dob", "birthday": "dob",
        "паспорт": "passport", "passport": "passport", "пас": "passport",
        "инн": "inn", "inn": "inn",
        "снилс": "snils", "snils": "snils",
        "номер": "phone", "телефон": "phone", "phone": "phone", "тел": "phone",
        "tg": "telegram", "тг": "telegram", "telegram": "telegram",
        "tgid": "tgid", "айди": "tgid", "id": "tgid",
        "вк": "vk", "vk": "vk",
        "ок": "ok", "ok": "ok",
        "wa": "whatsapp", "whatsapp": "whatsapp",
        "max": "max", "макс": "max",
        "адрес": "address", "address": "address", "город": "city",
        "почта": "email", "email": "email", "mail": "email",
    }

    role_markers = {
        "target": "TARGET", "цель": "TARGET", "жертва": "TARGET",
        "мама": "МАМА", "mother": "МАМА", "mom": "МАМА", "mama": "МАМА", "мать": "МАМА",
        "папа": "ПАПА", "father": "ПАПА", "dad": "ПАПА", "papa": "ПАПА", "отец": "ПАПА",
        "брат": "БРАТ", "brother": "БРАТ", "bro": "БРАТ",
        "сестра": "СЕСТРА", "sister": "СЕСТРА", "sis": "СЕСТРА",
        "сын": "СЫН", "son": "СЫН",
        "дочь": "ДОЧЬ", "daughter": "ДОЧЬ",
        "жена": "ЖЕНА", "wife": "ЖЕНА",
        "муж": "МУЖ", "husband": "МУЖ",
        "бабушка": "БАБУШКА", "grandmother": "БАБУШКА",
        "дедушка": "ДЕДУШКА", "grandfather": "ДЕДУШКА",
        "дядя": "ДЯДЯ", "uncle": "ДЯДЯ",
        "тётя": "ТЁТЯ", "тетя": "ТЁТЯ", "aunt": "ТЁТЯ",
        "родственник": "РОДСТВЕННИК", "родня": "РОДСТВЕННИК",
        "друг": "ДРУГ", "friend": "ДРУГ",
    }

    def auto_detect_field(value):
        v = value.strip()
        l = v.lower()
        if not v:
            return None
        if re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$", v):
            return "email"
        if "t.me" in l:
            return "telegram"
        if v.startswith("@") and len(v) < 40:
            return "telegram"
        if "vk.com" in l or "vk.ru" in l:
            return "vk"
        if "ok.ru" in l:
            return "ok"
        if "wa.me" in l or "whatsapp" in l:
            return "whatsapp"
        if "max.ru" in l:
            return "max"
        if re.match(r"^\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4}$", v):
            return "dob"
        digits = re.sub(r"[^\d]", "", v)
        if re.match(r"^[\d\s\-\+\(\)]+$", v):
            if "+" in v or v.startswith("7") or v.startswith("8"):
                if 10 <= len(digits) <= 15:
                    return "phone"
            if len(digits) == 10:
                return "passport"
            if len(digits) == 11:
                return "snils"
            if len(digits) == 12:
                return "inn"
        if any(w in l for w in ["ул.", "улица", "г.", "город", "обл.", "область", "пр.", "проспект", "д.", "дом", "street", "avenue"]):
            return "address"
        if re.match(r"^[А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z][а-яёa-z]+", v):
            return "name"
        return "other"

    def save_current():
        nonlocal current_role, current_data, first_block_saved
        if current_data:
            if current_role is None and not first_block_saved:
                data["target"] = current_data
                first_block_saved = True
            elif current_role == "TARGET":
                data["target"] = current_data
                first_block_saved = True
            elif current_role is not None:
                data["relatives"].append({"role": current_role, "data": current_data})
                first_block_saved = True
        current_data = {}

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        m = re.match(r"^([A-Za-zА-Яа-яЁё\s\.]+?)\s*[:\-]\s*(.*)$", stripped)
        if m:
            word = m.group(1).lower().strip()
            rest = m.group(2).strip()

            if word in role_markers:
                save_current()
                current_role = role_markers[word]
                current_data = {}
                if rest:
                    ftype = auto_detect_field(rest)
                    if ftype and ftype != "other":
                        current_data[ftype] = rest
                    else:
                        current_data["name"] = rest
                continue

            if word in field_markers:
                ftype = field_markers[word]
                if rest:
                    current_data[ftype] = rest
                continue

            if rest:
                ftype = auto_detect_field(rest)
                if ftype and ftype != "other":
                    current_data[ftype] = rest
                continue

        ftype = auto_detect_field(stripped)
        if ftype and ftype != "other":
            current_data[ftype] = stripped
        elif "name" not in current_data:
            current_data["name"] = stripped

    save_current()
    return data


# ============ РЕНДЕР ГРАФА ============
def render_graph(data):
    t = data.get("target") or {}
    relatives = data.get("relatives") or []

    nodes_count = 0
    if t: nodes_count += 1
    for r in relatives:
        d = r.get("data") or {}
        nodes_count += 1
        for key in ["phone", "telegram", "vk", "ok", "whatsapp", "max", "email", "address",
                    "passport", "inn", "snils", "name", "dob", "tgid"]:
            if d.get(key):
                nodes_count += 1

    base_width = 2400
    base_height = 1400
    extra_height = max(0, (nodes_count - 10) * 80)
    W = base_width
    H = base_height + extra_height
    if nodes_count > 30:
        W = 3200
        H = 2000 + (nodes_count - 30) * 60
    if nodes_count > 60:
        W = 4000
        H = 2600 + (nodes_count - 60) * 50

    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    for x in range(0, W, 30):
        for y in range(0, H, 30):
            draw.point((x, y), fill=(26, 26, 26))

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
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

    def draw_node(cx, cy, lines, color):
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
        draw.rounded_rectangle([x1, y1, x2, y2], radius=10, outline=color, width=3, fill=NODE_BG)
        for i, line in enumerate(lines):
            f = font_title if i == 0 else font_text
            c = color if i == 0 else TEXT_COLOR
            w, h = text_size(line, f)
            draw.text((cx - w // 2, y1 + 12 + i * 30), line, fill=c, font=f)
        return (x1, y1, x2, y2)

    def draw_arrow(x1, y1, x2, y2, color=(255, 255, 255)):
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 14
        ax1 = x2 - size * math.cos(angle - math.pi / 6)
        ay1 = y2 - size * math.sin(angle - math.pi / 6)
        ax2 = x2 - size * math.cos(angle + math.pi / 6)
        ay2 = y2 - size * math.sin(angle + math.pi / 6)
        draw.polygon([(x2, y2), (ax1, ay1), (ax2, ay2)], fill=color)

    target_color = ROLE_COLORS.get("TARGET", (231, 76, 60))
    target_cx = 400
    target_cy = H // 2

    target_lines = []
    if t.get("name"):
        target_lines.append("ЦЕЛЬ: " + str(t["name"])[:35])
    else:
        target_lines.append("ЦЕЛЬ")
    if t.get("dob"): target_lines.append("🎂 " + str(t["dob"]))
    if t.get("phone"): target_lines.append("📱 " + str(t["phone"]))
    if t.get("telegram"): target_lines.append("🔷 " + str(t["telegram"]))
    if t.get("tgid"): target_lines.append("🆔 " + str(t["tgid"]))
    if t.get("email"): target_lines.append("📧 " + str(t["email"]))
    if t.get("address"): target_lines.append("📍 " + str(t["address"])[:30])
    if t.get("passport"): target_lines.append("📄 " + str(t["passport"]))
    if t.get("inn"): target_lines.append("💰 " + str(t["inn"]))
    if t.get("snils"): target_lines.append("📋 " + str(t["snils"]))

    target_bbox = draw_node(target_cx, target_cy, target_lines, target_color)

    if relatives:
        rel_x = W - 500
        step = max(250, (H - 200) // max(len(relatives), 1))
        start_y = 200

        for idx, rel in enumerate(relatives):
            role = rel.get("role", "РОДСТВЕННИК")
            rdata = rel.get("data") or {}
            color = ROLE_COLORS.get(role, (255, 255, 255))
            rel_cy = start_y + idx * step

            rel_lines = [role]
            if rdata.get("name"): rel_lines.append(str(rdata["name"])[:30])
            if rdata.get("dob"): rel_lines.append("🎂 " + str(rdata["dob"]))
            if rdata.get("phone"): rel_lines.append("📱 " + str(rdata["phone"]))
            if rdata.get("telegram"): rel_lines.append("🔷 " + str(rdata["telegram"]))
            if rdata.get("email"): rel_lines.append("📧 " + str(rdata["email"]))
            if rdata.get("address"): rel_lines.append("📍 " + str(rdata["address"])[:25])
            if rdata.get("passport"): rel_lines.append("📄 " + str(rdata["passport"]))
            if rdata.get("inn"): rel_lines.append("💰 " + str(rdata["inn"]))
            if rdata.get("snils"): rel_lines.append("📋 " + str(rdata["snils"]))

            rel_bbox = draw_node(rel_x, rel_cy, rel_lines, color)
            draw_arrow(target_bbox[2], target_cy, rel_bbox[0], rel_cy, color)

    canvas_json = generate_obsidian_canvas(data)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf, canvas_json


def generate_obsidian_canvas(data):
    t = data.get("target") or {}
    relatives = data.get("relatives") or []

    canvas = {"nodes": [], "edges": []}

    def add_node(node_id, text, x, y, color="1"):
        canvas["nodes"].append({
            "id": node_id, "type": "text", "text": text,
            "x": x, "y": y, "width": 400, "height": 300, "color": color
        })

    def add_edge(from_id, to_id, label=""):
        canvas["edges"].append({
            "id": "edge_" + str(len(canvas["edges"])),
            "fromNode": from_id, "fromSide": "right",
            "toNode": to_id, "toSide": "left", "label": label
        })

    target_text = "**🎯 ЦЕЛЬ**\n\n"
    if t.get("name"): target_text += "**" + str(t["name"]) + "**\n"
    if t.get("dob"): target_text += "🎂 " + str(t["dob"]) + "\n"
    if t.get("phone"): target_text += "📱 " + str(t["phone"]) + "\n"
    if t.get("telegram"): target_text += "🔷 " + str(t["telegram"]) + "\n"
    if t.get("tgid"): target_text += "🆔 " + str(t["tgid"]) + "\n"
    if t.get("email"): target_text += "📧 " + str(t["email"]) + "\n"
    if t.get("address"): target_text += "📍 " + str(t["address"]) + "\n"
    if t.get("passport"): target_text += "📄 " + str(t["passport"]) + "\n"
    if t.get("inn"): target_text += "💰 " + str(t["inn"]) + "\n"
    if t.get("snils"): target_text += "📋 " + str(t["snils"]) + "\n"

    add_node("target", target_text, 0, 0, "1")

    y_pos = 400
    for idx, rel in enumerate(relatives):
        role = rel.get("role", "РОДСТВЕННИК")
        rdata = rel.get("data") or {}

        rel_text = "**👤 " + role + "**\n\n"
        if rdata.get("name"): rel_text += "**" + str(rdata["name"]) + "**\n"
        if rdata.get("dob"): rel_text += "🎂 " + str(rdata["dob"]) + "\n"
        if rdata.get("phone"): rel_text += "📱 " + str(rdata["phone"]) + "\n"
        if rdata.get("telegram"): rel_text += "🔷 " + str(rdata["telegram"]) + "\n"
        if rdata.get("email"): rel_text += "📧 " + str(rdata["email"]) + "\n"
        if rdata.get("address"): rel_text += "📍 " + str(rdata["address"]) + "\n"
        if rdata.get("passport"): rel_text += "📄 " + str(rdata["passport"]) + "\n"
        if rdata.get("inn"): rel_text += "💰 " + str(rdata["inn"]) + "\n"
        if rdata.get("snils"): rel_text += "📋 " + str(rdata["snils"]) + "\n"

        rel_id = "rel_" + str(idx)
        add_node(rel_id, rel_text, 600, y_pos, "2")
        add_edge("target", rel_id, role)
        y_pos += 400

    return json.dumps(canvas, ensure_ascii=False, indent=2)
  

# ============ OSINT ============
def phone_info(phone):
    try:
        import phonenumbers
        from phonenumbers import carrier, geocoder, timezone
    except ImportError:
        os.system(f"{os.sys.executable} -m pip install phonenumbers")
        import phonenumbers
        from phonenumbers import carrier, geocoder, timezone

    phone_clean = re.sub(r"[^\d+]", "", phone)
    if phone_clean.startswith("8"):
        phone_clean = "+7" + phone_clean[1:]
    if not phone_clean.startswith("+"):
        phone_clean = "+" + phone_clean

    r = {"input": phone_clean, "valid": False}
    try:
        parsed = phonenumbers.parse(phone_clean, None)
    except Exception:
        return r
    if not phonenumbers.is_valid_number(parsed):
        return r

    r["valid"] = True
    r["country"] = phonenumbers.region_code_for_number(parsed)
    r["operator"] = carrier.name_for_number(parsed, "ru")
    r["region"] = geocoder.description_for_number(parsed, "ru")
    tz = timezone.time_zones_for_number(parsed)
    r["timezone"] = list(tz)[0] if tz else None

    try:
        num = re.sub(r"[^\d]", "", phone_clean)
        if num.startswith("8"):
            num = "7" + num[1:]
        link = "https://t.me/+" + num
        r["tg_link"] = link
        rq = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if "tgme_page_title" in rq.text:
            m = re.search(r'<div class="tgme_page_title"[^>]*>([^<]+)</div>', rq.text)
            r["telegram"] = "✅ " + (m.group(1).strip() if m else "есть")
        else:
            r["telegram"] = "❌ Нет"
    except Exception:
        pass
    return r


def ip_info(ip):
    r = {"input": ip, "valid": False}
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip.strip())
    if not m:
        return r
    for part in m.groups():
        if int(part) > 255:
            return r
    r["valid"] = True
    try:
        rq = requests.get(f"http://ip-api.com/json/{ip}",
                          params={"fields": "status,message,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as"},
                          timeout=10)
        data = rq.json()
        if data.get("status") == "success":
            r["country"] = data.get("country")
            r["country_code"] = data.get("countryCode")
            r["region"] = data.get("regionName")
            r["city"] = data.get("city")
            r["zip"] = data.get("zip")
            r["lat"] = data.get("lat")
            r["lon"] = data.get("lon")
            r["timezone"] = data.get("timezone")
            r["isp"] = data.get("isp")
            r["org"] = data.get("org")
            r["as"] = data.get("as")
        else:
            r["error"] = data.get("message", "Ошибка")
    except Exception as e:
        r["error"] = str(e)[:60]
    return r


def domain_info(domain):
    r = {"input": domain, "valid": False}
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if not re.match(r"^[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$", domain):
        return r
    r["valid"] = True
    r["domain"] = domain
    try:
        r["ip"] = socket.gethostbyname(domain)
    except Exception:
        r["ip"] = None
    if r.get("ip"):
        try:
            rq = requests.get(f"http://ip-api.com/json/{r['ip']}", timeout=10)
            data = rq.json()
            if data.get("status") == "success":
                r["country"] = data.get("country")
                r["city"] = data.get("city")
                r["isp"] = data.get("isp")
        except Exception:
            pass
    try:
        rq = requests.get(f"https://rdap.org/domain/{domain}", timeout=15)
        if rq.status_code == 200:
            data = rq.json()
            for ev in data.get("events", []):
                if ev.get("eventAction") == "registration":
                    r["created"] = ev.get("eventDate", "")[:10]
                elif ev.get("eventAction") == "expiration":
                    r["expires"] = ev.get("eventDate", "")[:10]
            for ent in data.get("entities", []):
                if "registrar" in ent.get("roles", []):
                    vcard = ent.get("vcardArray", [])
                    if len(vcard) > 1:
                        for item in vcard[1]:
                            if item[0] == "fn":
                                r["registrar"] = item[3]
    except Exception:
        pass
    return r


def _gps_to_decimal(coords, ref):
    try:
        d = float(coords[0]); m = float(coords[1]); s = float(coords[2])
        result = d + (m / 60.0) + (s / 3600.0)
        if ref in ["S", "W"]:
            result = -result
        return round(result, 6)
    except Exception:
        return 0


def photo_exif(image_bytes):
    r = {"valid": False, "has_exif": False}
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exifdata = img.getexif()
        if not exifdata:
            r["valid"] = True
            return r
        r["valid"] = True
        r["has_exif"] = True
        r["info"] = {}
        for tag_id, value in exifdata.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ["Make", "Model", "Software", "DateTime", "DateTimeOriginal",
                       "ExifImageWidth", "ExifImageHeight"]:
                r["info"][tag] = str(value)
        try:
            gps_ifd = exifdata.get_ifd(0x8825)
            if gps_ifd:
                gps_data = {}
                for tag_id, value in gps_ifd.items():
                    gps_data[GPSTAGS.get(tag_id, tag_id)] = value
                if "GPSLatitude" in gps_data and "GPSLongitude" in gps_data:
                    lat = _gps_to_decimal(gps_data["GPSLatitude"], gps_data.get("GPSLatitudeRef", "N"))
                    lon = _gps_to_decimal(gps_data["GPSLongitude"], gps_data.get("GPSLongitudeRef", "E"))
                    r["coords"] = str(lat) + ", " + str(lon)
                    r["maps"] = "https://www.google.com/maps/place/" + str(lat) + "," + str(lon)
        except Exception:
            pass
    except Exception as e:
        r["error"] = str(e)[:60]
    return r


def username_info(nick):
    nick = nick.strip().lstrip("@")
    r = {"input": nick, "platforms": {}}
    platforms = {
        "VK": f"https://vk.com/{nick}",
        "Telegram": f"https://t.me/{nick}",
        "TikTok": f"https://www.tiktok.com/@{nick}",
        "Instagram": f"https://www.instagram.com/{nick}",
        "GitHub": f"https://github.com/{nick}",
        "Twitter": f"https://twitter.com/{nick}",
        "YouTube": f"https://www.youtube.com/@{nick}",
        "Reddit": f"https://www.reddit.com/user/{nick}",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for name, url in platforms.items():
        try:
            rq = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
            if rq.status_code == 200:
                r["platforms"][name] = url
        except Exception:
            pass
    return r


def fio_info(fio):
    r = {"input": fio, "gender": None, "nationality": None}
    parts = fio.split()
    if len(parts) >= 3:
        ml = parts[-1].lower()
        if ml.endswith("ович") or ml.endswith("евич"):
            r["gender"] = "Мужской"
        elif ml.endswith("овна") or ml.endswith("евна") or ml.endswith("ична"):
            r["gender"] = "Женский"
    l = fio.lower()
    if "енко" in l or l.endswith("ук"):
        r["nationality"] = "Украинская"
    elif "ян" in l:
        r["nationality"] = "Армянская"
    elif "дзе" in l or "швили" in l:
        r["nationality"] = "Грузинская"
    elif "оглы" in l or "заде" in l:
        r["nationality"] = "Азербайджанская"
    elif any(s in l for s in ["ов", "ев", "ин", "ский", "цкий"]):
        r["nationality"] = "Русская/славянская"
    return r


# ============ КЛАВИАТУРЫ ============
def main_menu_inline(user_id=0):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 Пример", callback_data="menu_example"),
        types.InlineKeyboardButton("⭐ Подписка", callback_data="menu_subscribe"),
    )
    markup.add(
        types.InlineKeyboardButton("🔑 Ключ доступа", callback_data="menu_key"),
        types.InlineKeyboardButton("🔁 Создать зеркало", callback_data="menu_mirror"),
    )
    markup.add(
        types.InlineKeyboardButton("🎁 Пробная подписка", callback_data="menu_trial"),
        types.InlineKeyboardButton("🔍 Поиск", callback_data="menu_search"),
    )
    return markup


def search_menu_inline():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📱 Номер", callback_data="search_phone"),
        types.InlineKeyboardButton("📛 ФИО", callback_data="search_fio"),
        types.InlineKeyboardButton("👤 Ник", callback_data="search_nick"),
        types.InlineKeyboardButton("📡 IP", callback_data="search_ip"),
        types.InlineKeyboardButton("🌐 Домен", callback_data="search_domain"),
        types.InlineKeyboardButton("📷 EXIF фото", callback_data="search_exif"),
    )
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_back"))
    return markup


def subscribe_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        markup.add(types.InlineKeyboardButton(t["label"] + " — " + str(t["stars"]) + " ⭐", callback_data="buy_" + key))
    return markup


EXAMPLE_TEXT = """Иванов Сергей Петрович
Дата рождения: 12.05.1995
Номер: +79001234567
TG: @sergey_ivanov
TGID: 123456789
Email: sergey@mail.ru
Адрес: МОСКВА, УЛ. ЛЕНИНА 15
Паспорт: 4515 123456
ИНН: 770123456789
СНИЛС: 12345678900

мама: Иванова Ольга Николаевна
Дата рождения: 20.08.1970
Номер: +79007654321
TG: @olga_iv
Адрес: МОСКВА, УЛ. ЛЕНИНА 15

папа: Иванов Пётр Сергеевич
Дата рождения: 15.03.1968
Номер: +79005554433
TG: @petr_iv

брат: Иванов Дмитрий Петрович
Дата рождения: 10.11.1999
Номер: +79003332211

сестра: Иванова Анна Петровна
Дата рождения: 05.07.2003
Номер: +79001112233"""


# ============ КАНАЛ + МЕНЮ ============
def is_subscribed(user_id):
    try:
        res = bot.get_chat_member(chat_id="@" + CHANNEL_USERNAME, user_id=user_id)
        return res.status in ["member", "administrator", "creator"]
    except Exception:
        return False


def send_subscribe_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_LINK))
    markup.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
    bot.send_message(chat_id, "⚠️ Подпишись на канал:\n" + CHANNEL_LINK, reply_markup=markup)


def send_menu(chat_id, user_id=0):
    try:
        bot.send_message(chat_id, "━━━━━━━━━━━━━━━\n🔽 Меню:", reply_markup=main_menu_inline(user_id))
    except Exception as e:
        print("[ERROR] send_menu: " + str(e))
      

# ============ ПРОГРЕСС ============
def show_progress(chat_id, text, percent):
    bar_length = 10
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    try:
        msg = bot.send_message(chat_id, text + "\n\n[" + bar + "] " + str(percent) + "%")
        return msg.message_id
    except Exception:
        return None


def update_progress(chat_id, message_id, text, percent):
    if not message_id:
        return
    bar_length = 10
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text + "\n\n[" + bar + "] " + str(percent) + "%")
    except Exception:
        pass


# ============ ОБРАБОТЧИКИ ============
if bot:
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        uid = message.from_user.id
        if not get_user(uid):
            create_user(uid, message.from_user.username, message.from_user.first_name)
        if not is_subscribed(uid):
            send_subscribe_message(message.chat.id)
            return
        text = (
            "OSINT БОТ\n\n"
            "Граф связей + поиск информации.\n\n"
            "Кнопки:\n"
            "📝 Пример — образец данных\n"
            "⭐ Подписка — купить доступ\n"
            "🔑 Ключ доступа — активировать\n"
            "🔁 Создать зеркало — +12ч\n"
            "🎁 Пробная подписка — 5 запросов\n"
            "🔍 Поиск — OSINT"
        )
        bot.send_message(message.chat.id, text, reply_markup=main_menu_inline(uid))

    @bot.message_handler(commands=["menu"])
    def cmd_menu(message):
        bot.send_message(message.chat.id, "Меню:", reply_markup=main_menu_inline(message.from_user.id))

    @bot.callback_query_handler(func=lambda call: call.data == "menu_back")
    def cb_back(call):
        bot.answer_callback_query(call.id)
        bot.edit_message_text("Меню:", call.message.chat.id, call.message.message_id, reply_markup=main_menu_inline())

    @bot.callback_query_handler(func=lambda call: call.data == "check_sub")
    def process_check_sub(call):
        uid = call.from_user.id
        if is_subscribed(uid):
            bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
            bot.send_message(call.message.chat.id, "✅ Добро пожаловать!", reply_markup=main_menu_inline(uid))
        else:
            bot.answer_callback_query(call.id, "❌ Не подписан!", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_example")
    def cb_example(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Пример данных:\n\n" + EXAMPLE_TEXT)
        send_menu(call.message.chat.id, call.from_user.id)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_subscribe")
    def cb_subscribe(call):
        bot.answer_callback_query(call.id)
        uid = call.from_user.id
        if not get_user(uid):
            create_user(uid, call.from_user.username, call.from_user.first_name)
        bot.send_message(call.message.chat.id, "Выбери тариф:", reply_markup=subscribe_menu())

    @bot.callback_query_handler(func=lambda call: call.data == "menu_key")
    def cb_key(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Введи ключ доступа:")
        bot.register_next_step_handler(msg, process_key)

    def process_key(message):
        key = message.text.strip()
        uid = message.from_user.id
        if not check_key(key):
            bot.send_message(message.chat.id, "❌ Ключ неверный или использован")
            send_menu(message.chat.id, uid)
            return
        if use_key(key, uid):
            give_subscription(uid, KEY_SUB_DAYS)
            bot.send_message(message.chat.id, "✅ Ключ активирован!\nПодписка на " + str(KEY_SUB_DAYS) + " дней.")
        else:
            bot.send_message(message.chat.id, "❌ Ошибка активации")
        send_menu(message.chat.id, uid)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_mirror")
    def cb_mirror(call):
        bot.answer_callback_query(call.id)
        text = (
            "🔁 СОЗДАНИЕ ЗЕРКАЛА\n\n"
            "За создание зеркала — +12 часов подписки.\n\n"
            "ИНСТРУКЦИЯ:\n"
            "1. Открой @BotFather\n"
            "2. Напиши /newbot\n"
            "3. Придумай имя\n"
            "4. Скопируй токен\n"
            "5. Отправь сюда\n\n"
            "⚠️ Токен от НОВОГО бота."
        )
        msg = bot.send_message(call.message.chat.id, text)
        bot.register_next_step_handler(msg, process_mirror)

    def process_mirror(message):
        token = message.text.strip()
        uid = message.from_user.id
        if not re.match(r"^\d{8,12}:[A-Za-z0-9_\-]{30,}$", token):
            bot.send_message(message.chat.id, "❌ Неверный формат токена")
            send_menu(message.chat.id, uid)
            return
        if create_mirror_request(uid, token):
            give_subscription(uid, 0.5)
            bot.send_message(message.chat.id, "✅ Заявка принята! +12 часов подписки.")
            if ADMIN_ID:
                try:
                    bot.send_message(ADMIN_ID, "🔁 ЗЕРКАЛО\nОт: " + str(uid))
                except Exception:
                    pass
        else:
            bot.send_message(message.chat.id, "❌ Ошибка сохранения")
        send_menu(message.chat.id, uid)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_trial")
    def cb_trial(call):
        bot.answer_callback_query(call.id)
        uid = call.from_user.id
        if not get_user(uid):
            create_user(uid, call.from_user.username, call.from_user.first_name)
        count = get_trial_count(uid)
        left = TRIAL_LIMIT - count
        if left <= 0:
            bot.send_message(call.message.chat.id, "❌ Пробная подписка использована.")
            send_menu(call.message.chat.id, uid)
            return
        give_subscription(uid, 1)
        bot.send_message(call.message.chat.id, "✅ Пробная активирована!\nОсталось: " + str(left) + " запросов.")
        send_menu(call.message.chat.id, uid)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_search")
    def cb_search(call):
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🔍 Выбери тип поиска:", call.message.chat.id, call.message.message_id, reply_markup=search_menu_inline())

    # ============ ПОИСК: НОМЕР ============
    @bot.callback_query_handler(func=lambda call: call.data == "search_phone")
    def cb_search_phone(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📱 Введи номер:")
        bot.register_next_step_handler(msg, process_search_phone)

    def process_search_phone(message):
        uid = message.from_user.id
        if not has_subscription(uid) and not has_trial_left(uid):
            bot.send_message(message.chat.id, "❌ Нет подписки.")
            send_menu(message.chat.id, uid)
            return
        if not has_subscription(uid):
            use_trial(uid)
        bot.send_message(message.chat.id, "🔍 Ищу...")
        try:
            r = phone_info(message.text.strip())
            if not r.get("valid"):
                bot.send_message(message.chat.id, "❌ Невалидный номер")
                send_menu(message.chat.id, uid)
                return
            text = (
                "📱 НОМЕР: " + r["input"] + "\n\n"
                "🌍 Страна: " + str(r.get("country") or "?") + "\n"
                "📡 Оператор: " + str(r.get("operator") or "?") + "\n"
                "🏙 Регион: " + str(r.get("region") or "?") + "\n"
                "🕐 TZ: " + str(r.get("timezone") or "?") + "\n\n"
                "🔷 Telegram: " + str(r.get("telegram") or "?") + "\n"
                "🔗 TG-ссылка: " + str(r.get("tg_link") or "?")
            )
            bot.send_message(message.chat.id, text)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
        send_menu(message.chat.id, uid)

    # ============ ПОИСК: ФИО ============
    @bot.callback_query_handler(func=lambda call: call.data == "search_fio")
    def cb_search_fio(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📛 Введи ФИО:")
        bot.register_next_step_handler(msg, process_search_fio)

    def process_search_fio(message):
        uid = message.from_user.id
        if not has_subscription(uid) and not has_trial_left(uid):
            bot.send_message(message.chat.id, "❌ Нет подписки.")
            send_menu(message.chat.id, uid)
            return
        if not has_subscription(uid):
            use_trial(uid)
        try:
            r = fio_info(message.text.strip())
            text = "📛 ФИО: " + r["input"] + "\n\n"
            if r.get("gender"): text += "⚧ Пол: " + r["gender"] + "\n"
            if r.get("nationality"): text += "🌐 Национальность: " + r["nationality"] + "\n"
            bot.send_message(message.chat.id, text)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
        send_menu(message.chat.id, uid)

    # ============ ПОИСК: НИК ============
    @bot.callback_query_handler(func=lambda call: call.data == "search_nick")
    def cb_search_nick(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "👤 Введи ник (без @):")
        bot.register_next_step_handler(msg, process_search_nick)

    def process_search_nick(message):
        uid = message.from_user.id
        if not has_subscription(uid) and not has_trial_left(uid):
            bot.send_message(message.chat.id, "❌ Нет подписки.")
            send_menu(message.chat.id, uid)
            return
        if not has_subscription(uid):
            use_trial(uid)
        try:
            r = username_info(message.text.strip())
            text = "👤 НИК: " + r["input"] + "\n\n"
            if r["platforms"]:
                for p, url in r["platforms"].items():
                    text += "✅ " + p + ": " + url + "\n"
            else:
                text += "❌ Ничего не найдено"
            bot.send_message(message.chat.id, text)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
        send_menu(message.chat.id, uid)

    # ============ ПОИСК: IP ============
    @bot.callback_query_handler(func=lambda call: call.data == "search_ip")
    def cb_search_ip(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📡 Введи IP (например 8.8.8.8):")
        bot.register_next_step_handler(msg, process_search_ip)

    def process_search_ip(message):
        uid = message.from_user.id
        if not has_subscription(uid) and not has_trial_left(uid):
            bot.send_message(message.chat.id, "❌ Нет подписки.")
            send_menu(message.chat.id, uid)
            return
        if not has_subscription(uid):
            use_trial(uid)
        bot.send_message(message.chat.id, "🔍 Ищу...")
        try:
            r = ip_info(message.text.strip())
            if not r.get("valid"):
                bot.send_message(message.chat.id, "❌ Неверный IP")
                send_menu(message.chat.id, uid)
                return
            if r.get("error"):
                bot.send_message(message.chat.id, "❌ " + r["error"])
                send_menu(message.chat.id, uid)
                return
            text = "📡 IP: " + r["input"] + "\n\n"
            if r.get("country"): text += "🌍 Страна: " + str(r["country"]) + "\n"
            if r.get("region"): text += "🏙 Регион: " + str(r["region"]) + "\n"
            if r.get("city"): text += "🏘 Город: " + str(r["city"]) + "\n"
            if r.get("lat") and r.get("lon"):
                text += "📍 Координаты: " + str(r["lat"]) + ", " + str(r["lon"]) + "\n"
                text += "🗺 Карта: https://www.google.com/maps/place/" + str(r["lat"]) + "," + str(r["lon"]) + "\n"
            if r.get("timezone"): text += "🕐 TZ: " + str(r["timezone"]) + "\n"
            if r.get("isp"): text += "📶 Провайдер: " + str(r["isp"]) + "\n"
            if r.get("as"): text += "🔢 ASN: " + str(r["as"]) + "\n"
            bot.send_message(message.chat.id, text)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
        send_menu(message.chat.id, uid)

    # ============ ПОИСК: ДОМЕН ============
    @bot.callback_query_handler(func=lambda call: call.data == "search_domain")
    def cb_search_domain(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🌐 Введи домен (example.com):")
        bot.register_next_step_handler(msg, process_search_domain)

    def process_search_domain(message):
        uid = message.from_user.id
        if not has_subscription(uid) and not has_trial_left(uid):
            bot.send_message(message.chat.id, "❌ Нет подписки.")
            send_menu(message.chat.id, uid)
            return
        if not has_subscription(uid):
            use_trial(uid)
        bot.send_message(message.chat.id, "🔍 Ищу...")
        try:
            r = domain_info(message.text.strip())
            if not r.get("valid"):
                bot.send_message(message.chat.id, "❌ Неверный домен")
                send_menu(message.chat.id, uid)
                return
            text = "🌐 ДОМЕН: " + r["domain"] + "\n\n"
            if r.get("ip"): text += "📡 IP: " + str(r["ip"]) + "\n"
            if r.get("country"): text += "🌍 Страна: " + str(r["country"]) + "\n"
            if r.get("city"): text += "🏙 Город: " + str(r["city"]) + "\n"
            if r.get("isp"): text += "📶 Провайдер: " + str(r["isp"]) + "\n"
            if r.get("registrar"): text += "📋 Регистратор: " + str(r["registrar"]) + "\n"
            if r.get("created"): text += "📅 Создан: " + str(r["created"]) + "\n"
            if r.get("expires"): text += "📅 Истекает: " + str(r["expires"]) + "\n"
            bot.send_message(message.chat.id, text)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
        send_menu(message.chat.id, uid)

    # ============ ПОИСК: EXIF ============
    @bot.callback_query_handler(func=lambda call: call.data == "search_exif")
    def cb_search_exif(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📷 Отправь фото:")
        bot.register_next_step_handler(msg, process_search_exif)

    def process_search_exif(message):
        uid = message.from_user.id
        if not has_subscription(uid) and not has_trial_left(uid):
            bot.send_message(message.chat.id, "❌ Нет подписки.")
            send_menu(message.chat.id, uid)
            return
        if not has_subscription(uid):
            use_trial(uid)
        if not message.photo:
            bot.send_message(message.chat.id, "❌ Это не фото.")
            send_menu(message.chat.id, uid)
            return
        try:
            bot.send_message(message.chat.id, "🔍 Анализирую...")
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded = bot.download_file(file_info.file_path)
            r = photo_exif(downloaded)
            if not r.get("valid"):
                bot.send_message(message.chat.id, "❌ Не удалось прочитать")
                send_menu(message.chat.id, uid)
                return
            if not r.get("has_exif"):
                bot.send_message(message.chat.id, "⚠️ EXIF данных нет")
                send_menu(message.chat.id, uid)
                return
            text = "📷 EXIF ФОТО\n\n"
            info = r.get("info", {})
            if info.get("Make"): text += "📱 Производитель: " + info["Make"] + "\n"
            if info.get("Model"): text += "📱 Модель: " + info["Model"] + "\n"
            if info.get("Software"): text += "💻 ПО: " + info["Software"] + "\n"
            if info.get("DateTime") or info.get("DateTimeOriginal"):
                text += "📅 Дата: " + str(info.get("DateTime") or info.get("DateTimeOriginal")) + "\n"
            if r.get("coords"):
                text += "\n📍 Координаты: " + str(r["coords"]) + "\n"
                text += "🗺 " + str(r.get("maps", "")) + "\n"
            bot.send_message(message.chat.id, text)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
        send_menu(message.chat.id, uid)

    # ============ ОПЛАТА ============
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
                description="OSINT бот на " + t["label"],
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
        bot.send_message(message.chat.id, "✅ Подписка активирована!")

    # ============ ГЛАВНАЯ ЛОГИКА ============
    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/"))
    def handle_data(message):
        uid = message.from_user.id
        if not is_subscribed(uid):
            send_subscribe_message(message.chat.id)
            return
        has_sub = has_subscription(uid)
        trial_left = has_trial_left(uid)
        if not has_sub and not trial_left:
            bot.send_message(message.chat.id, "❌ Нет подписки и пробные закончились.")
            send_menu(message.chat.id, uid)
            return
        if not has_sub and trial_left:
            use_trial(uid)

        text = message.text.strip()
        if not text:
            return

        msg = show_progress(message.chat.id, "[*] Обрабатываю данные...", 10)
        time.sleep(0.3)
        try:
            update_progress(message.chat.id, msg, "[*] Парсинг...", 30)
            data = parse_input(text)
            time.sleep(0.2)
            if not data["target"]:
                update_progress(message.chat.id, msg, "[!] Не нашёл данных", 100)
                send_menu(message.chat.id, uid)
                return
            update_progress(message.chat.id, msg, "[*] Рисую граф...", 60)
            buf, canvas_json = render_graph(data)
            time.sleep(0.2)
            update_progress(message.chat.id, msg, "[*] Отправляю...", 90)
            time.sleep(0.2)
            try:
                bot.delete_message(message.chat.id, msg)
            except Exception:
                pass

            bot._last_graph[uid] = buf.getvalue()
            bot._last_canvas[uid] = canvas_json
            bot._last_data[uid] = data
            buf.seek(0)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 Скачать PNG", callback_data="download_png"))
            bot.send_photo(message.chat.id, buf, reply_markup=markup)

            canvas_buf = io.BytesIO(canvas_json.encode("utf-8"))
            canvas_buf.name = "osint_graph.canvas"
            bot.send_document(message.chat.id, canvas_buf, caption="📎 Граф для Obsidian")

            send_menu(message.chat.id, uid)
        except Exception as e:
            bot.send_message(message.chat.id, "[!] Ошибка: " + str(e)[:200])
            send_menu(message.chat.id, uid)

    # ============ DOWNLOAD PNG ============
    @bot.callback_query_handler(func=lambda call: call.data == "download_png")
    def cb_download_png(call):
        bot.answer_callback_query(call.id)
        uid = call.from_user.id
        graph_data = bot._last_graph.get(uid)
        if not graph_data:
            bot.send_message(call.message.chat.id, "❌ Граф не найден")
            return
        buf = io.BytesIO(graph_data)
        buf.name = "osint_graph.png"
        bot.send_document(call.message.chat.id, buf, caption="📥 Граф в PNG")


# ============ WEBHOOK ============
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print("[ERROR] webhook: " + str(e))
    return "OK", 200


def set_webhook():
    try:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if not render_url:
            return False
        webhook_url = render_url + "/webhook"
        resp = requests.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message", "callback_query", "pre_checkout_query"]}
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
        time.sleep(3)
        print("[+] Устанавливаю webhook...")
        set_webhook()
        print("[+] Бот запущен")
        while True:
            time.sleep(60)
    else:
        while True:
            time.sleep(60)
