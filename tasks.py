from celeryconfig import celery_app
import pymongo
import redis
import time
from datetime import datetime, timedelta
import telebot
from bson.objectid import ObjectId

TOKEN = "8115885272:AAHvG_9HRkGDmmlye_XdVBCbHwxfH18rcwY"
bot = telebot.TeleBot(TOKEN)

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client.tasks
task_collection = db['task_collection']

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

@celery_app.task
def send_reminder(chat_id, task_text, str_task_id):
    task_id = ObjectId(str_task_id)
    task = task_collection.find_one({"_id": task_id})

    if not task:
        return  # Задача не найдена, ничего не делаем

    if task["status"] == "completed":
        return  # Если задача выполнена, уведомление не отправляется

    # Если задача не выполнена, отправляем напоминание
    bot.send_message(chat_id, f"🔔 Напоминание! Скоро дедлайн задачи: {task_text}")

@celery_app.task
def extend_deadline(user_id, str_task_id):
    task_id = ObjectId(str_task_id)
    task = task_collection.find_one({"_id": task_id})

    if task and task["status"] == "pending":
        new_deadline = task["deadline"] + timedelta(days=1)
        task_collection.update_one({"_id": task_id}, {"$set": {"deadline": new_deadline}})

        bot.send_message(user_id, f"⏳ Дедлайн задачи '{task['text']}' продлен на 1 день! Новый дедлайн: {new_deadline.strftime('%Y-%m-%d %H:%M')}")

@celery_app.task
def remind(chat_id, reminder_text):
    bot.send_message(chat_id, f"🔔 Напоминание: {reminder_text}")