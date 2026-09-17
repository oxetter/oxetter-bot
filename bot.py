#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import re
import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "СЮДА_ТОКЕН_БОТА")

# Цвета узлов
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
    "target":     "TARGET",
    "phone":      "TEL",
    "email":      "EMAIL",
    "vk":         "VK",
    "telegram":   "TG",
    "ok":         "OK",
    "whatsapp":   "WA",
    "address":    "ADDR",
    "passport":   "PASS",
    "inn":        "INN",
    "snils":      "SNILS",
    "car":        "CAR",
    "relative":   "ROD",
    "other":      "?",
}

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============ ПАРСЕР ============
def detect_type(line):
    """Определяет тип данных по строке."""
    l = line.lower()
    
    # Структурированный формат: PREFIX: value
    m = re.match(r"^(target|phone|email|vk|telegram|tg|ok|whatsapp|wa|address|addr|passport|pass|inn|snils|car|relative|rod)\s*:\s*(.+)$", l)
    if m:
        return m.group(1), m.group(2).strip()
    
    # Авто-определение
    if re.match(r"^\+?[\d\s\-\(\)]{10,}$", line.strip()):
        return "phone", line.strip()
    
    if re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$", line.strip()):
        return "email", line.strip()
    
    if "vk.com" in l or "vk.ru" in l:
        return "vk", line.strip()
    
    if "t.me" in l or "@" in line and len(line) < 40:
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
    
    # Если в строке есть слово "мать", "отец", "брат", "сестра" — родственник
    if any(w in l for w in ["мать", "отец", "брат", "сестра", "сын", "дочь", "жена", "муж", "бабушка", "дедушка", "тётя", "дядя", "родственник", "родня"]):
        return "relative", line.strip()
    
    return "other", line.strip()


def parse_input(text):
    """Парсит входной текст и возвращает словарь с данными."""
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
        # Первая строка без префикса = target (если это ФИО)
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


# ============ РЕНДЕР ГРАФА ============
def render_graph(data):
    """Рисует граф связей и возвращает PNG в байтах."""
    
    # Тёмный стиль
    plt.style.use("dark_background")
    
    G = nx.Graph()
    
    target = data["target"]
    G.add_node(target, label=target, ntype="target")
    
    # Позиции для узлов
    pos = {target: (0, 0)}
    
    # Узлы по группам
    all_groups = ["phone", "email", "vk", "telegram", "ok", "whatsapp", "address", "passport", "inn", "snils", "car", "relative", "other"]
    
    radius = 3
    angle_start = 0
    angle_step = 360 / max(len(all_groups), 1)
    
    node_id = 0
    for group in all_groups:
        items = data.get(group, [])
        if not items:
            continue
        
        angle = angle_start
        for item in items:
            node_id += 1
            nid = group + "_" + str(node_id)
            label = ICONS[group] + "\n" + str(item)[:30]
            G.add_node(nid, label=label, ntype=group)
            G.add_edge(target, nid, label=group)
            
            import math
            rad = math.radians(angle)
            pos[nid] = (radius * math.cos(rad), radius * math.sin(rad))
            angle += 40
        
        angle_start += angle_step
    
    # Рисование
    fig, ax = plt.subplots(figsize=(14, 10), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    
    node_colors = [COLORS.get(G.nodes[n].get("ntype", "other"), COLORS["other"]) for n in G.nodes()]
    node_sizes = [3000 if G.nodes[n].get("ntype") == "target" else 1800 for n in G.nodes()]
    
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
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    text = (
        "OSINT ВИЗУАЛИЗАТОР\n"
        "\n"
        "Кидай мне данные человека — я нарисую граф связей.\n"
        "\n"
        "ФОРМАТ 1 — свободный:\n"
        "Иванов Иван Иванович\n"
        "+79963132197\n"
        "ivan@mail.ru\n"
        "vk.com/id123456\n"
        "Москва, ул. Ленина 5\n"
        "Мать: Иванова Мария\n"
        "\n"
        "ФОРМАТ 2 — с префиксами:\n"
        "TARGET: Иванов Иван\n"
        "PHONE: +79963132197\n"
        "EMAIL: ivan@mail.ru\n"
        "VK: id123456\n"
        "ADDRESS: Москва, ул. Ленина 5\n"
        "RELATIVE: Иванова Мария (мать)\n"
        "\n"
        "ПОДДЕРЖИВАЮТСЯ:\n"
        "PHONE, EMAIL, VK, TELEGRAM/TG, OK, WHATSAPP/WA,\n"
        "ADDRESS/ADDR, PASSPORT/PASS, INN, SNILS, CAR, RELATIVE/ROD"
    )
    await message.answer(text)


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await cmd_start(message)


@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    if not text:
        await message.answer("Пустое сообщение")
        return
    
    await message.answer("[*] Обрабатываю данные...")
    
    try:
        data = parse_input(text)
        
        # Считаем сколько всего узлов
        total = sum(len(v) for k, v in data.items() if k != "target" and isinstance(v, list))
        
        if total == 0:
            await message.answer("[!] Не нашёл данных для графа. Смотри /help")
            return
        
        # Рендерим граф
        buf = render_graph(data)
        
        # Отправляем
        file = BufferedInputFile(buf.read(), filename="osint_graph.png")
        
        caption = (
            "OSINT ЦЕПОЧКА\n"
            "\n"
            "Цель: " + str(data["target"]) + "\n"
            "Узлов: " + str(total + 1) + "\n"
            "\n"
            "Телефоны: " + str(len(data["phone"])) + "\n"
            "Email: " + str(len(data["email"])) + "\n"
            "VK: " + str(len(data["vk"])) + "\n"
            "Telegram: " + str(len(data["telegram"])) + "\n"
            "Родственники: " + str(len(data["relative"])) + "\n"
        )
        
        await message.answer_photo(file, caption=caption)
    
    except Exception as e:
        await message.answer("[!] Ошибка: " + str(e)[:200])


# ============ ЗАПУСК ============
async def main():
    print("[+] Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
