# Для установки шрифта, требуемого к генерации изображений таблицы отчетности - закиньте в корневую папку с бото файл: FONT.ttf
# Вы можете использовать этот шаблон как вам угодно, но не использовать его в злых/корыстных целях
# Примечание: Автор кода не несет отвественности, за любые действия других человек, 
# при взаимодействии с кодом, предоставляемые 
# файлы опубликованы в открытый доступ лишь с целью 
# ознакомления с функциями бота, комерческое/использование в 
# недобросовестных целях запрещается (автор отвественности не несет, 
# при нарушении пользователем данного примечания)


#Библиотеки Python, что я использовал: discord.py discord.py[voice] Pillow psutil numpy edge-tts PyNaCl vosk discord-ext-voice-recv

#Start Up Info:

if [[ -d .git ]] && [[ "0" == "1" ]]; then git pull; fi; if [[ ! -z "discord.py discord.py[voice] Pillow psutil numpy edge-tts PyNaCl vosk discord-ext-voice-recv" ]]; then pip install -U --no-cache-dir --prefix .local discord.py discord.py[voice] Pillow psutil numpy edge-tts PyNaCl vosk discord-ext-voice-recv; fi; if [[ -f /home/container/${REQUIREMENTS_FILE} ]]; then pip install -U --no-cache-dir --prefix .local -r ${REQUIREMENTS_FILE}; fi; /usr/local/bin/python /home/container/bot.py


#################################################################################################

#################################################################################################

#################################################################################################

#Outdated (Войс-чат не работает, а именно STT)


# SILICIUM AI Bot

## Файлы в контейнере
```
/home/container/
  ├── bot.py
  ├── RussoOne-Regular.ttf
  ├── mascot.png
  ├── db_context.txt
  ├── memory.txt          (создаётся автоматически)
  └── vosk-model-small-ru-0.22/  (скачивается автоматически)
```

## Настройка Gemini API
В `bot.py` найдите строку:
```python
GEMINI_KEYS = [
    "ВСТАВЬ_СВОЙ_GEMINI_API_KEY",
]
```
Получить ключ: https://aistudio.google.com/apikey

## Пакеты для панели Pterodactyl
```
discord.py Pillow psutil numpy edge-tts PyNaCl vosk discord-ext-voice-recv
```

## Голосовой чат
- Скажите `@бот пошли в войс` — бот подключится
- В войсе: произнесите «**Силициум**» + вопрос
- Скажите `@бот ливни` — бот отключится

## Цепочка голоса
`discord-ext-voice-recv BasicSink` → `PCM` → `Vosk STT` → `Gemini API` → `edge-tts` → `FFmpeg` → `войс`

## ИИ: порядок запросов
1. **Gemini** (основной) — быстрый, бесплатный лимит 15 RPM
2. **APF ключи** (резерв) — если Gemini недоступен
