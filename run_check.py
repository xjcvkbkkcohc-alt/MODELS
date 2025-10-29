import os
import requests
import logging
import time

# Настройка логирования, чтобы видеть ошибки в Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
# (Эти переменные мы добавим в Render)

# URL, откуда мы берем ID игроков
ID_SOURCE_URL = os.environ.get('ID_SOURCE_URL') 
# Вебхук, куда отправляем итоговый отчет
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

# Шаблон API Roblox
ROBLOX_API_URL_TEMPLATE = "https://apis.roblox.com/toolbox-service/v1/marketplace/10?limit=100&pageNumber=0&keyword=&creatorType=1&creatorTargetId={}&includeOnlyVerifiedCreators=false"


def get_ids_from_source(url):
    """
    Получает JSON по URL и возвращает список ID из "PlayersIds".
    """
    if not url:
        logging.critical("ID_SOURCE_URL не установлен! Не могу найти ID.")
        return []
        
    logging.info(f"Загружаю ID из: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Вызовет ошибку, если URL не 200 OK
        
        data = response.json()
        id_list = data.get("PlayersIds", [])
        
        if not id_list:
            logging.warning("JSON получен, но ключ 'PlayersIds' пуст или отсутствует.")
            return []
            
        logging.info(f"Найдено {len(id_list)} ID игроков.")
        return id_list
        
    except requests.RequestException as e:
        logging.error(f"Не удалось получить JSON с ID: {e}")
        return []
    except Exception as e:
        logging.error(f"Ошибка парсинга JSON (файл по URL битый?): {e}")
        return []

def get_asset_count(creator_id):
    """
    Получает 'totalResults' (количество ассетов) для одного ID.
    """
    try:
        # Подставляем ID в шаблон URL
        url = ROBLOX_API_URL_TEMPLATE.format(creator_id)
        response = requests.get(url, timeout=10)
        
        # Roblox API может вернуть 400, если ID плохой, это нормально
        if response.status_code != 200:
            logging.warning(f"  ID {creator_id}: Неудачный запрос к Roblox API (Статус: {response.status_code})")
            return 0

        data = response.json()
        total = data.get("totalResults", 0)
        
        logging.info(f"  ID {creator_id}: Найдено {total} ассетов.")
        return total
        
    except Exception as e:
        logging.error(f"  ID {creator_id}: Критическая ошибка при запросе к Roblox API: {e}")
        return 0 # Возвращаем 0, чтобы не сломать общий подсчет

def send_discord_report(total_assets, accounts_checked):
    """
    Отправляет итоговый embed в Discord.
    """
    if not DISCORD_WEBHOOK_URL:
        logging.error("DISCORD_WEBHOOK_URL не установлен. Не могу отправить отчет.")
        return

    logging.info(f"Отправляю отчет в Discord: Всего {total_assets} ассетов.")
    
    # Собираем красивый embed
    embed = {
        "title": "📊 Общий подсчет ассетов",
        "description": "Сумма всех `totalResults` по списку ID.",
        "color": 5814783, # Фиолетовый
        "fields": [
            {
                "name": "Всего найдено ассетов",
                "value": f"**{total_assets:,}**", # Форматирование 1,234,567
                "inline": True
            },
            {
                "name": "ID проверено",
                "value": f"**{accounts_checked}**",
                "inline": True
            }
        ],
        "footer": {
            "text": "Obsidian Asset Counter (Cron Job)"
        }
    }
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Отчет в Discord успешно отправлен.")
    except Exception as e:
        logging.error(f"Не удалось отправить отчет в Discord: {e}")

# --- ГЛАВНЫЙ БЛОК ИСПОЛНЕНИЯ ---
if __name__ == "__main__":
    logging.info("---= Запуск 5-минутной проверки ассетов =---")
    
    # Шаг 1: Получаем ID
    creator_ids = get_ids_from_source(ID_SOURCE_URL)
    
    if not creator_ids:
        logging.warning("ID не найдены. Проверка завершена.")
        exit() # Выходим из скрипта

    # Шаг 2: Считаем ассеты для каждого ID
    grand_total = 0
    for creator_id in creator_ids:
        grand_total += get_asset_count(creator_id)
        time.sleep(0.5) # Пауза 0.5 сек, чтобы не "заспамить" Roblox API
        
    # Шаг 3: Отправляем итоговый отчет
    send_discord_report(grand_total, len(creator_ids))
    
    logging.info("---= Проверка успешно завершена =---")
