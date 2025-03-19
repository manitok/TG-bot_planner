## TG-bot_planner
# Установить зависимости
pip install -r requirements.txt

# 1-е окно терминала:
python bot.py

# 2-е окно терминала:
celery -A tasks worker

# TG-тэг бота:
@project_myplanner_bot
