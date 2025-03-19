import telebot
import pymongo
from datetime import datetime, timedelta
from tasks import send_reminder, extend_deadline, remind
from bson.objectid import ObjectId

# Настройки бота
TOKEN = "8115885272:AAHvG_9HRkGDmmlye_XdVBCbHwxfH18rcwY"
bot = telebot.TeleBot(TOKEN)

# Подключение к MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.tasks
task_collection = db['task_collection']

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Привет! С помощью этого бота ты сможешь:\n - создавать список задач с дедлайнами и выводить его,\n - получать информацию о задачах (выполнена/не выполнена, просрочена/сколько осталось до дедлайна, количество просроченных задач),\n - изменять задачи (текст задачи или статус),\n - удалять их,\n - устанавливать напоминания.\n"
        "Этот бот также уведомит тебя о том, что скоро дедлайн конкретной задачи (пришлет тебе сообщение об этом за 10 минут до дедлайна), и продлит задачу на день, если она просрочилась.\nДля получения информации по командам пиши /help"
    )

@bot.message_handler(commands=['help'])
def help(message):
    bot.reply_to(
        message,
        "Доступные команды:\n"
        "/add_task <задача> | <дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ)> – добавить задачу\n"
        "/list_tasks – список задач\n"
        "/edit_task <номер> | <новый текст> – изменить задачу\n"
        "/complete_task <номер> – отметить задачу как выполненную\n"
        "/delete_tasks <дата (ГГГГ-ММ-ДД)> - стереть задачи на конкретную дату\n"
        "/remind_me <текст напоминания> | <время напоминания (ГГГГ-ММ-ДД ЧЧ:ММ)> - создать напоминание"
    )
@bot.message_handler(commands=['add_task'])
def add_task(message):
    try:
        task_info = message.text[len('/add_task '):]
        parts = task_info.split("|")

        if len(parts) != 2:
            bot.reply_to(message, "Ошибка! Используй формат: /add_task <задача> | <дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ)>")
            return

        task_text = parts[0].strip()
        deadline = parts[1].strip()

        try:
            deadline_datetime = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
        except ValueError:
            bot.reply_to(message, "Ошибка! Неверный формат даты. Используй ГГГГ-ММ-ДД ЧЧ:ММ.")
            return

        # Сохраняем задачу в MongoDB
        task = {
            "user_id": message.chat.id,
            "text": task_text,
            "deadline": deadline_datetime,
            "status": "pending"
        }
        task_id = task_collection.insert_one(task).inserted_id  # Получаем _id задачи

        str_task_id = str(task_id)

        # Настраиваем напоминание
        reminder_time = deadline_datetime - timedelta(minutes=10)
        delay = (reminder_time - datetime.now()).total_seconds()

        if delay > 0:
            send_reminder.apply_async((message.chat.id, task_text, str_task_id), countdown=delay)

        extend_delay = (deadline_datetime - datetime.now()).total_seconds()

        if extend_delay > 0:
            extend_deadline.apply_async((message.chat.id, str_task_id), countdown=extend_delay)


        bot.reply_to(message, f"✅ Задача '{task_text}' добавлена! Дедлайн: {deadline}.")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")

@bot.message_handler(commands=['remind_me'])
def set_reminder(message):
    try:
        reminder_info = message.text[len('/remind_me '):]
        parts = reminder_info.split("|")

        if len(parts) != 2:
            bot.reply_to(message, "Ошибка! Используй формат: /remind_me <текст> | <время (ГГГГ-ММ-ДД ЧЧ:ММ)>")
            return

        reminder_text = parts[0].strip()
        reminder_time_str = parts[1].strip()

        try:
            reminder_time = datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            bot.reply_to(message, "Ошибка! Неверный формат даты. Используй ГГГГ-ММ-ДД ЧЧ:ММ.")
            return

        # Вычисляем задержку для Celery
        delay = (reminder_time - datetime.now()).total_seconds()

        if delay > 0:
            remind.apply_async((message.chat.id, reminder_text), countdown=delay)
            bot.reply_to(message, f"🔔 Напоминание установлено: '{reminder_text}' на {reminder_time_str}")
        else:
            bot.reply_to(message, "Ошибка! Время для напоминания должно быть в будущем.")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")

@bot.message_handler(commands=['list_tasks'])
def list_tasks(message):
    user_tasks = list(task_collection.find({"user_id": message.chat.id}))

    if len(user_tasks) == 0:
        bot.reply_to(message, "📭 У вас нет задач.")
        return

    now = datetime.now()
    overdue_count = 0  # Счетчик просроченных задач
    task_list = "📌 *Ваши задачи:*\n\n"

    for i, task in enumerate(user_tasks, start=1):
        status = "✅" if task['status'] == "completed" else "⏳"
        deadline = task['deadline']
        
        # Вычисляем оставшееся время до дедлайна
        time_left = deadline - now
        if time_left.total_seconds() <= 0:
            time_left_str = "❌ *Просрочена!*"
            overdue_count += 1  # Увеличиваем счетчик просроченных задач
        else:
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes = remainder // 60
            time_left_str = f"⏳ Осталось: {days} д. {hours} ч. {minutes} мин."

        task_list += (
            f"*{i}.* {task['text']}\n"
            f"   📅 Дедлайн: {deadline.strftime('%Y-%m-%d %H:%M')}\n"
            f"   {time_left_str}\n"
            f"   Статус: {status}\n\n"
        )

    # Добавляем в конец количество просроченных задач
    if overdue_count > 0:
        task_list += f"⚠ *Просрочено задач:* {overdue_count} ❗"

    bot.reply_to(message, task_list, parse_mode="Markdown")

@bot.message_handler(commands=['edit_task'])
def edit_task(message):
    try:
        task_info = message.text[len('/edit_task '):]
        parts = task_info.split("|")

        if len(parts) != 2:
            bot.reply_to(message, "Ошибка! Используй: /edit_task <номер> | <новый текст>")
            return

        task_number = int(parts[0].strip())
        new_text = parts[1].strip()

        user_tasks = list(task_collection.find({"user_id": message.chat.id}))

        if task_number < 1 or task_number > len(user_tasks):
            bot.reply_to(message, "Ошибка! Неверный номер задачи.")
            return

        task_id = user_tasks[task_number - 1]['_id']
        task_collection.update_one({"_id": task_id}, {"$set": {"text": new_text}})

        bot.reply_to(message, f"✅ Задача №{task_number} обновлена!\nНовый текст: {new_text}")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")

@bot.message_handler(commands=['complete_task'])
def complete_task(message):
    try:
        task_number = int(message.text[len('/complete_task '):].strip())

        user_tasks = list(task_collection.find({"user_id": message.chat.id}))

        if task_number < 1 or task_number > len(user_tasks):
            bot.reply_to(message, "Ошибка! Неверный номер задачи.")
            return

        task_id = user_tasks[task_number - 1]['_id']
        task_collection.update_one({"_id": task_id}, {"$set": {"status": "completed"}})

        bot.reply_to(message, f"✅ Задача №{task_number} выполнена!")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")

@bot.message_handler(commands=['delete_tasks'])
def delete_tasks(message):
    try:
        # Получаем дату из сообщения
        date_text = message.text[len('/delete_tasks '):].strip()

        # Проверяем формат даты
        try:
            target_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            bot.reply_to(message, "Ошибка! Используй формат даты: ГГГГ-ММ-ДД")
            return

        # Фильтр: ищем задачи пользователя с указанной датой
        user_id = message.chat.id
        deleted_count = task_collection.delete_many({
            "user_id": user_id,
            "deadline": {
                "$gte": datetime.combine(target_date, datetime.min.time()),  # С начала дня
                "$lt": datetime.combine(target_date, datetime.max.time())    # До конца дня
            }
        }).deleted_count

        if deleted_count > 0:
            bot.reply_to(message, f"🗑 Удалено {deleted_count} задач на {date_text}.")
        else:
            bot.reply_to(message, f"❌ У вас нет задач на {date_text}.")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")

bot.polling()
