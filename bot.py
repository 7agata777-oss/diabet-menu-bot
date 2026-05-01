import asyncio
import logging 
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Токен из BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Настройка логирования
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ---- Состояния анкеты ----
class Profile(StatesGroup):
    gender = State()
    age = State()
    weight = State()
    height = State()
    activity = State()

# ---- Клавиатура для выбора пола и активности ----
gender_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]],
    resize_keyboard=True, one_time_keyboard=True
)

activity_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сидячий образ жизни")],
        [KeyboardButton(text="Лёгкая активность (1-3 дня в неделю)")],
        [KeyboardButton(text="Средняя активность (3-5 дней)")],
        [KeyboardButton(text="Высокая активность (6-7 дней)")],
        [KeyboardButton(text="Очень высокая (спортсмены)")]
    ],
    resize_keyboard=True, one_time_keyboard=True
)

# ---- База рецептов (низкий ГИ, высокое содержание клетчатки) ----
recipes = {
    "breakfast": [
        ("Овсянка на воде с ягодами (черника/малина)", 200, 6, 4, 35),
        ("Омлет из 2 яиц с помидорами и зеленью", 220, 14, 16, 3),
        ("Творог 5% с огурцом и укропом (150 г)", 180, 22, 8, 4),
        ("Цельнозерновой тост с авокадо и яйцом пашот", 250, 12, 14, 20),
    ],
    "lunch": [
        ("Суп овощной с куриной грудкой (250 мл)", 150, 18, 4, 12),
        ("Гречка отварная (150 г) с тушёной телятиной (100 г)", 350, 28, 10, 40),
        ("Филе индейки на гриле с зелёной фасолью", 320, 35, 8, 15),
        ("Рыба запечённая (треска, 150 г) с брокколи на пару", 280, 30, 7, 10),
    ],
    "dinner": [
        ("Салат из свежих овощей с тунцом в с/с (без масла)", 200, 22, 6, 10),
        ("Куриные котлеты на пару (2 шт) с тушёной капустой", 280, 25, 12, 18),
        ("Овощное рагу с фасолью и грибами", 220, 12, 6, 28),
        ("Запечённый лосось (120 г) с цветной капустой", 300, 28, 14, 8),
    ],
    "snack": [
        ("Горсть миндаля (30 г)", 180, 6, 15, 6),
        ("Яблоко (1 среднее) + 10 г грецких орехов", 150, 2, 8, 20),
        ("Нежирный греческий йогурт (150 г) с семенами чиа", 160, 12, 5, 12),
        ("Морковь (1 шт) + сельдерей с хумусом (50 г)", 140, 5, 6, 18),
        ("Творожная запеканка без сахара (100 г)", 170, 18, 5, 14),
    ]
}

# ---- Расчёт базового метаболизма (Миффлин-Сан-Жеор) ----
def calculate_bmr(gender: str, weight: float, height: float, age: int) -> float:
    if gender == "Мужской":
        return 10 * weight + 6.25 * height - 5 * age + 5
    else:
        return 10 * weight + 6.25 * height - 5 * age - 161

# Коэффициенты активности
activity_coeffs = {
    "Сидячий образ жизни": 1.2,
    "Лёгкая активность (1-3 дня в неделю)": 1.375,
    "Средняя активность (3-5 дней)": 1.55,
    "Высокая активность (6-7 дней)": 1.725,
    "Очень высокая (спортсмены)": 1.9
}

# Подбор блюд под дневную калорийность
def generate_daily_menu(total_calories: int):
    # Распределение калорий: завтрак 25%, обед 35%, ужин 25%, перекусы по 7.5%
    target = {
        "breakfast": total_calories * 0.25,
        "lunch": total_calories * 0.35,
        "dinner": total_calories * 0.25,
        "snack": total_calories * 0.075  # для одного перекуса, их будет два
    }

    menu = {}
    total_real = 0

    for meal_type, cal_target in target.items():
        # Выбираем рецепт, максимально близкий по калориям
        best = min(recipes[meal_type], key=lambda x: abs(x[1] - cal_target))
        if meal_type == "snack":
            # для перекусов берём два блюда
            best2 = min(recipes[meal_type], key=lambda x: abs(x[1] - cal_target))
            menu["snack1"] = best
            menu["snack2"] = best2
            total_real += best[1] + best2[1]
        else:
            menu[meal_type] = best
            total_real += best[1]

    return menu, round(total_real)

# Форматирование меню для сообщения
def format_menu(menu: dict, total_calories: int) -> str:
    lines = ["🍽️ **Ваше меню на день**\n"]
    meal_names = {
        "breakfast": "🌅 Завтрак",
        "lunch": "☀️ Обед",
        "dinner": "🌆 Ужин",
        "snack1": "🥜 Перекус 1",
        "snack2": "🍏 Перекус 2"
    }
    total_protein = total_fat = total_carb = 0
    for key, (name, cal, prot, fat, carb) in menu.items():
        lines.append(f"{meal_names[key]}: {name} ({cal} ккал)")
        lines.append(f"   🔹 Белки: {prot}г, Жиры: {fat}г, Углеводы: {carb}г\n")
        total_protein += prot
        total_fat += fat
        total_carb += carb

    lines.append(f"📊 **Итого за день:** {total_calories} ккал")
    lines.append(f"   Белки: {total_protein}г, Жиры: {round(total_fat,1)}г, Углеводы: {total_carb}г")
    return "\n".join(lines)

# ---- Хендлеры ----
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я помогу составить меню на день с учётом диабета 2 типа.\n"
        "Сначала задам несколько вопросов. Начнём?\n"
        "Укажите ваш пол:",
        reply_markup=gender_kb
    )
    await state.set_state(Profile.gender)

@dp.message(Profile.gender, F.text.in_(["Мужской", "Женский"]))
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Сколько вам полных лет? (введите число)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Profile.age)

@dp.message(Profile.gender)
async def invalid_gender(message: types.Message):
    await message.answer("Пожалуйста, выберите пол кнопкой ниже.", reply_markup=gender_kb)

@dp.message(Profile.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 18 or int(message.text) > 100:
        await message.answer("Введите корректный возраст (18–100 лет).")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Ваш вес в килограммах (например, 78.5):")
    await state.set_state(Profile.weight)

@dp.message(Profile.weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
        if weight < 40 or weight > 200:
            raise ValueError
    except ValueError:
        await message.answer("Введите реальный вес в кг (от 40 до 200).")
        return
    await state.update_data(weight=weight)
    await message.answer("Ваш рост в сантиметрах (например, 170):")
    await state.set_state(Profile.height)

@dp.message(Profile.height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        height = float(message.text.replace(",", "."))
        if height < 130 or height > 250:
            raise ValueError
    except ValueError:
        await message.answer("Введите рост в см (от 130 до 250).")
        return
    await state.update_data(height=height)
    await message.answer("Уровень вашей физической активности:", reply_markup=activity_kb)
    await state.set_state(Profile.activity)

@dp.message(Profile.activity, F.text.in_(activity_coeffs.keys()))
async def process_activity(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bmr = calculate_bmr(data["gender"], data["weight"], data["height"], data["age"])
    coeff = activity_coeffs[message.text]
    daily_calories = round(bmr * coeff)

    menu, total = generate_daily_menu(daily_calories)

    answer = (
        f"📋 Ваша суточная норма калорий: **{daily_calories} ккал**\n\n"
        + format_menu(menu, total)
        + "\n\n⚠️ Меню является примером и не заменяет назначения врача. "
          "При диабете обязательно контролируйте уровень сахара и консультируйтесь со специалистом."
    )
    await message.answer(answer, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Profile.activity)
async def invalid_activity(message: types.Message):
    await message.answer("Пожалуйста, выберите активность из списка кнопок.", reply_markup=activity_kb)

# Прочие сообщения
@dp.message()
async def echo(message: types.Message):
    await message.answer("Напишите /start, чтобы получить меню на сегодня.")

# ---- Запуск ----
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
