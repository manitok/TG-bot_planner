## TG-bot_planner
# Установить зависимости
pip install -r requirements.txt

# Установить Redis
docker run --name redis -p 6379:6379 -d redis

# 1-е окно терминала:
python bot.py

# 2-е окно терминала:
celery -A tasks worker

# TG-тэг бота:
@project_myplanner_bot

# Начать работу с ботом 
/start
