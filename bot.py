#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import re
import math
import logging
import telebot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from flask import Flask
from threading import Thread

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

print("[DEBUG] Длина токена: " + str(len(BOT_TOKEN)))
print("[DEBUG] Первые 10 символов: " + str(BOT_TOKEN[:10]))

if not BOT_TOKEN:
    print("[ERROR] TELEGRAM_TOKEN пустой! Проверь Render Environment")

# Цвета
COLORS = {
    "target":     "#e74c3c",
    "phone":      "#3498db",
    "email":      "#9b59b6",
    "vk":         "#4a76a8",
    "telegram":   "#2aabee",
    "ok":         "#ee8208",
    "whatsapp":   "#25d366",
    "address":    "#16a085",
    "passport":   "#e67e22",
    "inn":        "#f39c12",
    "snils":      "#f1c40f",
    "car":        "#95a5a6",
    "relative":   "#1abc9c",
    "other":      "#7f8c8d",
}

ICONS = {
    "target":     "[ЦЕЛЬ]",
    "phone":      "[ТЕЛ]",
    "email":      "[EMAIL]",
    "vk":         "[VK]",
    "telegram":   "[TG]",
    "ok":         "[OK]",
    "whatsapp":   "[WA]",
    "address":    "[АДРЕС]",
    "passport":   "[ПАСП]",
    "inn":        "[ИНН]",
    "snils":      "[СНИЛС]",
    "car":        "[АВТО]",
    "relative":   "[РОДНЯ]",
    "other":      "[?]",
}

logging.basicConfig(level=logging.INFO)

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
    print("[DEBUG] Flask запускается на порту " + str(port))
    app.run(host="0.0.0.0", port=port)


# ============ БОТ ============
if BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("[+] Бот создан успешно")
else:
    bot = None
    print("[ERROR] Бот НЕ создан — нет токена")


# ============ ПАРСЕР ============
def detect_type(line):
    l = line.lower()

    m = re.match(
        r"^(target|phone|email|vk|telegram|tg|ok|whatsapp|wa|address|addr|passport|pass|inn|snils|car|relative|rod)\s*:\s*(.+)$",
        l)
    if m:
        return m.group(1), m.group(2).strip()

    if re.match(r"^\+?[\d\s\-\(\)]{10,}$", line.strip()):
        return "phone", line.strip()

    if re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$", line.strip()):
        return "email", line.strip()

    if "vk.com" in l or "vk.ru" in l:
        return "vk", line.strip()

    if "t.me" in l:
        return "telegram", line.strip()

    if "ok.ru" in l:
        return "ok", line.strip()

    if "wa.me" in l or "whatsapp" in l:
        return "whatsapp", line.strip()

    if any(w in l for w in ["ул.", "улица", "г.", "город", "обл.", "область", "пр.", "проспект", "д.", "дом"]):
        return "address", line.strip()

    if re.match(r"^\d{4}\s?\d{6}$", line.strip()):
        return "passport", line.strip()

    if re.match(r"^\d{12}$", line.strip()):
        return "inn", line.strip()

    if re.match(r"^\d{3}-\d{3}-\d{3}\s?\d{2}$", line.strip()):
        return "snils", line.strip()

    if re.match(r"^[А-Я]\d{3}[А-Я]{2}\d{2,3}$", line.strip()):
        return "car", line.strip()

    if any(w in l for w in ["мать", "отец", "брат", "сестра", "сын", "дочь", "жена", "муж", "бабушка", "дедушка", "тётя", "дядя", "родственник", "родня"]):
        return "relative", line.strip()

    if "@" in line and len(line) < 40:
        return "telegram", line.strip()

    return "other", line.strip()


def parse_input(text):
    data = {
        "target": None,
        "phone": [],
        "email": [],
        "vk": [],
        "telegram": [],
        "ok": [],
        "whatsapp": [],
        "address": [],
        "passport": [],
        "inn": [],
        "snils": [],
        "car": [],
        "relative": [],
        "other": [],
    }

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for i, line in enumerate(lines):
        if i == 0 and not re.match(r"^[a-z_]+\s*:", line.lower()):
            if re.match(r"^[А-ЯЁ][а-яё]+\s+[А-ЯЁ]", line) or re.match(r"^[A-Z][a-z]+\s+[A-Z]", line):
                data["target"] = line
                continue

        dtype, value = detect_type(line)

        if dtype == "target":
            data["target"] = value
        elif dtype in data:
            data[dtype].append(value)
        else:
            data["other"].append(value)

    if not data["target"]:
        data["target"] = "TARGET"

    return data


# ============ РЕНДЕР ============
def render_graph(data):
    plt.style.use("dark_background")

    G = nx.Graph()
    target = data["target"]
    G.add_node(target, label=target, ntype="target")
    pos = {target: (0, 0)}

    all_groups = ["phone", "email", "vk", "telegram", "ok", "whatsapp", "address", "passport", "inn", "snils", "car", "relative", "other"]

    node_id = 0
    angle = 0

    for group in all_groups:
        items = data.get(group, [])
        if not items:
            continue

        for item in items:
            node_id += 1
            nid = group + "_" + str(node_id)
            label = ICONS.get(group, "?") + "\n" + str(item)[:30]
            G.add_node(nid, label=label, ntype=group)
            G.add_edge(target, nid)

            rad = math.radians(angle)
            radius = 3.5
            pos[nid] = (radius * math.cos(rad), radius * math.sin(rad))
            angle += 40

    fig, ax = plt.subplots(figsize=(14, 10), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")

    node_colors = [COLORS.get(G.nodes[n].get("ntype", "other"), COLORS["other"]) for n in G.nodes()]
    node_sizes = [3500 if G.nodes[n].get("ntype") == "target" else 2000 for n in G.nodes()]

    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9, edgecolors="white", linewidths=2)
    nx.draw_networkx_edges(G, pos, width=2, alpha=0.6, edge_color="#7f8c8d")

    labels = {n: G.nodes[n].get("label", n) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=9, font_color="white", font_weight="bold")

    plt.title("OSINT ЦЕПОЧКА — " + str(target), color="white", fontsize=16, fontweight="bold", pad=20)
    plt.axis("off")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor="#0a0a0a", bbox_inches="tight")
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
            "Кидай данные — нарисую граф связей.\n"
            "\n"
            "СВОБОДНЫЙ ФОРМАТ:\n"
            "Иванов Иван Иванович\n"
            "+79963132197\n"
            "ivan@mail.ru\n"
            "vk.com/id123456\n"
            "Москва, ул. Ленина 5\n"
            "Мать: Иванова Мария\n"
            "\n"
            "С ПРЕФИКСАМИ:\n"
            "TARGET: Иванов Иван\n"
            "PHONE: +79963132197\n"
            "EMAIL: ivan@mail.ru\n"
            "VK: id123456\n"
            "ADDRESS: Москва, ул. Ленина 5\n"
            "RELATIVE: Иванова Мария (мать)"
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

        bot.send_message(message.chat.id, "[*] Обрабатываю данные...")

        try:
            data = parse_input(text)
            total = sum(len(v) for k, v in data.items() if k != "target" and isinstance(v, list))

            if total == 0:
                bot.send_message(message.chat.id, "[!] Не нашёл данных. Смотри /help")
                return

            buf = render_graph(data)

            caption = (
                "OSINT ЦЕПОЧКА\n"
                "\n"
                "Цель: " + str(data["target"]) + "\n"
                "Узлов: " + str(total + 1) + "\n"
                "\n"
                "Телефоны: " + str(len(data["phone"])) + "\n"
                "Email: " + str(len(data["email"])) + "\n"
                "VK: " + str(len(data["vk"])) + "\n"
                "TG: " + str(len(data["telegram"])) + "\n"
                "Родня: " + str(len(data["relative"]))
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
        print("[ERROR] Бот не запущен — нет токена")
        import time
        while True:
            time.sleep(60)
