#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import re
import math
import telebot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import networkx as nx
from flask import Flask
from threading import Thread

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

print("[DEBUG] Длина токена: " + str(len(BOT_TOKEN)))

if not BOT_TOKEN:
    print("[ERROR] TELEGRAM_TOKEN пустой")

# ============ ЦВЕТА ============
BG_COLOR = "#0a0a0a"
NODE_BG = "#0a0a0a"
NODE_BORDER = "#ffffff"
NODE_BORDER_TARGET = "#e74c3c"
TEXT_COLOR = "#ffffff"
ARROW_COLOR = "#ffffff"

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


# ============ БОТ ============
if BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("[+] Бот создан")
else:
    bot = None
    print("[ERROR] Бот НЕ создан")


# ============ ПАРСЕР ============
ROLES = ["TARGET", "MOTHER", "FATHER", "BROTHER", "SISTER", "SON", "DAUGHTER", "WIFE", "HUSBAND", "GRANDMOTHER", "GRANDFATHER", "RELATIVE"]
ROLE_LABELS = {
    "TARGET": "ЦЕЛЬ",
    "MOTHER": "МАМА",
    "FATHER": "ПАПА",
    "BROTHER": "БРАТ",
    "SISTER": "СЕСТРА",
    "SON": "СЫН",
    "DAUGHTER": "ДОЧЬ",
    "WIFE": "ЖЕНА",
    "HUSBAND": "МУЖ",
    "GRANDMOTHER": "БАБУШКА",
    "GRANDFATHER": "ДЕДУШКА",
    "RELATIVE": "РОДСТВЕННИК",
}


def parse_input(text):
    """Парсит данные с префиксами."""
    data = {
        "target": {},
        "relatives": []
    }

    current_relative = None
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines:
        m = re.match(r"^([A-Z_]+)\s*:\s*(.+)$", line)
        if not m:
            continue

        key = m.group(1).upper()
        value = m.group(2).strip()

        if key == "TARGET":
            data["target"]["name"] = value
        elif key == "DOB":
            data["target"]["dob"] = value
        elif key == "PHONE":
            data["target"]["phone"] = value
        elif key == "TG":
            data["target"]["tg"] = value
        elif key == "TGID":
            data["target"]["tgid"] = value
        elif key == "VK":
            data["target"]["vk"] = value
        elif key == "OK":
            data["target"]["ok"] = value
        elif key == "WHATSAPP":
            data["target"]["whatsapp"] = value
        elif key == "ADDRESS":
            data["target"]["address"] = value
        elif key == "PASSPORT":
            data["target"]["passport"] = value
        elif key == "INN":
            data["target"]["inn"] = value
        elif key == "SNILS":
            data["target"]["snils"] = value
        elif key == "CAR":
            data["target"]["car"] = value
        elif key in ROLES and key != "TARGET":
            current_relative = {
                "role": key,
                "label": ROLE_LABELS.get(key, key),
                "data": {"name": value}
            }
            data["relatives"].append(current_relative)
        elif key.startswith("MOTHER_") or key.startswith("FATHER_") or key.startswith("BROTHER_") or key.startswith("SISTER_") or key.startswith("SON_") or key.startswith("DAUGHTER_") or key.startswith("WIFE_") or key.startswith("HUSBAND_"):
            parts = key.split("_", 1)
            role = parts[0]
            field = parts[1].lower() if len(parts) > 1 else "value"
            for rel in data["relatives"]:
                if rel["role"] == role:
                    rel["data"][field] = value
                    break
        else:
            if current_relative:
                current_relative["data"][key.lower()] = value

    return data


# ============ РЕНДЕР ============
def render_graph(data):
    """Рисует граф в стиле образца."""
    fig, ax = plt.subplots(figsize=(18, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # Точки на фоне
    for x in range(0, 19):
        for y in range(0, 11):
            ax.plot(x, y, marker=".", color="#1a1a1a", markersize=2, zorder=0)

    def draw_node(x, y, w, h, title, lines, is_target=False):
        """Рисует узел — прямоугольник со скруглёнными углами."""
        border_color = NODE_BORDER_TARGET if is_target else NODE_BORDER
        lw = 2.5 if is_target else 1.2

        box = FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.15",
            linewidth=lw,
            edgecolor=border_color,
            facecolor=NODE_BG,
            zorder=2
        )
        ax.add_patch(box)

        # Заголовок
        title_color = NODE_BORDER_TARGET if is_target else NODE_BORDER
        ax.text(x, y + h / 2 - 0.25, title, ha="center", va="top",
                color=title_color, fontsize=9, fontweight="bold", zorder=3)

        # Строки
        for i, line in enumerate(lines):
            ax.text(x, y + h / 2 - 0.55 - i * 0.22, line, ha="center", va="top",
                    color=TEXT_COLOR, fontsize=8, zorder=3)

        return (x, y, w, h)

    def draw_arrow(x1, y1, x2, y2):
        """Рисует стрелку между узлами."""
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.2,
            color=ARROW_COLOR,
            zorder=1
        )
        ax.add_patch(arrow)

    # ============ ЦЕЛЬ ============
    t = data["target"]
    t_lines = []
    if t.get("dob"):
        t_lines.append(t["dob"])
    if t.get("tg"):
        t_lines.append(t["tg"])
    if t.get("tgid"):
        t_lines.append("ID: " + t["tgid"])
    if t.get("phone"):
        t_lines.append(t["phone"])
    if t.get("vk"):
        t_lines.append(t["vk"])
    if t.get("ok"):
        t_lines.append("OK: " + t["ok"])
    if t.get("whatsapp"):
        t_lines.append("WA: " + t["whatsapp"])
    if t.get("address"):
        t_lines.append(t["address"])
    if t.get("passport"):
        t_lines.append("ПАСПОРТ: " + t["passport"])
    if t.get("inn"):
        t_lines.append("ИНН: " + t["inn"])
    if t.get("snils"):
        t_lines.append("СНИЛС: " + t["snils"])
    if t.get("car"):
        t_lines.append("АВТО: " + t["car"])

    target_h = 0.55 + len(t_lines) * 0.22 + 0.15
    draw_node(3.5, 5, 4.5, target_h, "ЦЕЛЬ: " + t.get("name", "?"), t_lines, is_target=True)

    # ============ РОДСТВЕННИКИ ============
    relatives = data["relatives"]
    n = len(relatives)

    if n > 0:
        # Распределяем по вертикали справа
        total_height = 8.5
        step = total_height / max(n, 1)
        start_y = 9 - step / 2

        for i, rel in enumerate(relatives):
            rel_y = start_y - i * step
            rel_x = 12

            r_lines = []
            for k, v in rel["data"].items():
                if k == "name":
                    continue
                if v and str(v).strip():
                    label = k.upper() + ": " + str(v)
                    r_lines.append(label)

            rel_h = 0.55 + len(r_lines) * 0.22 + 0.15
            draw_node(rel_x, rel_y, 4.5, rel_h, rel["label"] + ": " + rel["data"].get("name", "?"), r_lines, is_target=False)

            # Стрелка от цели к родственнику
            draw_arrow(5.75, 5, 9.75, rel_y)

    plt.title("OSINT ЦЕПОЧКА", color="white", fontsize=14, fontweight="bold", pad=10)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=BG_COLOR, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf


# ============ ОБРАБОТЧИКИ ============
if bot:
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        text = (
            "OSINT ВИЗУАЛИЗАТОР\n"
            "\n"
            "Кидай данные с префиксами — построю граф.\n"
            "\n"
            "ПРИМЕР:\n"
            "TARGET: Иванов Иван\n"
            "DOB: 01.01.2000\n"
            "PHONE: +79963132197\n"
            "TG: @ivan\n"
            "TGID: 123456789\n"
            "VK: vk.com/id123456\n"
            "MOTHER: Иванова Мария\n"
            "MOTHER_DOB: 15.05.1970\n"
            "MOTHER_PHONE: +7996...\n"
            "MOTHER_PASSPORT: 4515 123456\n"
            "MOTHER_INN: 770123456789\n"
            "MOTHER_ADDRESS: Москва, ул. ...\n"
            "FATHER: Иванов Пётр\n"
            "FATHER_PHONE: +7996...\n"
        )
        bot.send_message(message.chat.id, text)

    @bot.message_handler(commands=["help"])
    def cmd_help(message):
        cmd_start(message)

    @bot.message_handler(func=lambda m: True)
    def handle_text(message):
        if not message.text:
            return

        text = message.text.strip()
        if not text:
            return

        bot.send_message(message.chat.id, "[*] Строю граф...")

        try:
            data = parse_input(text)

            if not data["target"].get("name"):
                bot.send_message(message.chat.id, "[!] Нет TARGET. Смотри /help")
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
        print("[ERROR] Бот не запущен")
        import time
        while True:
            time.sleep(60)
