#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import re
import sys
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
REFERRAL_TARGET = 10
REFERRAL_BONUS_DAYS = 2

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
    "1day":    {"days": 1,     "stars": 15,  "label": "1 день"},
    "3days":   {"days": 3,     "stars": 25,  "label": "3 дня"},
    "week":    {"days": 7,     "stars": 50,  "label": "Неделя"},
    "month":   {"days": 30,    "stars": 100, "label": "Месяц"},
    "forever": {"days": 36500, "stars": 200, "label": "Навсегда"},
}
# ============ ГОРОДА МИРА ============
CITIES_WORLD = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
    "Казань", "Нижний Новгород", "Челябинск", "Самара", "Омск",
    "Ростов-на-Дону", "Уфа", "Красноярск", "Воронеж", "Пермь",
    "Волгоград", "Краснодар", "Саратов", "Тюмень", "Тольятти",
    "Ижевск", "Барнаул", "Ульяновск", "Иркутск", "Хабаровск",
    "Ярославль", "Владивосток", "Махачкала", "Томск", "Оренбург",
    "Кемерово", "Новокузнецк", "Рязань", "Астрахань", "Набережные Челны",
    "Пенза", "Липецк", "Киров", "Чебоксары", "Тула",
    "Калининград", "Балашиха", "Курск", "Севастополь", "Сочи",
    "Ставрополь", "Улан-Удэ", "Тверь", "Магнитогорск", "Иваново",
    "Брянск", "Сургут", "Белгород", "Владимир", "Нижний Тагил",
    "Архангельск", "Чита", "Симферополь", "Калуга", "Смоленск",
    "Волжский", "Курган", "Череповец", "Орёл", "Вологда",
    "Мурманск", "Якутск", "Тамбов", "Стерлитамак", "Грозный",
    "Кострома", "Петрозаводск", "Нижневартовск", "Новороссийск",
    "Йошкар-Ола", "Химки", "Таганрог", "Комсомольск-на-Амуре",
    "Сыктывкар", "Нальчик", "Нижнекамск", "Шахты", "Дзержинск",
    "Братск", "Орск", "Ангарск", "Благовещенск", "Старый Оскол",
    "Великий Новгород", "Псков", "Бийск", "Прокопьевск", "Балаково",
    "Рыбинск", "Северодвинск", "Армавир", "Подольск", "Королёв",
    "Пятигорск", "Кисловодск", "Невинномысск", "Георгиевск",
    "Норильск", "Абакан", "Кызыл", "Горно-Алтайск", "Биробиджан",
    "Магадан", "Анадырь", "Петропавловск-Камчатский", "Южно-Сахалинск",
    "Минск", "Гомель", "Могилёв", "Витебск", "Гродно", "Брест",
    "Киев", "Харьков", "Одесса", "Днепр", "Донецк", "Запорожье",
    "Львов", "Кривой Рог", "Николаев", "Мариуполь", "Луганск",
    "Винница", "Херсон", "Полтава", "Чернигов", "Черкассы",
    "Житомир", "Сумы", "Хмельницкий", "Черновцы", "Ровно",
    "Кропивницкий", "Ивано-Франковск", "Кременчуг", "Тернополь",
    "Луцк", "Белая Церковь", "Краматорск", "Мелитополь", "Ужгород",
    "Алматы", "Астана", "Шымкент", "Караганда", "Актобе", "Тараз",
    "Павлодар", "Усть-Каменогорск", "Семей", "Атырау", "Костанай",
    "Кызылорда", "Уральск", "Петропавловск", "Актау", "Темиртау",
    "Ташкент", "Самарканд", "Бухара", "Андижан", "Наманган",
    "Фергана", "Нукус", "Карши", "Термез", "Джизак",
    "Бишкек", "Ош", "Джалал-Абад", "Каракол", "Токмок",
    "Душанбе", "Худжанд", "Бохтар", "Куляб", "Истаравшан",
    "Ашхабад", "Туркменабад", "Дашогуз", "Мары", "Балканабад",
    "Баку", "Гянджа", "Сумгаит", "Мингечевир", "Ленкорань",
    "Ереван", "Гюмри", "Ванадзор", "Вагаршапат", "Абовян",
    "Тбилиси", "Батуми", "Кутаиси", "Рустави", "Гори",
    "Кишинёв", "Тирасполь", "Бельцы", "Бендеры", "Кагул",
    "Лондон", "Манчестер", "Бирмингем", "Ливерпуль", "Лидс",
    "Эдинбург", "Глазго", "Кардифф", "Белфаст",
    "Париж", "Марсель", "Лион", "Тулуза", "Ницца", "Нант",
    "Страсбург", "Бордо", "Лилль", "Ренн",
    "Берлин", "Гамбург", "Мюнхен", "Кёльн", "Франкфурт",
    "Штутгарт", "Дюссельдорф", "Дортмунд", "Эссен", "Лейпциг",
    "Дрезден", "Ганновер", "Нюрнберг", "Бремен", "Бонн",
    "Мадрид", "Барселона", "Валенсия", "Севилья", "Сарагоса",
    "Малага", "Мурсия", "Пальма", "Бильбао", "Аликанте",
    "Рим", "Милан", "Неаполь", "Турин", "Палермо",
    "Генуя", "Болонья", "Флоренция", "Бари", "Катания",
    "Венеция", "Верона", "Падуя", "Триест", "Кальяри",
    "Амстердам", "Роттердам", "Гаага", "Утрехт", "Эйндховен",
    "Брюссель", "Антверпен", "Гент", "Шарлеруа", "Льеж",
    "Вена", "Грац", "Линц", "Зальцбург", "Инсбрук",
    "Цюрих", "Женева", "Базель", "Берн", "Лозанна",
    "Стокгольм", "Гётеборг", "Мальмё", "Уппсала",
    "Осло", "Берген", "Тронхейм", "Ставангер",
    "Копенгаген", "Орхус", "Оденсе", "Ольборг",
    "Хельсинки", "Эспоо", "Тампере", "Вантаа", "Оулу",
    "Рейкьявик", "Акюрейри",
    "Дублин", "Корк", "Лимерик", "Голуэй",
    "Лиссабон", "Порту", "Брага", "Коимбра",
    "Афины", "Салоники", "Патры", "Ираклион",
    "Варшава", "Краков", "Лодзь", "Вроцлав", "Познань",
    "Гданьск", "Щецин", "Люблин", "Катовице",
    "Прага", "Брно", "Острава", "Пльзень",
    "Братислава", "Кошице", "Прешов",
    "Будапешт", "Дебрецен", "Сегед", "Мишкольц",
    "Бухарест", "Клуж-Напока", "Тимишоара", "Яссы", "Констанца",
    "София", "Пловдив", "Варна", "Бургас",
    "Белград", "Нови-Сад", "Ниш", "Крагуевац",
    "Загреб", "Сплит", "Риека", "Осиек",
    "Сараево", "Баня-Лука", "Тузла",
    "Скопье", "Битола", "Куманово",
    "Тирана", "Дуррес", "Влёра",
    "Подгорица", "Никшич",
    "Любляна", "Марибор", "Целе",
    "Вильнюс", "Каунас", "Клайпеда", "Шяуляй",
    "Рига", "Даугавпилс", "Лиепая",
    "Таллин", "Тарту", "Нарва",
    "Валлетта", "Мдина",
    "Люксембург", "Эш-сюр-Альзетт",
    "Монако", "Монте-Карло",
    "Андорра-ла-Велья",
    "Сан-Марино",
    "Ватикан",
    "Токио", "Осака", "Йокогама", "Нагоя", "Саппоро",
    "Киото", "Кобе", "Фукуока", "Хиросима", "Сэндай",
    "Сеул", "Пусан", "Инчхон", "Тэгу", "Тэджон",
    "Кванджу", "Ульсан", "Сувон",
    "Пекин", "Шанхай", "Гуанчжоу", "Шэньчжэнь", "Чэнду",
    "Ханчжоу", "Ухань", "Сиань", "Нанкин", "Тяньцзинь",
    "Чунцин", "Харбин", "Шэньян", "Далянь", "Циндао",
    "Гонконг", "Макао", "Тайбэй", "Гаосюн", "Тайчжун",
    "Сингапур", "Бангкок", "Чиангмай", "Пхукет", "Паттайя",
    "Куала-Лумпур", "Джорджтаун", "Ипох", "Джохор-Бару",
    "Джакарта", "Сурабая", "Бандунг", "Медан", "Семаранг",
    "Манила", "Кесон-Сити", "Давао", "Себу", "Замбоанга",
    "Ханой", "Хошимин", "Дананг", "Хайфон", "Кантхо",
    "Пномпень", "Сиемреап", "Баттамбанг",
    "Вьентьян", "Луангпхабанг", "Паксе",
    "Янгон", "Мандалай", "Нейпьидо",
    "Дакка", "Читтагонг", "Кхулна",
    "Коломбо", "Канди", "Галле",
    "Катманду", "Покхара", "Лалитпур",
    "Тхимпху", "Паро",
    "Нью-Дели", "Мумбаи", "Бангалор", "Хайдарабад", "Ченнаи",
    "Калькутта", "Пуна", "Ахмадабад", "Джайпур", "Лакхнау",
    "Канпур", "Нагпур", "Индаур", "Тхане", "Бхопал",
    "Исламабад", "Карачи", "Лахор", "Фейсалабад", "Равалпинди",
    "Пешавар", "Мултан", "Гуджранвала",
    "Кабул", "Кандагар", "Герат", "Мазари-Шариф",
    "Тегеран", "Мешхед", "Исфахан", "Кередж", "Тебриз",
    "Шираз", "Ахваз", "Кум", "Керманшах",
    "Багдад", "Басра", "Мосул", "Эрбиль", "Киркук",
    "Эр-Рияд", "Джидда", "Мекка", "Медина", "Даммам",
    "Дубай", "Абу-Даби", "Шарджа", "Аджман",
    "Доха", "Эль-Кувейт", "Манама", "Маскат",
    "Сана", "Аден", "Таиз",
    "Амман", "Зарка", "Ирбид",
    "Бейрут", "Триполи", "Сидон",
    "Дамаск", "Алеппо", "Хомс",
    "Иерусалим", "Тель-Авив", "Хайфа", "Беэр-Шева",
    "Анкара", "Стамбул", "Измир", "Бурса", "Адана",
    "Газиантеп", "Конья", "Анталья", "Кайсери",
    "Нью-Йорк", "Лос-Анджелес", "Чикаго", "Хьюстон", "Финикс",
    "Филадельфия", "Сан-Антонио", "Сан-Диего", "Даллас", "Сан-Хосе",
    "Остин", "Джэксонвилл", "Сан-Франциско", "Индианаполис", "Колумбус",
    "Форт-Уэрт", "Шарлотт", "Сиэтл", "Денвер", "Вашингтон",
    "Бостон", "Эль-Пасо", "Нашвилл", "Детройт", "Оклахома-Сити",
    "Портленд", "Лас-Вегас", "Мемфис", "Луисвилл", "Балтимор",
    "Милуоки", "Альбукерке", "Тусон", "Фресно", "Сакраменто",
    "Канзас-Сити", "Атланта", "Майами", "Орландо", "Тампа",
    "Новый Орлеан", "Кливленд", "Миннеаполис", "Гонолулу", "Анкоридж",
    "Торонто", "Монреаль", "Ванкувер", "Калгари", "Эдмонтон",
    "Оттава", "Виннипег", "Квебек", "Гамильтон", "Галифакс",
    "Мехико", "Гвадалахара", "Монтеррей", "Пуэбла", "Тихуана",
    "Леон", "Сьюдад-Хуарес", "Сапопан", "Мерида", "Канкун",
    "Гавана", "Сантьяго-де-Куба", "Камагуэй",
    "Санто-Доминго", "Сантьяго-де-лос-Кабальерос",
    "Порт-о-Пренс", "Кап-Аитьен",
    "Кингстон", "Монтего-Бей",
    "Гватемала", "Кесальтенанго",
    "Сан-Сальвадор", "Санта-Ана",
    "Тегусигальпа", "Сан-Педро-Сула",
    "Манагуа", "Леон",
    "Сан-Хосе", "Алахуэла",
    "Панама", "Колон",
    "Богота", "Медельин", "Кали", "Барранкилья", "Картахена",
    "Кукута", "Букараманга", "Перейра", "Санта-Марта",
    "Кито", "Гуаякиль", "Куэнка", "Санто-Доминго",
    "Лима", "Арекипа", "Трухильо", "Чиклайо", "Куско",
    "Ла-Пас", "Санта-Крус-де-ла-Сьерра", "Кочабамба",
    "Асунсьон", "Сьюдад-дель-Эсте",
    "Монтевидео", "Сальто",
    "Буэнос-Айрес", "Кордова", "Росарио", "Мендоса", "Ла-Плата",
    "Сантьяго", "Вальпараисо", "Консепсьон", "Антофагаста",
    "Сан-Паулу", "Рио-де-Жанейро", "Бразилиа", "Салвадор", "Форталеза",
    "Белу-Оризонти", "Манаус", "Куритиба", "Ресифи", "Порту-Алегри",
    "Каракас", "Маракайбо", "Валенсия", "Баркисимето",
    "Джорджтаун", "Парамарибо", "Кайенна",
    "Каир", "Александрия", "Гиза", "Шарм-эш-Шейх", "Хургада",
    "Луксор", "Асуан", "Порт-Саид", "Суэц",
    "Лагос", "Абуджа", "Кано", "Ибадан", "Порт-Харкорт",
    "Бенин-Сити", "Кадуна", "Энугу",
    "Найроби", "Момбаса", "Кисуму", "Накуру",
    "Аддис-Абеба", "Дире-Дауа", "Мекеле", "Гондэр",
    "Хартум", "Омдурман", "Порт-Судан",
    "Джуба", "Вау", "Малакаль",
    "Кампала", "Энтеббе", "Гулу",
    "Кигали", "Бутаре", "Гисеньи",
    "Бужумбура", "Гитега",
    "Додома", "Дар-эс-Салам", "Аруша", "Мванза",
    "Лусака", "Китве", "Ндола",
    "Хараре", "Булавайо", "Мутаре",
    "Лилонгве", "Блантайр", "Мзузу",
    "Мапуту", "Матола", "Бейра",
    "Антананариву", "Туамасина", "Анцирабе",
    "Порт-Луи", "Кюрпип",
    "Виктория", "Анс-Рояль",
    "Могадишо", "Харгейса", "Босасо",
    "Джибути", "Али-Сабие",
    "Асмэра", "Кэрэн", "Массауа",
    "Триполи", "Бенгази", "Мисурата",
    "Тунис", "Сфакс", "Сус",
    "Алжир", "Оран", "Константина", "Аннаба",
    "Рабат", "Касабланка", "Фес", "Марракеш", "Танжер",
    "Агадир", "Мекнес", "Уджда",
    "Дакар", "Тиес", "Сен-Луи",
    "Бамако", "Сикасо", "Мопти",
    "Уагадугу", "Бобо-Диуласо",
    "Конакри", "Нзерекоре",
    "Фритаун", "Бо", "Кенема",
    "Монровия", "Гбарнга",
    "Абиджан", "Буаке", "Далоа",
    "Аккра", "Кумаси", "Тамале",
    "Ломе", "Сокоде",
    "Котону", "Порто-Ново", "Параку",
    "Ниамей", "Зиндер", "Маради",
    "Нджамена", "Мунду", "Сарх",
    "Яунде", "Дуала", "Гаруа",
    "Либревиль", "Порт-Жантиль",
    "Браззавиль", "Пуэнт-Нуар",
    "Киншаса", "Лубумбаши", "Мбуджи-Майи", "Кисангани",
    "Банги", "Бимбо",
    "Мале", "Адду",
    "Морони", "Муцамуду",
    "Сан-Томе", "Триндади",
    "Прая", "Минделу",
    "Сидней", "Мельбурн", "Брисбен", "Перт", "Аделаида",
    "Голд-Кост", "Канберра", "Ньюкасл", "Вуллонгонг", "Хобарт",
    "Дарвин", "Кэрнс", "Таунсвилл", "Джилонг",
    "Окленд", "Веллингтон", "Крайстчерч", "Гамильтон", "Данидин",
    "Порт-Морсби", "Лаэ",
    "Сува", "Нанди",
    "Нумеа", "Мон-Дор",
    "Папеэте",
    "Апиа",
    "Нукуалофа",
    "Хониара", "Ауки",
    "Порт-Вила",
    "Паликир",
    "Маджуро",
    "Тарава",
]

CITIES_WORLD = list(set(CITIES_WORLD))
CITIES_LOWER = {c.lower(): c for c in CITIES_WORLD}
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
        sb.table("keys").update({
            "used_by": user_id,
            "used_at": datetime.now(timezone.utc).isoformat()
        }).eq("key", key).execute()
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


def has_mirror_bonus_used(user_id):
    u = get_user(user_id)
    if not u:
        return False
    return bool(u.get("mirror_bonus_used"))


def mark_mirror_bonus_used(user_id):
    try:
        sb.table("users").update({"mirror_bonus_used": True}).eq("user_id", user_id).execute()
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


def log_search(user_id, kind, query):
    try:
        sb.table("searches").insert({
            "user_id": user_id,
            "kind": kind,
            "query": query[:300],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass


# ============ РЕФЕРАЛКА ============
def get_referral_link(user_id):
    try:
        me = bot.get_me()
        return "https://t.me/" + me.username + "?start=ref_" + str(user_id)
    except Exception:
        return "https://t.me/?start=ref_" + str(user_id)


def register_referral(new_user_id, referrer_id):
    if new_user_id == referrer_id:
        return False
    try:
        u = get_user(new_user_id)
        if not u:
            return False
        if u.get("referred_by"):
            return False
        sb.table("users").update({"referred_by": referrer_id}).eq("user_id", new_user_id).execute()

        ref = get_user(referrer_id)
        if not ref:
            create_user(referrer_id, "", "")
            ref = get_user(referrer_id)
        count = (ref.get("referrals_count") or 0) + 1
        sb.table("users").update({"referrals_count": count}).eq("user_id", referrer_id).execute()

        if count >= REFERRAL_TARGET and not ref.get("referral_bonus_given"):
            give_subscription(referrer_id, REFERRAL_BONUS_DAYS)
            sb.table("users").update({"referral_bonus_given": True}).eq("user_id", referrer_id).execute()
            try:
                bot.send_message(referrer_id, "🎉 Ты пригласил " + str(REFERRAL_TARGET) + " друзей!\n+" + str(REFERRAL_BONUS_DAYS * 24) + " часов подписки начислено.")
            except Exception:
                pass
        return True
    except Exception as e:
        print("[ERROR] register_referral: " + str(e))
        return False


def get_referral_stats(user_id):
    u = get_user(user_id)
    if not u:
        return {"count": 0, "bonus_given": False, "link": get_referral_link(user_id)}
    return {
        "count": u.get("referrals_count") or 0,
        "bonus_given": bool(u.get("referral_bonus_given")),
        "link": get_referral_link(user_id),
    }


# ============ ПРОФИЛЬ ============
def get_profile(user_id):
    u = get_user(user_id)
    if not u:
        return None
    now = datetime.now(timezone.utc)
    until = u.get("subscription_until")
    sub_days_left = 0
    sub_hours_left = 0
    if until:
        try:
            dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
            if dt > now:
                delta = dt - now
                sub_days_left = delta.days
                sub_hours_left = int(delta.seconds / 3600)
        except Exception:
            pass
    return {
        "user_id": user_id,
        "username": u.get("username") or "",
        "first_name": u.get("first_name") or "",
        "sub_active": (sub_days_left > 0) or (sub_hours_left > 0),
        "sub_days_left": sub_days_left,
        "sub_hours_left": sub_hours_left,
        "trial_used": u.get("trial_used") or 0,
        "trial_left": TRIAL_LIMIT - (u.get("trial_used") or 0),
        "referrals": u.get("referrals_count") or 0,
        "referral_bonus": bool(u.get("referral_bonus_given")),
        "total_searches": u.get("total_searches") or 0,
        "mirror_bonus_used": bool(u.get("mirror_bonus_used")),
    }


def increment_search_counter(user_id):
    try:
        u = get_user(user_id)
        if not u:
            return
        cnt = (u.get("total_searches") or 0) + 1
        sb.table("users").update({"total_searches": cnt}).eq("user_id", user_id).execute()
    except Exception:
        pass


# ============ СТАТИСТИКА АДМИНА ============
def admin_stats():
    stats = {
        "users_total": 0, "users_today": 0,
        "subs_active": 0, "subs_trial": 0,
        "searches_total": 0, "searches_today": 0,
        "by_kind": {}, "top_users": [],
        "payments_total": 0, "stars_total": 0, "stars_today": 0,
        "keys_total": 0, "keys_used": 0, "keys_free": 0,
        "mirrors_total": 0, "mirrors_pending": 0,
        "referrals_total": 0,
    }
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        res = sb.table("users").select("*").execute()
        rows = res.data or []
        stats["users_total"] = len(rows)
        for u in rows:
            ca = u.get("created_at")
            if ca:
                try:
                    if datetime.fromisoformat(ca.replace("Z", "+00:00")) >= today_start:
                        stats["users_today"] += 1
                except Exception:
                    pass
            until = u.get("subscription_until")
            if until:
                try:
                    if datetime.fromisoformat(until.replace("Z", "+00:00")) > now:
                        stats["subs_active"] += 1
                except Exception:
                    pass
            if (u.get("trial_used") or 0) > 0:
                stats["subs_trial"] += 1
            if u.get("referred_by"):
                stats["referrals_total"] += 1
    except Exception as e:
        print("[ERROR] admin_stats.users: " + str(e))

    try:
        res = sb.table("searches").select("*").execute()
        rows = res.data or []
        stats["searches_total"] = len(rows)
        counter = {}
        for s in rows:
            ca = s.get("created_at")
            if ca:
                try:
                    if datetime.fromisoformat(ca.replace("Z", "+00:00")) >= today_start:
                        stats["searches_today"] += 1
                except Exception:
                    pass
            k = s.get("kind") or "?"
            counter[k] = counter.get(k, 0) + 1
        stats["by_kind"] = counter
        uc = {}
        for s in rows:
            uid = s.get("user_id")
            if uid:
                uc[uid] = uc.get(uid, 0) + 1
        stats["top_users"] = sorted(uc.items(), key=lambda x: -x[1])[:5]
    except Exception as e:
        print("[ERROR] admin_stats.searches: " + str(e))

    try:
        res = sb.table("payments").select("*").execute()
        rows = res.data or []
        stats["payments_total"] = len(rows)
        for p in rows:
            amt = p.get("amount") or 0
            stats["stars_total"] += amt
            ca = p.get("created_at")
            if ca:
                try:
                    if datetime.fromisoformat(ca.replace("Z", "+00:00")) >= today_start:
                        stats["stars_today"] += amt
                except Exception:
                    pass
    except Exception as e:
        print("[ERROR] admin_stats.payments: " + str(e))

    try:
        res = sb.table("keys").select("*").execute()
        rows = res.data or []
        stats["keys_total"] = len(rows)
        for k in rows:
            if k.get("used_by"):
                stats["keys_used"] += 1
            else:
                stats["keys_free"] += 1
    except Exception as e:
        print("[ERROR] admin_stats.keys: " + str(e))

    try:
        res = sb.table("mirrors").select("*").execute()
        rows = res.data or []
        stats["mirrors_total"] = len(rows)
        for m in rows:
            if m.get("status") == "pending":
                stats["mirrors_pending"] += 1
    except Exception as e:
        print("[ERROR] admin_stats.mirrors: " + str(e))

    return stats


def format_admin_stats(s):
    t = "📊 СТАТИСТИКА БОТА\n"
    t += "━━━━━━━━━━━━━━━━━━━━\n\n"
    t += "👥 ЮЗЕРЫ:\n"
    t += "  Всего: " + str(s["users_total"]) + "\n"
    t += "  Сегодня: +" + str(s["users_today"]) + "\n"
    t += "  Активных подписок: " + str(s["subs_active"]) + "\n"
    t += "  Триалов: " + str(s["subs_trial"]) + "\n"
    t += "  Рефералов: " + str(s["referrals_total"]) + "\n\n"
    t += "🔍 ЗАПРОСЫ:\n"
    t += "  Всего: " + str(s["searches_total"]) + "\n"
    t += "  Сегодня: +" + str(s["searches_today"]) + "\n"
    if s["by_kind"]:
        t += "  По типам:\n"
        for k, v in sorted(s["by_kind"].items(), key=lambda x: -x[1]):
            t += "    • " + str(k) + ": " + str(v) + "\n"
    if s["top_users"]:
        t += "  ТОП юзеров:\n"
        for uid, cnt in s["top_users"]:
            t += "    • " + str(uid) + " — " + str(cnt) + "\n"
    t += "\n"
    t += "💰 ПЛАТЕЖИ:\n"
    t += "  Всего: " + str(s["payments_total"]) + "\n"
    t += "  Звёзд всего: " + str(s["stars_total"]) + "\n"
    t += "  Звёзд сегодня: +" + str(s["stars_today"]) + "\n\n"
    t += "🔑 КЛЮЧИ:\n"
    t += "  Всего: " + str(s["keys_total"]) + "\n"
    t += "  Использовано: " + str(s["keys_used"]) + "\n"
    t += "  Свободно: " + str(s["keys_free"]) + "\n\n"
    t += "🔁 ЗЕРКАЛА:\n"
    t += "  Всего: " + str(s["mirrors_total"]) + "\n"
    t += "  В ожидании: " + str(s["mirrors_pending"]) + "\n"
    return t
  # ============ ОПРЕДЕЛЕНИЕ СТРАНЫ ============
def country_by_phone(phone):
    digits = re.sub(r"[^\d]", "", phone)
    if digits.startswith("7") or digits.startswith("8"):
        return "Россия/Казахстан"
    if digits.startswith("380"):
        return "Украина"
    if digits.startswith("375"):
        return "Беларусь"
    if digits.startswith("373"):
        return "Молдова"
    if digits.startswith("994"):
        return "Азербайджан"
    if digits.startswith("374"):
        return "Армения"
    if digits.startswith("995"):
        return "Грузия"
    if digits.startswith("998"):
        return "Узбекистан"
    if digits.startswith("996"):
        return "Кыргызстан"
    if digits.startswith("992"):
        return "Таджикистан"
    if digits.startswith("993"):
        return "Туркменистан"
    if digits.startswith("1"):
        return "США/Канада"
    if digits.startswith("44"):
        return "Великобритания"
    if digits.startswith("49"):
        return "Германия"
    if digits.startswith("33"):
        return "Франция"
    if digits.startswith("39"):
        return "Италия"
    if digits.startswith("34"):
        return "Испания"
    if digits.startswith("48"):
        return "Польша"
    if digits.startswith("31"):
        return "Нидерланды"
    if digits.startswith("32"):
        return "Бельгия"
    if digits.startswith("41"):
        return "Швейцария"
    if digits.startswith("43"):
        return "Австрия"
    if digits.startswith("46"):
        return "Швеция"
    if digits.startswith("47"):
        return "Норвегия"
    if digits.startswith("45"):
        return "Дания"
    if digits.startswith("358"):
        return "Финляндия"
    if digits.startswith("351"):
        return "Португалия"
    if digits.startswith("30"):
        return "Греция"
    if digits.startswith("420"):
        return "Чехия"
    if digits.startswith("421"):
        return "Словакия"
    if digits.startswith("36"):
        return "Венгрия"
    if digits.startswith("40"):
        return "Румыния"
    if digits.startswith("359"):
        return "Болгария"
    if digits.startswith("381"):
        return "Сербия"
    if digits.startswith("385"):
        return "Хорватия"
    if digits.startswith("387"):
        return "Босния"
    if digits.startswith("382"):
        return "Черногория"
    if digits.startswith("386"):
        return "Словения"
    if digits.startswith("370"):
        return "Литва"
    if digits.startswith("371"):
        return "Латвия"
    if digits.startswith("372"):
        return "Эстония"
    if digits.startswith("86"):
        return "Китай"
    if digits.startswith("81"):
        return "Япония"
    if digits.startswith("82"):
        return "Корея"
    if digits.startswith("91"):
        return "Индия"
    if digits.startswith("92"):
        return "Пакистан"
    if digits.startswith("880"):
        return "Бангладеш"
    if digits.startswith("84"):
        return "Вьетнам"
    if digits.startswith("66"):
        return "Таиланд"
    if digits.startswith("60"):
        return "Малайзия"
    if digits.startswith("65"):
        return "Сингапур"
    if digits.startswith("62"):
        return "Индонезия"
    if digits.startswith("63"):
        return "Филиппины"
    if digits.startswith("90"):
        return "Турция"
    if digits.startswith("972"):
        return "Израиль"
    if digits.startswith("971"):
        return "ОАЭ"
    if digits.startswith("966"):
        return "Саудовская Аравия"
    if digits.startswith("974"):
        return "Катар"
    if digits.startswith("965"):
        return "Кувейт"
    if digits.startswith("973"):
        return "Бахрейн"
    if digits.startswith("968"):
        return "Оман"
    if digits.startswith("20"):
        return "Египет"
    if digits.startswith("27"):
        return "ЮАР"
    if digits.startswith("234"):
        return "Нигерия"
    if digits.startswith("254"):
        return "Кения"
    if digits.startswith("55"):
        return "Бразилия"
    if digits.startswith("54"):
        return "Аргентина"
    if digits.startswith("56"):
        return "Чили"
    if digits.startswith("57"):
        return "Колумбия"
    if digits.startswith("52"):
        return "Мексика"
    if digits.startswith("61"):
        return "Австралия"
    if digits.startswith("64"):
        return "Новая Зеландия"
    return None


def country_by_email(email):
    if not email or "@" not in email:
        return None
    domain = email.split("@")[1].lower()
    tld_map = {
        ".ru": "Россия", ".ua": "Украина", ".by": "Беларусь",
        ".kz": "Казахстан", ".uz": "Узбекистан", ".kg": "Кыргызстан",
        ".tj": "Таджикистан", ".tm": "Туркменистан", ".az": "Азербайджан",
        ".am": "Армения", ".ge": "Грузия", ".md": "Молдова",
        ".de": "Германия", ".fr": "Франция", ".uk": "Великобритания",
        ".us": "США", ".it": "Италия", ".es": "Испания", ".pl": "Польша",
        ".nl": "Нидерланды", ".be": "Бельгия", ".ch": "Швейцария",
        ".at": "Австрия", ".se": "Швеция", ".no": "Норвегия",
        ".dk": "Дания", ".fi": "Финляндия", ".pt": "Португалия",
        ".gr": "Греция", ".cz": "Чехия", ".sk": "Словакия",
        ".hu": "Венгрия", ".ro": "Румыния", ".bg": "Болгария",
        ".rs": "Сербия", ".hr": "Хорватия", ".lt": "Литва",
        ".lv": "Латвия", ".ee": "Эстония",
        ".cn": "Китай", ".jp": "Япония", ".kr": "Корея",
        ".in": "Индия", ".pk": "Пакистан", ".bd": "Бангладеш",
        ".vn": "Вьетнам", ".th": "Таиланд", ".my": "Малайзия",
        ".sg": "Сингапур", ".id": "Индонезия", ".ph": "Филиппины",
        ".tr": "Турция", ".il": "Израиль", ".ae": "ОАЭ",
        ".sa": "Саудовская Аравия", ".qa": "Катар", ".kw": "Кувейт",
        ".bh": "Бахрейн", ".om": "Оман", ".eg": "Египет",
        ".za": "ЮАР", ".ng": "Нигерия", ".ke": "Кения",
        ".br": "Бразилия", ".ar": "Аргентина", ".cl": "Чили",
        ".co": "Колумбия", ".mx": "Мексика",
        ".au": "Австралия", ".nz": "Новая Зеландия",
        ".com": "США/международный", ".net": "США/международный",
        ".org": "США/международный",
    }
    for tld, country in tld_map.items():
        if domain.endswith(tld):
            return country
    return None


def country_by_city(city):
    if not city:
        return None
    cl = city.strip().lower()
    if cl in CITIES_LOWER:
        ru_cities = ["москва", "санкт-петербург", "спб", "новосибирск",
                     "екатеринбург", "казань", "нижний новгород", "челябинск",
                     "самара", "омск"]
        if cl in ru_cities:
            return "Россия"
        ua_cities = ["киев", "харьков", "одесса", "днепр", "донецк",
                     "запорожье", "львов", "николаев", "мариуполь", "луганск"]
        if cl in ua_cities:
            return "Украина"
        by_cities = ["минск", "гомель", "могилёв", "витебск", "гродно", "брест"]
        if cl in by_cities:
            return "Беларусь"
        kz_cities = ["алматы", "астана", "шымкент", "караганда", "актобе",
                     "тараз", "павлодар", "семей", "атырау", "костанай", "актау"]
        if cl in kz_cities:
            return "Казахстан"
        return CITIES_LOWER[cl]
    return None


# ============ ПАРСЕР СВОБОДНОГО ВВОДА ============
def parse_free_input(text):
    result = {
        "fio": None, "lastname": None, "firstname": None, "middlename": None,
        "dob": None, "age": None, "birth_year": None,
        "city": None, "country": None,
        "phone": None, "email": None, "nick": None,
        "extra": [],
    }

    text = text.strip()
    if not text:
        return result

    email_match = re.search(r"[\w\.\-\+]+@[\w\.\-]+\.\w+", text)
    if email_match:
        result["email"] = email_match.group(0)
        result["country"] = country_by_email(result["email"])
        text = text.replace(result["email"], " ")

    phone_match = re.search(r"(\+?\d[\d\s\-\(\)]{9,15}\d)", text)
    if phone_match:
        phone_raw = phone_match.group(0).strip()
        digits = re.sub(r"[^\d]", "", phone_raw)
        if 10 <= len(digits) <= 15:
            result["phone"] = phone_raw
            c = country_by_phone(phone_raw)
            if c:
                result["country"] = c
            text = text.replace(phone_raw, " ")

    dob_match = re.search(r"\b(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4})\b", text)
    if dob_match:
        result["dob"] = dob_match.group(1)
        text = text.replace(result["dob"], " ")

    year_match = re.search(r"\((\d{4})\)", text)
    if year_match:
        result["birth_year"] = year_match.group(1)
        result["age"] = datetime.now().year - int(result["birth_year"])
        text = text.replace(year_match.group(0), " ")

    year_match2 = re.search(r"\b(19\d{2}|20[0-2]\d)\b", text)
    if year_match2 and not result["birth_year"]:
        y = year_match2.group(1)
        age = datetime.now().year - int(y)
        if 0 <= age <= 100:
            result["birth_year"] = y
            result["age"] = age
            text = text.replace(y, " ")

    found_city = None
    for city_lower, city_real in CITIES_LOWER.items():
        if re.search(r"\b" + re.escape(city_lower) + r"\b", text.lower()):
            found_city = city_real
            break
    if found_city:
        result["city"] = found_city
        if not result["country"]:
            result["country"] = country_by_city(found_city)
        text = re.sub(re.escape(found_city), " ", text, flags=re.IGNORECASE)

    words = re.findall(r"[А-ЯЁA-Z][а-яёa-z\-]+", text)
    name_words = [w for w in words if len(w) >= 2]
    if name_words:
        if len(name_words) >= 3:
            result["lastname"] = name_words[0]
            result["firstname"] = name_words[1]
            result["middlename"] = name_words[2]
        elif len(name_words) == 2:
            result["lastname"] = name_words[0]
            result["firstname"] = name_words[1]
        else:
            result["lastname"] = name_words[0]
        result["fio"] = " ".join(name_words[:3])

    nick_match = re.search(r"@([A-Za-z0-9_]{3,32})", text)
    if nick_match:
        result["nick"] = nick_match.group(1)

    return result
  # ============ GOOGLE DORKS ============
def generate_dorks(fio=None, phone=None, dob=None, city=None, email=None, nick=None, country=None):
    dorks = []
    fio_q = '"' + fio + '"' if fio else None
    phone_q = '"' + phone + '"' if phone else None
    dob_q = '"' + dob + '"' if dob else None
    city_q = '"' + city + '"' if city else None
    email_q = '"' + email + '"' if email else None
    nick_q = '"' + nick + '"' if nick else None

    if fio_q:
        dorks += [
            "site:vk.com " + fio_q,
            "site:ok.ru " + fio_q,
            "site:t.me " + fio_q,
            "site:facebook.com " + fio_q,
            "site:instagram.com " + fio_q,
            "site:linkedin.com " + fio_q,
            "site:twitter.com " + fio_q,
            "site:x.com " + fio_q,
            "site:tiktok.com " + fio_q,
            "site:youtube.com " + fio_q,
            "site:github.com " + fio_q,
            "site:reddit.com " + fio_q,
            "site:medium.com " + fio_q,
            "site:quora.com " + fio_q,
            "site:pastebin.com " + fio_q,
            fio_q + " резюме",
            fio_q + " работа",
            fio_q + " CV",
            fio_q + " resume",
            fio_q + " biography",
            fio_q + " биография",
            fio_q + " суд",
            fio_q + " court",
            fio_q + " утечка",
            fio_q + " leak",
            fio_q + " ИНН",
            fio_q + " СНИЛС",
            fio_q + " passport",
        ]
    if phone_q:
        dorks += [
            "site:pastebin.com " + phone_q,
            "site:telegram.org " + phone_q,
            "site:vk.com " + phone_q,
            "site:ok.ru " + phone_q,
            "site:avito.ru " + phone_q,
            "site:youla.ru " + phone_q,
            "site:2gis.ru " + phone_q,
            "site:facebook.com " + phone_q,
            "site:linkedin.com " + phone_q,
            "site:twitter.com " + phone_q,
            phone_q + " объявление",
            phone_q + " утечка",
            phone_q + " leak",
            phone_q + " advertisement",
        ]
    if email_q:
        dorks += [
            email_q,
            "site:pastebin.com " + email_q,
            "site:github.com " + email_q,
            "site:linkedin.com " + email_q,
            "site:facebook.com " + email_q,
            email_q + " пароль",
            email_q + " password",
            email_q + " breach",
            email_q + " leak",
        ]
    if nick_q:
        dorks += [
            "site:vk.com " + nick_q,
            "site:t.me " + nick_q,
            "site:instagram.com " + nick_q,
            "site:github.com " + nick_q,
            "site:twitter.com " + nick_q,
            "site:tiktok.com " + nick_q,
            "site:reddit.com " + nick_q,
        ]
    if fio_q and city_q:
        dorks += [
            fio_q + " " + city_q,
            "site:vk.com " + fio_q + " " + city_q,
            "site:facebook.com " + fio_q + " " + city_q,
            "site:linkedin.com " + fio_q + " " + city_q,
        ]
    if fio_q and dob_q:
        dorks += [
            fio_q + " " + dob_q,
            fio_q + " " + dob_q + " " + (city_q or ""),
        ]
    if fio_q and phone_q:
        dorks += [
            fio_q + " " + phone_q,
            "site:vk.com " + fio_q + " " + phone_q,
        ]
    if fio_q and country:
        dorks.append(fio_q + ' "' + country + '"')

    seen = set()
    out = []
    for d in dorks:
        d = d.strip()
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


# ============ ПАРСЕР ГРАФА СВЯЗЕЙ ============
def parse_input(text):
    data = {"target": {}, "relatives": []}
    current_role = None
    current_data = {}
    first_block_saved = False

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
        "target": "TARGET", "цель": "TARGET", "жертва": "TARGET",
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
        if any(w in l for w in ["ул.", "улица", "г.", "город", "обл.", "область"]):
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
  # ============ OSINT: НОМЕР ============
def phone_advanced(phone):
    r = {"input": phone, "sections": {}}

    try:
        import phonenumbers
        from phonenumbers import carrier, geocoder
        from phonenumbers import timezone as ph_timezone
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "phonenumbers"], check=False)
        import phonenumbers
        from phonenumbers import carrier, geocoder
        from phonenumbers import timezone as ph_timezone

    phone_clean = re.sub(r"[^\d+]", "", phone)
    if phone_clean.startswith("8"):
        phone_clean = "+7" + phone_clean[1:]
    if not phone_clean.startswith("+"):
        phone_clean = "+" + phone_clean

    try:
        parsed = phonenumbers.parse(phone_clean, None)
        if phonenumbers.is_valid_number(parsed):
            r["sections"]["basic"] = {
                "valid": True,
                "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
                "country": phonenumbers.region_code_for_number(parsed),
                "operator": carrier.name_for_number(parsed, "ru") or carrier.name_for_number(parsed, "en"),
                "region": geocoder.description_for_number(parsed, "ru") or geocoder.description_for_number(parsed, "en"),
                "timezone": list(ph_timezone.time_zones_for_number(parsed)),
            }
    except Exception as e:
        r["sections"]["basic"] = {"valid": False, "error": str(e)[:60]}

    r["sections"]["socials"] = {}

    try:
        num = re.sub(r"[^\d]", "", phone_clean)
        if num.startswith("8"):
            num = "7" + num[1:]
        link = "https://t.me/+" + num
        rq = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if "tgme_page_title" in rq.text:
            m = re.search(r'<div class="tgme_page_title"[^>]*>([^<]+)</div>', rq.text)
            r["sections"]["socials"]["telegram"] = {
                "found": True,
                "name": m.group(1).strip() if m else "есть",
                "link": link,
            }
        else:
            r["sections"]["socials"]["telegram"] = {"found": False}
    except Exception:
        pass

    try:
        num = re.sub(r"[^\d]", "", phone_clean)
        wa_link = "https://wa.me/" + num
        rq = requests.get(wa_link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r["sections"]["socials"]["whatsapp"] = {
            "found": "WhatsApp" in rq.text and "not on WhatsApp" not in rq.text,
            "link": wa_link,
        }
    except Exception:
        pass

    r["sections"]["dorks"] = generate_dorks(phone=phone_clean)
    return r


# ============ OSINT: ФИО ============
def fio_advanced(raw_input):
    parsed = parse_free_input(raw_input)

    r = {
        "input": raw_input,
        "parsed": parsed,
        "sections": {},
    }

    fio = parsed.get("fio")
    parts = []
    if parsed.get("lastname"):
        parts.append(parsed["lastname"])
    if parsed.get("firstname"):
        parts.append(parsed["firstname"])
    if parsed.get("middlename"):
        parts.append(parsed["middlename"])

    if parts:
        r["sections"]["parsed"] = {
            "lastname": parsed.get("lastname"),
            "firstname": parsed.get("firstname"),
            "middlename": parsed.get("middlename"),
        }

        ml = (parsed.get("middlename") or "").lower()
        if ml.endswith("ович") or ml.endswith("евич") or ml.endswith("ич"):
            r["sections"]["parsed"]["gender"] = "Мужской"
        elif ml.endswith("овна") or ml.endswith("евна") or ml.endswith("ична") or ml.endswith("инична"):
            r["sections"]["parsed"]["gender"] = "Женский"

        l = (fio or "").lower()
        nat = None
        if "енко" in l or l.endswith("ук") or "ук " in l:
            nat = "Украинская"
        elif "ян" in l or "ian" in l:
            nat = "Армянская"
        elif "дзе" in l or "швили" in l:
            nat = "Грузинская"
        elif "ов" in l or "ев" in l or "ин" in l or "ский" in l or "цкий" in l:
            nat = "Русская/славянская"
        elif any(x in l for x in ["-оглы", "-кызы", "оглы", "кызы"]):
            nat = "Тюркская"
        if nat:
            r["sections"]["parsed"]["nationality"] = nat

    translit_map = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"
    }
    if fio:
        translit = ""
        for ch in fio.lower():
            translit += translit_map.get(ch, ch)
        r["sections"]["variants"] = {
            "original": fio,
            "translit": translit.title(),
            "yo_ye": fio.replace("ё", "е").replace("Ё", "Е"),
        }

    dorks = generate_dorks(
        fio=fio,
        phone=parsed.get("phone"),
        dob=parsed.get("dob"),
        city=parsed.get("city"),
        email=parsed.get("email"),
        nick=parsed.get("nick"),
        country=parsed.get("country"),
    )
    r["sections"]["dorks"] = dorks
    return r
  # ============ OSINT: IP ============
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
        rq = requests.get(
            "http://ip-api.com/json/" + ip,
            params={"fields": "status,message,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as"},
            timeout=10,
        )
        data = rq.json()
        if data.get("status") == "success":
            r["country"] = data.get("country")
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


# ============ OSINT: ДОМЕН ============
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
            rq = requests.get("http://ip-api.com/json/" + r["ip"], timeout=10)
            data = rq.json()
            if data.get("status") == "success":
                r["country"] = data.get("country")
                r["city"] = data.get("city")
                r["isp"] = data.get("isp")
        except Exception:
            pass
    try:
        rq = requests.get("https://rdap.org/domain/" + domain, timeout=15)
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


# ============ OSINT: EXIF ============
def _gps_to_decimal(coords, ref):
    try:
        d = float(coords[0])
        m = float(coords[1])
        s = float(coords[2])
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
            if tag in ["Make", "Model", "Software", "DateTime", "DateTimeOriginal"]:
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


# ============ OSINT: НИК ============
def username_info(nick):
    nick = nick.strip().lstrip("@")
    r = {"input": nick, "platforms": {}}
    platforms = {
        "VK": "https://vk.com/" + nick,
        "Telegram": "https://t.me/" + nick,
        "TikTok": "https://www.tiktok.com/@" + nick,
        "Instagram": "https://www.instagram.com/" + nick,
        "GitHub": "https://github.com/" + nick,
        "Twitter": "https://twitter.com/" + nick,
        "YouTube": "https://www.youtube.com/@" + nick,
        "Reddit": "https://www.reddit.com/user/" + nick,
        "Pinterest": "https://www.pinterest.com/" + nick,
        "Twitch": "https://www.twitch.tv/" + nick,
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for name, url in platforms.items():
        try:
            if name in ("Instagram", "TikTok", "Twitter"):
                rq = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
                if rq.status_code == 200:
                    if name == "Instagram" and ("Sorry, this page" in rq.text or "Page Not Found" in rq.text):
                        continue
                    if name == "TikTok" and ("Couldn't find this account" in rq.text or "page unavailable" in rq.text):
                        continue
                    if name == "Twitter" and ("This account doesn" in rq.text or "doesn't exist" in rq.text):
                        continue
                    r["platforms"][name] = url
            else:
                rq = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
                if rq.status_code == 200:
                    r["platforms"][name] = url
        except Exception:
            pass
    return r
  # ============ ПАКЕТНЫЙ ПОИСК ============
def batch_search(items, kind, max_items=20):
    results = []
    for item in items[:max_items]:
        item = item.strip()
        if not item:
            continue
        try:
            if kind == "phone":
                r = phone_advanced(item)
                basic = r["sections"].get("basic", {})
                socials = r["sections"].get("socials", {})
                results.append({
                    "input": item,
                    "valid": basic.get("valid", False),
                    "country": basic.get("country"),
                    "operator": basic.get("operator"),
                    "region": basic.get("region"),
                    "tg": socials.get("telegram", {}).get("found"),
                    "wa": socials.get("whatsapp", {}).get("found"),
                })
            elif kind == "fio":
                r = fio_advanced(item)
                p = r.get("parsed") or {}
                results.append({
                    "input": item,
                    "fio": p.get("fio"),
                    "dob": p.get("dob"),
                    "city": p.get("city"),
                    "country": p.get("country"),
                    "phone": p.get("phone"),
                    "dorks_count": len(r["sections"].get("dorks", [])),
                })
            elif kind == "nick":
                r = username_info(item)
                results.append({
                    "input": item,
                    "platforms": len(r.get("platforms", {})),
                    "list": list(r.get("platforms", {}).keys()),
                })
            elif kind == "ip":
                r = ip_info(item)
                results.append({
                    "input": item,
                    "valid": r.get("valid"),
                    "country": r.get("country"),
                    "city": r.get("city"),
                    "isp": r.get("isp"),
                })
            elif kind == "domain":
                r = domain_info(item)
                results.append({
                    "input": item,
                    "valid": r.get("valid"),
                    "ip": r.get("ip"),
                    "country": r.get("country"),
                })
        except Exception as e:
            results.append({"input": item, "error": str(e)[:80]})
    return results


def format_batch_results(results, kind):
    t = "📦 ПАКЕТНЫЙ ПОИСК — " + kind.upper() + "\n"
    t += "Обработано: " + str(len(results)) + "\n"
    t += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, r in enumerate(results, 1):
        t += str(idx) + ") " + str(r.get("input"))[:40] + "\n"
        if r.get("error"):
            t += "   ❌ " + r["error"] + "\n"
        elif kind == "phone":
            if r.get("valid"):
                t += "   ✅ " + str(r.get("country") or "?") + " / " + str(r.get("operator") or "?") + "\n"
                if r.get("region"):
                    t += "   Регион: " + str(r["region"]) + "\n"
                if r.get("tg"):
                    t += "   TG: ✅\n"
                if r.get("wa"):
                    t += "   WA: ✅\n"
            else:
                t += "   ❌ Невалидный\n"
        elif kind == "fio":
            if r.get("dob"):
                t += "   ДР: " + str(r["dob"]) + "\n"
            if r.get("city"):
                t += "   Город: " + str(r["city"]) + "\n"
            if r.get("phone"):
                t += "   Тел: " + str(r["phone"]) + "\n"
            t += "   Dorks: " + str(r.get("dorks_count", 0)) + "\n"
        elif kind == "nick":
            t += "   Платформ: " + str(r.get("platforms", 0)) + "\n"
            if r.get("list"):
                t += "   " + ", ".join(r["list"]) + "\n"
        elif kind == "ip":
            if r.get("valid"):
                t += "   " + str(r.get("country") or "?") + " / " + str(r.get("city") or "?") + "\n"
                if r.get("isp"):
                    t += "   " + str(r["isp"]) + "\n"
            else:
                t += "   ❌ Невалидный\n"
        elif kind == "domain":
            t += "   IP: " + str(r.get("ip") or "?") + " | " + str(r.get("country") or "?") + "\n"
        t += "\n"
    return t


# ============ РЕНДЕР ГРАФА ============
def render_graph(data):
    t = data.get("target") or {}
    relatives = data.get("relatives") or []

    nodes_count = 0
    if t:
        nodes_count += 1
    for rel in relatives:
        d = rel.get("data") or {}
        nodes_count += 1
        for key in ["phone", "telegram", "email", "address", "passport", "inn", "snils", "name", "dob"]:
            if d.get(key):
                nodes_count += 1

    W = 2400
    H = 1400 + max(0, (nodes_count - 10) * 80)
    if nodes_count > 30:
        W = 3200
        H = 2000 + (nodes_count - 30) * 60

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

    target_color = ROLE_COLORS["TARGET"]
    target_cx = 400
    target_cy = H // 2

    target_lines = []
    if t.get("name"):
        target_lines.append("ЦЕЛЬ: " + str(t["name"])[:35])
    else:
        target_lines.append("ЦЕЛЬ")
    if t.get("dob"):
        target_lines.append("[DR] " + str(t["dob"]))
    if t.get("phone"):
        target_lines.append("[TEL] " + str(t["phone"]))
    if t.get("telegram"):
        target_lines.append("[TG] " + str(t["telegram"]))
    if t.get("tgid"):
        target_lines.append("[ID] " + str(t["tgid"]))
    if t.get("email"):
        target_lines.append("[MAIL] " + str(t["email"]))
    if t.get("address"):
        target_lines.append("[ADR] " + str(t["address"])[:30])
    if t.get("passport"):
        target_lines.append("[PASS] " + str(t["passport"]))
    if t.get("inn"):
        target_lines.append("[INN] " + str(t["inn"]))
    if t.get("snils"):
        target_lines.append("[SNILS] " + str(t["snils"]))

    target_bbox = draw_node(target_cx, target_cy, target_lines, target_color)

    if relatives and target_bbox:
        rel_x = W - 500
        step = max(250, (H - 200) // max(len(relatives), 1))
        start_y = 200

        for idx, rel in enumerate(relatives):
            role = rel.get("role", "РОДСТВЕННИК")
            rdata = rel.get("data") or {}
            color = ROLE_COLORS.get(role, (255, 255, 255))
            rel_cy = start_y + idx * step

            rel_lines = [role]
            if rdata.get("name"):
                rel_lines.append(str(rdata["name"])[:30])
            if rdata.get("dob"):
                rel_lines.append("[DR] " + str(rdata["dob"]))
            if rdata.get("phone"):
                rel_lines.append("[TEL] " + str(rdata["phone"]))
            if rdata.get("telegram"):
                rel_lines.append("[TG] " + str(rdata["telegram"]))
            if rdata.get("email"):
                rel_lines.append("[MAIL] " + str(rdata["email"]))
            if rdata.get("address"):
                rel_lines.append("[ADR] " + str(rdata["address"])[:25])

            rel_bbox = draw_node(rel_x, rel_cy, rel_lines, color)
            draw_arrow(target_bbox[2], target_cy, rel_bbox[0], rel_cy, color)

    canvas_json = generate_obsidian_canvas(data)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf, canvas_json


# ============ OBSIDIAN CANVAS ============
def generate_obsidian_canvas(data):
    t = data.get("target") or {}
    relatives = data.get("relatives") or []
    canvas = {"nodes": [], "edges": []}

    def add_node(node_id, text, x, y, color="1"):
        canvas["nodes"].append({
            "id": node_id,
            "type": "text",
            "text": text,
            "x": x,
            "y": y,
            "width": 500,
            "height": 400,
            "color": color,
        })

    def add_edge(from_id, to_id, label=""):
        canvas["edges"].append({
            "id": "edge_" + str(len(canvas["edges"])),
            "fromNode": from_id,
            "fromSide": "right",
            "toNode": to_id,
            "toSide": "left",
            "label": label,
        })

    target_text = "**ЦЕЛЬ**\n\n"
    if t.get("name"):
        target_text += "**" + str(t["name"]) + "**\n"
    if t.get("dob"):
        target_text += "ДР: " + str(t["dob"]) + "\n"
    if t.get("phone"):
        target_text += "Тел: " + str(t["phone"]) + "\n"
    if t.get("telegram"):
        target_text += "TG: " + str(t["telegram"]) + "\n"
    if t.get("email"):
        target_text += "Email: " + str(t["email"]) + "\n"
    if t.get("address"):
        target_text += "Адрес: " + str(t["address"]) + "\n"
    if t.get("passport"):
        target_text += "Паспорт: " + str(t["passport"]) + "\n"
    if t.get("inn"):
        target_text += "ИНН: " + str(t["inn"]) + "\n"
    if t.get("snils"):
        target_text += "СНИЛС: " + str(t["snils"]) + "\n"

    add_node("target", target_text, 0, 0, "1")

    y_pos = 400
    for idx, rel in enumerate(relatives):
        role = rel.get("role", "РОДСТВЕННИК")
        rdata = rel.get("data") or {}
        rel_text = "**" + role + "**\n\n"
        if rdata.get("name"):
            rel_text += "**" + str(rdata["name"]) + "**\n"
        if rdata.get("dob"):
            rel_text += "ДР: " + str(rdata["dob"]) + "\n"
        if rdata.get("phone"):
            rel_text += "Тел: " + str(rdata["phone"]) + "\n"
        if rdata.get("telegram"):
            rel_text += "TG: " + str(rdata["telegram"]) + "\n"
        if rdata.get("email"):
            rel_text += "Email: " + str(rdata["email"]) + "\n"
        if rdata.get("address"):
            rel_text += "Адрес: " + str(rdata["address"]) + "\n"
        rel_id = "rel_" + str(idx)
        add_node(rel_id, rel_text, 600, y_pos, "2")
        add_edge("target", rel_id, role)
        y_pos += 400

    return json.dumps(canvas, ensure_ascii=False, indent=2)
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
    markup.add(
        types.InlineKeyboardButton("📦 Пакетный поиск", callback_data="menu_batch"),
        types.InlineKeyboardButton("👤 Мой профиль", callback_data="menu_profile"),
    )
    markup.add(
        types.InlineKeyboardButton("🔗 Рефералка", callback_data="menu_ref"),
        types.InlineKeyboardButton("ℹ️ Информация", callback_data="menu_info"),
    )
    if user_id and ADMIN_ID and user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("📊 Админ-статистика", callback_data="admin_stats"))
    return markup


def search_menu_inline():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📱 Номер", callback_data="search_phone"),
        types.InlineKeyboardButton("📛 ФИО (любой формат)", callback_data="search_fio"),
        types.InlineKeyboardButton("👤 Ник", callback_data="search_nick"),
        types.InlineKeyboardButton("📡 IP", callback_data="search_ip"),
        types.InlineKeyboardButton("🌐 Домен", callback_data="search_domain"),
        types.InlineKeyboardButton("📷 EXIF фото", callback_data="search_exif"),
    )
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_back"))
    return markup


def batch_menu_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📱 Номера", callback_data="batch_phone"),
        types.InlineKeyboardButton("📛 ФИО", callback_data="batch_fio"),
    )
    markup.add(
        types.InlineKeyboardButton("👤 Ники", callback_data="batch_nick"),
        types.InlineKeyboardButton("📡 IP", callback_data="batch_ip"),
    )
    markup.add(
        types.InlineKeyboardButton("🌐 Домены", callback_data="batch_domain"),
    )
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_back"))
    return markup


def subscribe_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        markup.add(types.InlineKeyboardButton(t["label"] + " — " + str(t["stars"]) + " ⭐", callback_data="buy_" + key))
    return markup


# ============ ТЕКСТЫ ============
INFO_TEXT = """Привет дорогой читатель, данный бот был создан лично Евгением Оксетеровым, на этого бота было потрачено столько сил и нервов, прошу не хейтить данного бота и поддержать автора морально, это мой первый бот созданный мною"""


EXAMPLE_FIO = """📛 РАЗДЕЛ «ФИО» — ЛЮБОЙ ФОРМАТ

Можно отправить одной строкой в любом порядке.
Парсер сам найдёт ФИО, телефон, дату рождения,
город, год, email, ник.

━━━━━━━━━━━━━━━━━━━━
📌 ПРИМЕРЫ:

1) Иванов Иван Владимирович
2) Иванов Иван Владимирович +71234567890
3) Иванов Иван Владимирович Москва
4) Иванов Иван Владимирович 12.12.1999
5) Иванов Иван Владимирович Москва +71234567890
6) Иванов Иван Владимирович 12.12.1999 +71234567890
7) Иванов Иван Владимирович (1999)
8) Иванов Иван sergey@mail.ru
9) Иванов Иван @sergey_iv
10) Иванов Иван Владимирович 12.12.1999 Москва +71234567890 sergey@mail.ru
11) Sergey Ivanov
12) Иванов Иван, Москва, +7 999 123-45-67
13) Иванов Иван (1999) Лондон
14) Ivanov Ivan 12/12/1999 London +447911123456

🌍 Поддержка всего мира: города, телефоны, email, форматы даты."""


EXAMPLE_GRAPH = """📝 ПРИМЕР ДЛЯ ГРАФА СВЯЗЕЙ

Иванов Сергей Петрович
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

папа: Иванов Пётр Сергеевич
Дата рождения: 15.03.1968
Номер: +79005554433
TG: @petr_iv

брат: Иванов Алексей Петрович
Дата рождения: 05.11.2000
TG: @alex_iv"""
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

        try:
            args = message.text.split()
            if len(args) > 1 and args[1].startswith("ref_"):
                ref_id = int(args[1].replace("ref_", ""))
                if register_referral(uid, ref_id):
                    bot.send_message(message.chat.id, "🎉 Ты пришёл по реферальной ссылке!")
        except Exception:
            pass

        if not is_subscribed(uid):
            send_subscribe_message(message.chat.id)
            return

        text = (
            "🔍 OSINT БОТ\n\n"
            "Граф связей + поиск информации.\n\n"
            "Кнопки:\n"
            "📝 Пример — образец данных\n"
            "⭐ Подписка — купить доступ\n"
            "🔑 Ключ доступа — активировать\n"
            "🔁 Создать зеркало — +12ч (1 раз)\n"
            "🎁 Пробная подписка — 5 запросов\n"
            "🔍 Поиск — OSINT\n"
            "📦 Пакетный поиск — до 20 значений\n"
            "👤 Мой профиль — твой статус\n"
            "🔗 Рефералка — 10 друзей = +48ч\n"
            "ℹ️ Информация — об авторе"
        )
        bot.send_message(message.chat.id, text, reply_markup=main_menu_inline(uid))

    @bot.message_handler(commands=["admin"])
    def cmd_admin(message):
        uid = message.from_user.id
        if not ADMIN_ID or uid != ADMIN_ID:
            bot.send_message(message.chat.id, "❌ Нет доступа")
            return
        bot.send_message(message.chat.id, "📊 Считаю статистику...")
        try:
            s = admin_stats()
            bot.send_message(message.chat.id, format_admin_stats(s))
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])

    @bot.message_handler(commands=["menu"])
    def cmd_menu(message):
        bot.send_message(message.chat.id, "Меню:", reply_markup=main_menu_inline(message.from_user.id))

    @bot.callback_query_handler(func=lambda call: call.data == "menu_back")
    def cb_back(call):
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "Меню:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu_inline(call.from_user.id),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "menu_info")
    def cb_info(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, INFO_TEXT)
        send_menu(call.message.chat.id, call.from_user.id)

    @bot.callback_query_handler(func=lambda call: call.data == "check_sub")
    def process_check_sub(call):
        uid = call.from_user.id
        if is_subscribed(uid):
            bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
            bot.send_message(call.message.chat.id, "✅ Добро пожаловать!", reply_markup=main_menu_inline(uid))
        else:
            bot.answer_callback_query(call.id, "❌ Не подписан!", snow_alert=True)

    @bot.callback_query_handler(func=lamba call: call.data == "admin=stats")
def cb_admin_stats(call):
    uid = call.from_user.id
    if not ADMIN_ID or uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Нет доступа", show_alert=True)
        return
    bot.send_message(call.message.chat.id, "📊 Считаю статистику...")
    try:
        s = admin_stats()
        bot.send_message(call.message.chat.id, format_admin_stats(s))
    except Exception as e:
        bot.send_message(call.message.chat.id, "❌ Ошибка: " + str(e)[:200])

@bot.callback_query_handler(func=lambda call: call.data == "menu_example")
def cb_example(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, EXAMPLE_GRAPH)
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
    uid = call.from_user.id
    bonus_used = has_mirror_bonus_used(uid)
    if bonus_used:
        text = (
            "🔁 СОЗДАНИЕ ЗЕРКАЛА\n\n"
            "⚠️ Бонус +12 часов уже был получен ранее.\n"
            "Повторно бонус не начисляется.\n\n"
            "Но ты всё ещё можешь создать зеркало:\n"
            "1. Открой @BotFather\n"
            "2. /newbot\n"
            "3. Скопируй токен\n"
            "4. Отправь сюда"
        )
    else:
        text = (
            "🔁 СОЗДАНИЕ ЗЕРКАЛА\n\n"
            "За создание — +12 часов подписки (только 1 раз).\n\n"
            "1. Открой @BotFather\n"
            "2. /newbot\n"
            "3. Скопируй токен\n"
            "4. Отправь сюда"
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
    bonus_used = has_mirror_bonus_used(uid)
    if create_mirror_request(uid, token):
        if not bonus_used:
            give_subscription(uid, 0.5)
            mark_mirror_bonus_used(uid)
            bot.send_message(message.chat.id, "✅ Заявка принята! +12 часов начислено (бонус за первое зеркало).")
        else:
            bot.send_message(message.chat.id, "✅ Заявка принята! Бонус не начислен — уже был получен ранее.")
        if ADMIN_ID:
            try:
                bot.send_message(ADMIN_ID, "🔁 ЗЕРКАЛО\nОт: " + str(uid) + "\nБонус: " + ("нет" if bonus_used else "да"))
            except Exception:
                pass
    else:
        bot.send_message(message.chat.id, "❌ Ошибка")
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
        bot.send_message(call.message.chat.id, "❌ Пробная использована.")
        send_menu(call.message.chat.id, uid)
        return
    give_subscription(uid, 1)
    bot.send_message(call.message.chat.id, "✅ Пробная активирована!\nОсталось: " + str(left) + " запросов.")
    send_menu(call.message.chat.id, uid)
  @bot.callback_query_handler(func=lambda call: call.data == "menu_profile")
def cb_profile(call):
    bot.answer_callback_query(call.id)
    uid = call.from_user.id
    if not get_user(uid):
        create_user(uid, call.from_user.username, call.from_user.first_name)
    p = get_profile(uid)
    if not p:
        bot.send_message(call.message.chat.id, "❌ Профиль не найден")
        return
    text = "👤 МОЙ ПРОФИЛЬ\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "🆔 ID: " + str(p["user_id"]) + "\n"
    if p.get("username"):
        text += "📛 @" + p["username"] + "\n"
    if p.get("first_name"):
        text += "👋 " + p["first_name"] + "\n"
    text += "\n"
    if p["sub_active"]:
        text += "✅ Подписка активна\n"
        text += "⏳ Осталось: " + str(p["sub_days_left"]) + " д. " + str(p["sub_hours_left"]) + " ч.\n"
    else:
        text += "❌ Подписки нет\n"
        text += "🎁 Триалов осталось: " + str(p["trial_left"]) + "/" + str(TRIAL_LIMIT) + "\n"
    text += "\n"
    text += "🔍 Всего запросов: " + str(p["total_searches"]) + "\n"
    text += "👥 Приглашено друзей: " + str(p["referrals"]) + "\n"
    if p["referral_bonus"]:
        text += "🎉 Бонус за " + str(REFERRAL_TARGET) + " друзей: получен\n"
    else:
        text += "🎯 До бонуса: " + str(max(0, REFERRAL_TARGET - p["referrals"])) + " друзей\n"
    if p["mirror_bonus_used"]:
        text += "🔁 Бонус за зеркало: получен\n"
    bot.send_message(call.message.chat.id, text)
    send_menu(call.message.chat.id, uid)

@bot.callback_query_handler(func=lambda call: call.data == "menu_ref")
def cb_ref(call):
    bot.answer_callback_query(call.id)
    uid = call.from_user.id
    if not get_user(uid):
        create_user(uid, call.from_user.username, call.from_user.first_name)
    s = get_referral_stats(uid)
    text = "🔗 РЕФЕРАЛЬНАЯ ПРОГРАММА\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "🎁 За " + str(REFERRAL_TARGET) + " приглашённых друзей — " + str(REFERRAL_BONUS_DAYS * 24) + " часов подписки!\n\n"
    text += "Твоя ссылка:\n"
    text += s["link"] + "\n\n"
    text += "👥 Приглашено: " + str(s["count"]) + "/" + str(REFERRAL_TARGET) + "\n"
    if s["bonus_given"]:
        text += "✅ Бонус уже получен\n"
    else:
        text += "🎯 Осталось: " + str(max(0, REFERRAL_TARGET - s["count"])) + " друзей\n"
    bot.send_message(call.message.chat.id, text)
    send_menu(call.message.chat.id, uid)

@bot.callback_query_handler(func=lambda call: call.data == "menu_search")
def cb_search(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🔍 Тип поиска:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=search_menu_inline(),
    )
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
    bot.send_message(message.chat.id, "🔍 Расширенный поиск...")
    try:
        r = phone_advanced(message.text.strip())
        log_search(uid, "phone", message.text.strip())
        increment_search_counter(uid)
        text = "📱 НОМЕР: " + r["input"] + "\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        basic = r["sections"].get("basic", {})
        if basic.get("valid"):
            text += "📊 ОСНОВНОЕ:\n"
            text += "  🌍 Страна: " + str(basic.get("country") or "?") + "\n"
            text += "  📡 Оператор: " + str(basic.get("operator") or "?") + "\n"
            text += "  🏙 Регион: " + str(basic.get("region") or "?") + "\n"
            text += "  🕐 TZ: " + ", ".join(basic.get("timezone", [])) + "\n\n"
        socials = r["sections"].get("socials", {})
        if socials:
            text += "🔗 СОЦСЕТИ:\n"
            tg = socials.get("telegram", {})
            if tg.get("found"):
                text += "  ✅ Telegram: " + str(tg.get("name")) + "\n"
                text += "     " + str(tg.get("link")) + "\n"
            wa = socials.get("whatsapp", {})
            if wa.get("found"):
                text += "  ✅ WhatsApp: " + str(wa.get("link")) + "\n"
            text += "\n"
        dorks = r["sections"].get("dorks", [])
        if dorks:
            text += "🔍 DORKS:\n"
            for d in dorks[:10]:
                text += "  • " + d + "\n"
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
    send_menu(message.chat.id, uid)

# ============ ПОИСК: ФИО ============
@bot.callback_query_handler(func=lambda call: call.data == "search_fio")
def cb_search_fio(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, EXAMPLE_FIO)
    msg = bot.send_message(call.message.chat.id, "📛 Отправь данные одной строкой в любом формате:")
    bot.register_next_step_handler(msg, process_search_fio)

def process_search_fio(message):
    uid = message.from_user.id
    if not has_subscription(uid) and not has_trial_left(uid):
        bot.send_message(message.chat.id, "❌ Нет подписки.")
        send_menu(message.chat.id, uid)
        return
    if not has_subscription(uid):
        use_trial(uid)
    bot.send_message(message.chat.id, "🔍 Расширенный поиск...")
    try:
        r = fio_advanced(message.text.strip())
        log_search(uid, "fio", message.text.strip())
        increment_search_counter(uid)
        text = "📛 ЗАПРОС: " + r["input"][:120] + "\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"

        parsed = r.get("parsed") or {}
        p = r["sections"].get("parsed", {})

        text += "📊 РАЗБОР:\n"
        if parsed.get("lastname"):
            text += "  Фамилия: " + parsed["lastname"] + "\n"
        if parsed.get("firstname"):
            text += "  Имя: " + parsed["firstname"] + "\n"
        if parsed.get("middlename"):
            text += "  Отчество: " + parsed["middlename"] + "\n"
        if parsed.get("dob"):
            text += "  🎂 ДР: " + parsed["dob"] + "\n"
        if parsed.get("birth_year"):
            text += "  📅 Год: " + parsed["birth_year"] + "\n"
        if parsed.get("age"):
            text += "  👤 Возраст: " + str(parsed["age"]) + "\n"
        if parsed.get("city"):
            text += "  🏙 Город: " + parsed["city"] + "\n"
        if parsed.get("country"):
            text += "  🌍 Страна: " + parsed["country"] + "\n"
        if parsed.get("phone"):
            text += "  📱 Номер: " + parsed["phone"] + "\n"
        if parsed.get("email"):
            text += "  📧 Email: " + parsed["email"] + "\n"
        if parsed.get("nick"):
            text += "  👤 Ник: @" + parsed["nick"] + "\n"
        if p.get("gender"):
            text += "  ⚧ Пол: " + p["gender"] + "\n"
        if p.get("nationality"):
            text += "  🌐 Нация: " + p["nationality"] + "\n"
        text += "\n"

        variants = r["sections"].get("variants", {})
        if variants:
            text += "🔄 ВАРИАНТЫ:\n"
            text += "  • " + variants.get("original", "") + "\n"
            text += "  • " + variants.get("translit", "") + "\n"
            if variants.get("yo_ye") != variants.get("original"):
                text += "  • " + variants.get("yo_ye", "") + "\n"
            text += "\n"

        dorks = r["sections"].get("dorks", [])
        if dorks:
            text += "🔍 GOOGLE DORKS (" + str(len(dorks)) + "):\n"
            for d in dorks[:15]:
                text += "  • " + d + "\n"
            if len(dorks) > 15:
                text += "  ... и ещё " + str(len(dorks) - 15) + "\n"
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
        log_search(uid, "nick", message.text.strip())
        increment_search_counter(uid)
        text = "👤 НИК: " + r["input"] + "\n\n"
        if r["platforms"]:
            for p, url in r["platforms"].items():
                text += "✅ " + p + ": " + url + "\n"
        else:
            text += "❌ Не найдено"
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
    send_menu(message.chat.id, uid)
  # ============ ПОИСК: IP ============
@bot.callback_query_handler(func=lambda call: call.data == "search_ip")
def cb_search_ip(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📡 Введи IP:")
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
        log_search(uid, "ip", message.text.strip())
        increment_search_counter(uid)
        if not r.get("valid"):
            bot.send_message(message.chat.id, "❌ Неверный IP")
            send_menu(message.chat.id, uid)
            return
        text = "📡 IP: " + r["input"] + "\n\n"
        if r.get("country"):
            text += "🌍 " + str(r["country"]) + "\n"
        if r.get("region"):
            text += "🏙 " + str(r["region"]) + "\n"
        if r.get("city"):
            text += "🏘 " + str(r["city"]) + "\n"
        if r.get("lat"):
            text += "📍 " + str(r["lat"]) + ", " + str(r["lon"]) + "\n"
        if r.get("isp"):
            text += "📶 " + str(r["isp"]) + "\n"
        if r.get("as"):
            text += "🔢 " + str(r["as"]) + "\n"
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
    send_menu(message.chat.id, uid)

# ============ ПОИСК: ДОМЕН ============
@bot.callback_query_handler(func=lambda call: call.data == "search_domain")
def cb_search_domain(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🌐 Введи домен:")
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
        log_search(uid, "domain", message.text.strip())
        increment_search_counter(uid)
        if not r.get("valid"):
            bot.send_message(message.chat.id, "❌ Неверный домен")
            send_menu(message.chat.id, uid)
            return
        text = "🌐 ДОМЕН: " + r["domain"] + "\n\n"
        if r.get("ip"):
            text += "📡 IP: " + str(r["ip"]) + "\n"
        if r.get("country"):
            text += "🌍 " + str(r["country"]) + "\n"
        if r.get("city"):
            text += "🏙 " + str(r["city"]) + "\n"
        if r.get("isp"):
            text += "📶 " + str(r["isp"]) + "\n"
        if r.get("registrar"):
            text += "📋 Регистратор: " + str(r["registrar"]) + "\n"
        if r.get("created"):
            text += "📅 Создан: " + str(r["created"]) + "\n"
        if r.get("expires"):
            text += "📅 Истекает: " + str(r["expires"]) + "\n"
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
        log_search(uid, "exif", "photo")
        increment_search_counter(uid)
        if not r.get("valid"):
            bot.send_message(message.chat.id, "❌ Не читается")
            send_menu(message.chat.id, uid)
            return
        if not r.get("has_exif"):
            bot.send_message(message.chat.id, "⚠️ EXIF нет")
            send_menu(message.chat.id, uid)
            return
        text = "📷 EXIF ФОТО\n\n"
        info = r.get("info", {})
        if info.get("Make"):
            text += "📱 " + info["Make"] + "\n"
        if info.get("Model"):
            text += "📱 " + info["Model"] + "\n"
        if info.get("Software"):
            text += "💻 " + info["Software"] + "\n"
        if info.get("DateTime") or info.get("DateTimeOriginal"):
            text += "📅 " + str(info.get("DateTime") or info.get("DateTimeOriginal")) + "\n"
        if r.get("coords"):
            text += "\n📍 " + str(r["coords"]) + "\n"
            text += "🗺 " + str(r.get("maps", "")) + "\n"
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
    send_menu(message.chat.id, uid)

# ============ ПАКЕТНЫЙ ПОИСК ============
@bot.callback_query_handler(func=lambda call: call.data == "menu_batch")
def cb_batch(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "📦 Пакетный поиск\n\nВыбери тип данных (до 20 значений):",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=batch_menu_inline(),
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("batch_"))
def cb_batch_kind(call):
    bot.answer_callback_query(call.id)
    kind = call.data.replace("batch_", "")
    kind_names = {
        "phone": "номера телефонов",
        "fio": "ФИО",
        "nick": "ники",
        "ip": "IP-адреса",
        "domain": "домены",
    }
    msg = bot.send_message(
        call.message.chat.id,
        "📦 Отправь " + kind_names.get(kind, "значения") + " — каждое с новой строки (до 20):",
    )
    bot.register_next_step_handler(msg, process_batch_search, kind)

def process_batch_search(message, kind):
    uid = message.from_user.id
    if not has_subscription(uid) and not has_trial_left(uid):
        bot.send_message(message.chat.id, "❌ Нет подписки.")
        send_menu(message.chat.id, uid)
        return
    if not has_subscription(uid):
        use_trial(uid)

    items = [x.strip() for x in message.text.split("\n") if x.strip()]
    if not items:
        bot.send_message(message.chat.id, "❌ Пустой список")
        send_menu(message.chat.id, uid)
        return

    bot.send_message(message.chat.id, "🔍 Обрабатываю " + str(len(items)) + " значений...")
    try:
        results = batch_search(items, kind, max_items=20)
        text = format_batch_results(results, kind)
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                bot.send_message(message.chat.id, text[i:i + 4000])
        else:
            bot.send_message(message.chat.id, text)
        log_search(uid, "batch_" + kind, str(len(items)) + " items")
        increment_search_counter(uid)
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
                start_parameter="sub",
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, "[!] " + str(e)[:150])

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
            bot.send_message(message.chat.id, "❌ Нет подписки.")
            send_menu(message.chat.id, uid)
            return
        if not has_sub and trial_left:
            use_trial(uid)

        text = message.text.strip()
        if not text:
            return

        msg = show_progress(message.chat.id, "[*] Обработка...", 10)
        time.sleep(0.3)
        try:
            update_progress(message.chat.id, msg, "[*] Парсинг...", 30)
            data = parse_input(text)
            time.sleep(0.2)
            if not data["target"]:
                update_progress(message.chat.id, msg, "[!] Нет данных", 100)
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

            log_search(uid, "graph", text[:200])
            increment_search_counter(uid)
            send_menu(message.chat.id, uid)
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Ошибка: " + str(e)[:200])
            send_menu(message.chat.id, uid)

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
            json={
                "url": webhook_url,
                "allowed_updates": [
                    "message",
                    "callback_query",
                    "pre_checkout_query",
                    "successful_payment",
                ],
            },
        )
        print("[+] Webhook: " + str(resp.json()))
        return True
    except Exception as e:
        print("[ERROR] set_webhook: " + str(e))
        return False


# ============ MAIN ============
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
