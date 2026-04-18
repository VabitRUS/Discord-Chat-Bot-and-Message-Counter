import discord
import asyncio
import io
import psutil
import re
import tempfile
import time as _time
from pathlib import Path
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# ═══════════════════════════════════════════════════
#  СТАТУС — ВСПОМОГАТЕЛЬНЫЙ МОДУЛЬ
# ═══════════════════════════════════════════════════

import socket
import time
import os as _os
from collections import deque

import time

# История использования команд для графика (хранит timestamp)
def uptime_str():
    sec = int(time.time() - _bot_start)
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m, s   = divmod(rem, 60)
    parts  = []
    if d: parts.append(f"{d}д")
    if h: parts.append(f"{h}ч")
    if m: parts.append(f"{m}м")
    parts.append(f"{s}с")
    return " ".join(parts)

async def tcp_ping_ms(host: str, port: int = 443) -> int | None:
    """Measure TCP connection latency in ms."""
    try:
        loop = asyncio.get_event_loop()
        t0   = loop.time()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=2.0
        )
        ms = round((loop.time() - t0) * 1000)
        writer.close()
        return ms
    except Exception:
        return None

def generate_status_image(
    ping_ff: int | None,
    ping_dc: int | None,
    discord_ws_ms: int,
    cpu: float,
    ram_used: float,
    ram_total: float,
    disk_used: float,
    disk_total: float,
    uptime: str,
    total_reports: int,
    cmd_history: deque,
    font_path: str,
) -> io.BytesIO:

    # ── Palette ──
    BG      = (11, 11, 17)
    CARD    = (19, 19, 29)
    LINE    = (36, 36, 52)
    WHITE   = (228, 228, 238)
    MUTED   = (105, 105, 130)
    GOLD    = (255, 195, 40)
    GREEN   = (55,  200, 105)
    RED     = (225,  62,  62)
    BLUE    = (65,  145, 255)
    PURPLE  = (155, 100, 255)
    ORANGE  = (255, 140,  40)

    W, H  = 860, 520
    PAD   = 20
    CW    = (W - 3*PAD) // 2   # column width

    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    def ft(size, bold=True):
        suffix = "-Regular.ttf" if not bold else "-Regular.ttf"
        try:    return ImageFont.truetype(font_path, size)
        except: return ImageFont.load_default()

    fT  = ft(17)
    fH  = ft(13)
    fN  = ft(12)
    fS  = ft(10)
    fXL = ft(22)

    def card(x0,y0,x1,y1,r=8):
        d.rounded_rectangle([x0,y0,x1,y1], radius=r, fill=CARD, outline=LINE, width=1)

    def bar(x0,y,w,pct,color):
        bh = 10
        d.rounded_rectangle([x0,y,x0+w,y+bh], radius=5, fill=(22,22,35))
        fill_w = int(w * pct / 100)
        if fill_w > 0:
            d.rounded_rectangle([x0,y,x0+fill_w,y+bh], radius=5, fill=color)
            sh = max(2, bh//3)
            sc = tuple(min(255,c+60) for c in color)
            d.rounded_rectangle([x0,y,x0+fill_w,y+sh], radius=5, fill=sc)

    def ping_color(ms):
        if ms is None: return RED
        if ms < 80:    return GREEN
        if ms < 200:   return ORANGE
        return RED

    def ping_label(ms):
        return f"{ms} ms" if ms is not None else "недоступен"

    # ══ HEADER ══
    card(PAD, PAD, W-PAD, PAD+52, r=10)
    d.rounded_rectangle([PAD, PAD, PAD+3, PAD+52], radius=2, fill=GOLD)
    d.text((PAD+16, PAD+16), "СТАТУС СИСТЕМЫ", font=fT, fill=WHITE, anchor="lm")
    d.text((PAD+16, PAD+36), f"☣  ПОДРАЗДЕЛЕНИЕ BIO   |   Аптайм: {uptime}", font=fS, fill=MUTED, anchor="lm")
    d.text((W-PAD-10, PAD+16), f"Отчетов за 14 дней:", font=fS, fill=MUTED, anchor="rm")
    d.text((W-PAD-10, PAD+36), str(total_reports), font=fH, fill=GREEN, anchor="rm")

    y = PAD + 52 + PAD

    # ══ LEFT COLUMN ══
    lx = PAD

    # --- PING CARD ---
    card(lx, y, lx+CW, y+140)
    d.rounded_rectangle([lx, y, lx+3, y+140], radius=2, fill=BLUE)
    d.text((lx+14, y+14), "СОЕДИНЕНИЕ", font=fH, fill=WHITE, anchor="lm")

    dc_color = ping_color(discord_ws_ms)
    d.text((lx+14, y+42), "Discord (WebSocket)", font=fS, fill=MUTED, anchor="lm")
    d.text((lx+CW-14, y+42), f"{discord_ws_ms} ms", font=fH, fill=dc_color, anchor="rm")
    bar(lx+14, y+58, CW-28, min(100, discord_ws_ms//5), dc_color)

    ff_color = ping_color(ping_ff)
    d.text((lx+14, y+80), "apifreellm.com (ИИ-сервер)", font=fS, fill=MUTED, anchor="lm")
    d.text((lx+CW-14, y+80), ping_label(ping_ff), font=fH, fill=ff_color, anchor="rm")
    bar(lx+14, y+96, CW-28, min(100, (ping_ff or 500)//5), ff_color)

    dc2_color = ping_color(ping_dc)
    d.text((lx+14, y+118), "discord.com (HTTPS)", font=fS, fill=MUTED, anchor="lm")
    d.text((lx+CW-14, y+118), ping_label(ping_dc), font=fH, fill=dc2_color, anchor="rm")
    bar(lx+14, y+134, CW-28, min(100, (ping_dc or 500)//5), dc2_color)

    y2 = y + 140 + PAD

    # --- РЕСУРСЫ ---
    card(lx, y2, lx+CW, y2+170)
    d.rounded_rectangle([lx, y2, lx+3, y2+170], radius=2, fill=PURPLE)
    d.text((lx+14, y2+14), "РЕСУРСЫ", font=fH, fill=WHITE, anchor="lm")

    cpu_color = GREEN if cpu < 60 else (ORANGE if cpu < 85 else RED)
    d.text((lx+14, y2+42), "ЦП", font=fS, fill=MUTED, anchor="lm")
    d.text((lx+CW-14, y2+42), f"{cpu:.1f}%", font=fH, fill=cpu_color, anchor="rm")
    bar(lx+14, y2+58, CW-28, cpu, cpu_color)

    ram_pct   = ram_used / ram_total * 100 if ram_total else 0
    ram_color = GREEN if ram_pct < 60 else (ORANGE if ram_pct < 85 else RED)
    ram_used_gb  = ram_used  / 1024**3
    ram_total_gb = ram_total / 1024**3
    d.text((lx+14, y2+78), "ОЗУ", font=fS, fill=MUTED, anchor="lm")
    d.text((lx+CW-14, y2+78), f"{ram_used_gb:.1f} / {ram_total_gb:.1f} ГБ", font=fH, fill=ram_color, anchor="rm")
    bar(lx+14, y2+94, CW-28, ram_pct, ram_color)

    disk_pct    = disk_used / disk_total * 100 if disk_total else 0
    disk_color  = GREEN if disk_pct < 70 else (ORANGE if disk_pct < 90 else RED)
    disk_used_gb  = disk_used  / 1024**3
    disk_total_gb = disk_total / 1024**3
    d.text((lx+14, y2+118), "ДИСК", font=fS, fill=MUTED, anchor="lm")
    d.text((lx+CW-14, y2+118), f"{disk_used_gb:.1f} / {disk_total_gb:.1f} ГБ", font=fH, fill=disk_color, anchor="rm")
    bar(lx+14, y2+134, CW-28, disk_pct, disk_color)

    dot_color = GREEN if cpu < 85 and ram_pct < 85 and disk_pct < 90 else RED
    status_txt = "СИСТЕМА В НОРМЕ" if dot_color == GREEN else "ВЫСОКАЯ НАГРУЗКА"
    d.ellipse([lx+14, y2+156, lx+22, y2+164], fill=dot_color)
    d.text((lx+28, y2+160), status_txt, font=fS, fill=dot_color, anchor="lm")

    # ══ RIGHT COLUMN — GRAPH ══
    rx = PAD + CW + PAD
    graph_h = H - y - PAD

    card(rx, y, rx+CW, y+graph_h)
    d.rounded_rectangle([rx, y, rx+3, y+graph_h], radius=2, fill=GREEN)
    d.text((rx+14, y+14), "АКТИВНОСТЬ БОТА", font=fH, fill=WHITE, anchor="lm")
    d.text((rx+CW-14, y+14), "использований команд", font=fS, fill=MUTED, anchor="rm")

    now_t = time.time()
    hours  = 24
    buckets = [0] * hours
    for ts in cmd_history:
        diff_h = int((now_t - ts) / 3600)
        if 0 <= diff_h < hours:
            buckets[hours - 1 - diff_h] += 1

    gx0 = rx + 14
    gy0 = y + 38
    gx1 = rx + CW - 14
    gy1 = y + graph_h - 30
    gw  = gx1 - gx0
    gh  = gy1 - gy0

    for gi in range(5):
        gy = gy0 + int(gh * gi / 4)
        d.line([(gx0, gy),(gx1, gy)], fill=LINE, width=1)

    max_b = max(max(buckets), 1)
    bar_w = gw // hours
    for i, count in enumerate(buckets):
        bx   = gx0 + i * bar_w
        bh_p = int(gh * count / max_b)
        by   = gy1 - bh_p
        if bh_p > 0:
            d.rounded_rectangle([bx+1, by, bx+bar_w-2, gy1], radius=2, fill=GREEN)
            sh = max(1, bh_p//4)
            d.rounded_rectangle([bx+1, by, bx+bar_w-2, by+sh], radius=2,
                                  fill=tuple(min(255,c+70) for c in GREEN))
        else:
            d.line([(bx+bar_w//2, gy1-1), (bx+bar_w//2, gy1)], fill=LINE, width=1)

    for label, pos in [("24ч", 0), ("12ч", hours//2), ("сейчас", hours-1)]:
        lbx = gx0 + int(pos * bar_w) + bar_w//2
        d.text((lbx, gy1+5), label, font=fS, fill=MUTED, anchor="mt")

    total_cmds = len(cmd_history)
    d.text((rx+14, y+graph_h-12), f"Всего вызовов: {total_cmds}", font=fS, fill=MUTED, anchor="lm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ═══════════════════════════════════════════════════
#  РЕСУРСЫ КОНТЕЙНЕРА (cgroup v1)
# ═══════════════════════════════════════════════════

def _cgroup_ram():
    try:
        used  = int(open('/sys/fs/cgroup/memory/memory.usage_in_bytes').read())
        limit = int(open('/sys/fs/cgroup/memory/memory.limit_in_bytes').read())
        if limit > 10 * 1024**4:
            import psutil
            m = psutil.virtual_memory()
            return m.used, m.total
        return used, limit
    except Exception:
        import psutil
        m = psutil.virtual_memory()
        return m.used, m.total


def _cgroup_cpu(interval: float = 0.5) -> float:
    try:
        def _read():
            return int(open('/sys/fs/cgroup/cpuacct/cpuacct.usage').read())
        t1, u1 = time.time(), _read()
        import time as _t; _t.sleep(interval)
        t2, u2 = time.time(), _read()
        cpu_ns   = u2 - u1
        time_ns  = (t2 - t1) * 1e9
        try:
            quota  = int(open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us').read())
            period = int(open('/sys/fs/cgroup/cpu/cpu.cfs_period_us').read())
            ncpus  = quota / period if quota > 0 else (_os.cpu_count() or 1)
        except Exception:
            ncpus = _os.cpu_count() or 1
        return round(min((cpu_ns / time_ns / ncpus) * 100, 100.0), 1)
    except Exception:
        import psutil
        return psutil.cpu_percent(interval=interval)


def _cgroup_disk():
    import shutil
    s = shutil.disk_usage('/')
    return s.used, s.total


# ═══════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════

BOT_TOKEN = ""

REPORT_CHANNEL_ID = 0
OUTPUT_CHANNEL_ID = 0

TRACKED_ROLE_ID = 0
MENTION_ROLE_ID = 0

VACATION_ROLE_IDS = {
    0,
    0,
}

IGNORED_ROLE_IDS = {0,
}

ALLOWED_ROLE_IDS = IGNORED_ROLE_IDS | {0}

# Роли, которым разрешён доступ к ИИ-чату
AI_CHAT_ROLE_IDS = {0}

KEYWORDS = ["состав группы", "отчёт", "отчет", "дата", "позывной"]
MIN_WORDS = 10
NORM_MIN    = 3
PROMOTE_MIN = 6

IGNORED_MESSAGE_TYPES = {
    discord.MessageType.pins_add,
    discord.MessageType.new_member,
    discord.MessageType.premium_guild_subscription,
    discord.MessageType.premium_guild_tier_1,
    discord.MessageType.premium_guild_tier_2,
    discord.MessageType.premium_guild_tier_3,
    discord.MessageType.channel_name_change,
    discord.MessageType.channel_icon_change,
    discord.MessageType.thread_created,
    discord.MessageType.channel_follow_add,
    discord.MessageType.guild_discovery_disqualified,
    discord.MessageType.guild_discovery_requalified,
    discord.MessageType.thread_starter_message,
}

# ═══════════════════════════════════════════════════
#  ИНИЦИАЛИЗАЦИЯ
# ═══════════════════════════════════════════════════

_bot_start: float = time.time()
_cmd_history: deque = deque(maxlen=1000)

def record_command_use():
    _cmd_history.append(time.time())

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ═══════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════

def is_valid_message(message: discord.Message, ignored_member_ids: set) -> bool:
    if message.type in IGNORED_MESSAGE_TYPES:
        return False
    if isinstance(message.channel, discord.Thread):
        return False
    if message.author.id in ignored_member_ids:
        return False
    content = message.content.strip()
    if len(content.split()) < MIN_WORDS:
        return False
    content_lower = content.lower()
    if not any(kw in content_lower for kw in KEYWORDS):
        return False
    return True


def clean_name(display_name: str) -> str:
    import re
    if "|" in display_name:
        name = display_name.split("|")[-1].strip()
    else:
        name = display_name.strip()
    name = re.sub(r"\[.*?\]", "", name).strip()
    name = re.sub(r"\(.*?\)", "", name).strip()
    return name


def extract_bio_number(display_name: str) -> str:
    import re
    match = re.match(r"([A-Za-z]+-\d+)", display_name.strip())
    if match:
        return match.group(1).upper()
    return clean_name(display_name)


# ═══════════════════════════════════════════════════════════════════
#  VOICE CHANNELS / ГОЛОСОВЫЕ КАНАЛЫ
# ═══════════════════════════════════════════════════════════════════

import struct
import threading
import zipfile
import urllib.request
from pathlib import Path as _Path

try:
    from discord.ext import voice_recv as _voice_recv
    _VOICE_RECV_OK = True
except ImportError:
    _voice_recv = None
    _VOICE_RECV_OK = False

# ── Vosk ──
_VOSK_NAME   = "vosk-model-small-ru-0.22"
_VOSK_URL    = f"https://alphacephei.com/vosk/models/{_VOSK_NAME}.zip"
_VOSK_DIR    = _Path(_os.path.dirname(_os.path.abspath(__file__)))
_VOSK_MODEL_DIR = _VOSK_DIR / _VOSK_NAME
_vosk_model  = None

def _ensure_vosk():
    global _vosk_model
    if _vosk_model is not None:
        return _vosk_model
    try:
        from vosk import Model, SetLogLevel
        SetLogLevel(-1)
        if not _VOSK_MODEL_DIR.exists():
            _log(f"[VOSK] Скачиваю модель {_VOSK_NAME}...")
            zpath = _VOSK_DIR / f"{_VOSK_NAME}.zip"
            urllib.request.urlretrieve(_VOSK_URL, str(zpath))
            with zipfile.ZipFile(str(zpath)) as zf:
                zf.extractall(str(_VOSK_DIR))
            zpath.unlink()
            _log("[VOSK] Распакована")
        _vosk_model = Model(str(_VOSK_MODEL_DIR))
        _log("[VOSK] Модель загружена")
        return _vosk_model
    except Exception as e:
        _log(f"[VOSK] Ошибка загрузки: {e}")
        return None

async def _preload_vosk():
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _ensure_vosk)
        _log("[VOSK] Предзагрузка завершена")
    except Exception as e:
        _log(f"[VOSK] Ошибка предзагрузки: {e}")

def _pcm_to_wav(pcm: bytes) -> str | None:
    try:
        import wave as _wave
        mono = []
        for i in range(0, len(pcm) - 3, 4):
            l = struct.unpack_from("<h", pcm, i)[0]
            r = struct.unpack_from("<h", pcm, i + 2)[0]
            mono.append((l + r) // 2)
        ds = mono[::3]
        raw = struct.pack(f"<{len(ds)}h", *ds)
        import tempfile as _tf
        tmp = _tf.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with _wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            wf.writeframes(raw)
        return tmp.name
    except Exception as e:
        _log(f"[VOICE] PCM→WAV: {e}"); return None

def _stt_vosk(wav_path: str) -> str:
    import wave as _wave, json as _jv
    try:
        from vosk import KaldiRecognizer
        model = _ensure_vosk()
        if not model:
            return ""
        with _wave.open(wav_path, "rb") as wf:
            rate = wf.getframerate()
            raw  = wf.readframes(wf.getnframes())
        rec = KaldiRecognizer(model, rate)
        rec.SetWords(False)
        for i in range(0, len(raw), 4000):
            rec.AcceptWaveform(raw[i:i+4000])
        return _jv.loads(rec.FinalResult()).get("text", "").strip()
    except Exception as e:
        _log(f"[STT] {e}"); return ""

def _safe_unlink(p: str):
    try: _os.unlink(p)
    except: pass

_voice_sessions: dict[int, "VoiceSession"] = {}

class VoiceSession:
    SILENCE_SEC   = 1.5
    MIN_PCM_BYTES = 48000 * 4

    def __init__(self, vc, text_channel, guild):
        self.vc = vc; self.text_channel = text_channel; self.guild = guild
        self._active = True
        self._buffers: dict[int, list[bytes]] = {}
        self._last_audio: dict[int, float]   = {}
        self._processing: set[int]           = set()
        self._lock = threading.Lock()
        self._task: asyncio.Task | None = None

    def on_packet(self, member, data):
        if member is None or member.bot: return
        pcm = data.pcm if hasattr(data, "pcm") else bytes(data)
        with self._lock:
            self._buffers.setdefault(member.id, []).append(pcm)
            self._last_audio[member.id] = time.time()

    def start(self):
        _log("[VOICE] STT отключён. TTS (APF→войс) активен.")
        self._task = asyncio.get_event_loop().create_task(self._check_loop())

    async def _check_loop(self):
        while self._active:
            await asyncio.sleep(0.5)
            now = time.time()
            with self._lock:
                ready = [
                    uid for uid, t in self._last_audio.items()
                    if now - t > self.SILENCE_SEC
                    and self._buffers.get(uid)
                    and uid not in self._processing
                ]
            for uid in ready:
                with self._lock:
                    pcm = b"".join(self._buffers.pop(uid, []))
                    self._last_audio.pop(uid, None)
                if len(pcm) < self.MIN_PCM_BYTES: continue
                self._processing.add(uid)
                asyncio.get_event_loop().create_task(self._handle(uid, pcm))

    async def _handle(self, uid: int, pcm: bytes):
        try:
            loop = asyncio.get_event_loop()
            wav = await loop.run_in_executor(None, _pcm_to_wav, pcm)
            if not wav: return
            text = await loop.run_in_executor(None, _stt_vosk, wav)
            _safe_unlink(wav)
            if not text or len(text) < 3: return
            _log(f"[STT] uid={uid}: «{text[:80]}»")
            tl = text.lower()
            triggers = {"силициум", "silicium", "силиций", "бот"}
            if not any(w in tl for w in triggers): return
            query = text
            for w in sorted(triggers, key=len, reverse=True):
                query = query.lower().replace(w, "").strip(" ,.")
            if not query: return
            member = self.guild.get_member(uid)
            nick   = clean_name(member.display_name) if member else str(uid)
            bio    = extract_bio_number(member.display_name) if member else nick
            mode   = "РЕЖИМ 1 — УВАЖЕНИЕ" if nick in _VIP_CALLSIGNS else "РЕЖИМ 2 — GLaDOS"
            prompt = (
                f"Ты — SILICIUM, ИИ подразделения РХБЗ.\n"
                f"ОТВЕЧАЙ КРАТКО (1-3 предложения), только чистый текст без markdown.\n"
                f"{mode}\n[СОТРУДНИК] {bio} ({nick})\n"
                f"[БАЗА]\n{_db_context[:25000]}\n\n{_VIP_INFO}\n\n"
                f"[ВОПРОС]\n{query}\n[ОТВЕТ]"
            )
            ai = await _ask_ai(prompt)
            if "[MEMORY_UPDATE]" in ai:
                ai = ai.split("[MEMORY_UPDATE]", 1)[0].strip()
            _log(f"[VOICE-AI] {bio}: «{ai[:80]}»")
            mp3 = await _generate_tts_audio(ai)
            await _play_audio_in_voice(self.vc, mp3)
            if self.text_channel:
                try:
                    await self.text_channel.send(f"🎙️ _{query}_\n**SILICIUM:** {ai[:500]}")
                except: pass
        except Exception as e:
            _log(f"[VOICE] Ошибка: {e}")
        finally:
            self._processing.discard(uid)

    def stop(self):
        self._active = False
        if self._task: self._task.cancel()
        try:
            if _VOICE_RECV_OK and hasattr(self.vc, "stop_listening"):
                self.vc.stop_listening()
        except: pass
        with self._lock: self._buffers.clear()


def _parse_voice_action(text: str) -> str | None:
    text = text.lower()
    if not text: return None
    if re.search(r"\b(зайди|подключ|залез|присоедин|заход|иди|войди|го|залетай)\b", text) and \
       re.search(r"\b(войс|voice|голосов)\b", text):
        return "join"
    if re.search(r"\b(ливни|выйди|уйди|отвали|отключ|покин|выход|ливай)\b", text):
        return "leave"
    return None

def _get_voice_client(guild: discord.Guild) -> discord.VoiceClient | None:
    for vc in bot.voice_clients:
        if vc.guild == guild: return vc
    return None

async def _disconnect_voice(guild: discord.Guild) -> bool:
    gid = guild.id
    if gid in _voice_sessions:
        _voice_sessions[gid].stop()
        del _voice_sessions[gid]
    vc = _get_voice_client(guild)
    if vc and vc.is_connected():
        try: await vc.disconnect(force=True); return True
        except: pass
    return False

async def _handle_voice_command(message: discord.Message, action: str):
    guild = message.guild
    if action == "join":
        member = message.author
        if not isinstance(member, discord.Member) or not member.voice or not member.voice.channel:
            await message.reply("❌ Сначала войдите в голосовой канал.")
            return
        ch = member.voice.channel
        await _disconnect_voice(guild)
        await asyncio.sleep(0.4)
        try:
            if _VOICE_RECV_OK:
                vc = await ch.connect(cls=_voice_recv.VoiceRecvClient)
            else:
                vc = await ch.connect()
            sess = VoiceSession(vc, message.channel, guild)
            _voice_sessions[guild.id] = sess
            sess.start()
            stt = "Vosk (локально)" if _VOICE_RECV_OK else "STT недоступен"
            await message.reply(
                f"🎙️ Подключился к **{ch.name}**.\n"
                f"Скажите «**Силициум**» + вопрос.\n_STT: {stt} | TTS: edge-tts_"
            )
            _log(f"[VOICE] Подключён к #{ch.name}")
        except Exception as e:
            _log(f"[VOICE] Ошибка: {e}")
            await message.reply(f"❌ Ошибка подключения: {e}")
        return

    if action == "leave":
        if await _disconnect_voice(guild):
            await message.reply("🔇 Покинул голосовой канал.")
        else:
            await message.reply("Я не в голосовом канале.")


# ═══════════════════════════════════════════════════
#  ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ
# ═══════════════════════════════════════════════════

import os as _os

_BOT_DIR  = _os.path.dirname(_os.path.abspath(__file__))
RUSSO     = _os.path.join(_BOT_DIR, "RussoOne-Regular.ttf")
MASCOT    = _os.path.join(_BOT_DIR, "mascot.png")
FB        = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR        = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def ft(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(FB, size)
        except Exception:
            return ImageFont.load_default()


def generate_table_image(promotion, met_norm, not_met, vacation,
                          start_date_str, end_date_str,
                          message_counts_named=None,
                          mascot_path=None,
                          NORM_MIN=3, PROMOTE_MIN=6):

    BG=(11,11,17); CARD=(19,19,29); LINE=(36,36,52)
    WHITE=(228,228,238); MUTED=(105,105,130)
    GOLD=(255,195,40); GOLD_DIM=(55,42,6)
    GREEN=(55,195,105); GRN_DIM=(10,52,24)
    RED=(225,62,62); RED_DIM=(58,10,10)
    BLUE=(65,145,255); BLU_DIM=(10,34,72)
    PURPLE=(155,100,255)

    W=990; TABLE_W=565; PAD=18; ROW_H=36; HEADER_H=54; FOOTER_H=34; SEC_GAP=6

    sections=[
        ("ПОВЫШЕНИЕ",f"ОТ {PROMOTE_MIN}+",GOLD,GOLD_DIM,promotion),
        ("НОРМА",f"{NORM_MIN}-{PROMOTE_MIN-1} ОТЧЕТА",GREEN,GRN_DIM,met_norm),
        ("НЕ ХВАТАЕТ",f"МЕНЕЕ {NORM_MIN}",RED,RED_DIM,not_met),
        ("ОТПУСК","РЕЗЕРВ",BLUE,BLU_DIM,vacation),
    ]

    def rows_needed(lst): return max(1,-(-len(lst)//3))
    total_rows=sum(rows_needed(s[4]) for s in sections)
    content_h=PAD+HEADER_H+PAD+len(sections)*(ROW_H+SEC_GAP)+total_rows*ROW_H+PAD+FOOTER_H+PAD
    H=max(content_h,520)

    img=Image.new("RGB",(W,H),BG)
    d=ImageDraw.Draw(img)

    fT=ft(RUSSO,17); fSub=ft(RUSSO,10); fSH=ft(RUSSO,12); fSS=ft(RUSSO,10)
    fN=ft(RUSSO,12); fFT=ft(RUSSO,10); fCT=ft(RUSSO,13); fCL=ft(RUSSO,11); fCN=ft(RUSSO,11)

    def pill(x0,y0,x1,y1,fill,outline=None,r=5):
        d.rounded_rectangle([x0,y0,x1,y1],radius=r,fill=fill)
        if outline: d.rounded_rectangle([x0,y0,x1,y1],radius=r,outline=outline,width=1)

    def text_w(text, font):
        bbox = d.textbbox((0,0), text, font=font)
        return bbox[2] - bbox[0]

    pill(PAD,PAD,TABLE_W-PAD,PAD+HEADER_H,CARD,LINE,r=10)
    d.text((PAD+16,PAD+HEADER_H//2-8),"ИТОГИ ПОДРАЗДЕЛЕНИЯ BIO",font=fT,fill=WHITE,anchor="lm")
    d.text((PAD+16,PAD+HEADER_H//2+10),"☣  СИСТЕМА ПОДСЧЕТА ОТЧЕТОВ",font=fSub,fill=MUTED,anchor="lm")
    d.rounded_rectangle([PAD,PAD,PAD+3,PAD+HEADER_H],radius=2,fill=GOLD)

    if mascot_path:
        try:
            import numpy as np
            msc=Image.open(mascot_path).convert("RGBA")
            mh=HEADER_H-4; mw=mh
            msc=msc.resize((mw,mh),Image.LANCZOS)
            arr=np.array(msc)
            mask=(arr[:,:,0]<30)&(arr[:,:,1]<30)&(arr[:,:,2]<30)
            arr[mask,3]=0
            msc=Image.fromarray(arr)
            img.paste(msc,(TABLE_W-PAD-mw-2,PAD+2),msc)
        except Exception:
            pass

    y=PAD+HEADER_H+PAD
    col_w=(TABLE_W-2*PAD)//3

    for (title,sub,color,dim,members) in sections:
        pill(PAD,y,TABLE_W-PAD,y+ROW_H,dim,color,r=5)
        d.rounded_rectangle([PAD,y,PAD+3,y+ROW_H],radius=2,fill=color)
        d.text((PAD+12,y+ROW_H//2-7),title,font=fSH,fill=color,anchor="lm")
        d.text((PAD+12,y+ROW_H//2+7),sub,font=fSS,fill=color,anchor="lm")
        cnt=str(len(members)); badge_w=max(26,len(cnt)*10+12)
        pill(TABLE_W-PAD-badge_w-2,y+7,TABLE_W-PAD-2,y+ROW_H-7,BG,color,r=7)
        d.text((TABLE_W-PAD-badge_w//2-2,y+ROW_H//2),cnt,font=fSH,fill=color,anchor="mm")
        y+=ROW_H

        nr=rows_needed(members)
        for ri in range(nr):
            chunk=members[ri*3:(ri+1)*3]
            for ci in range(3):
                cx=PAD+ci*col_w
                if ci<len(chunk):
                    pill(cx+2,y+2,cx+col_w-2,y+ROW_H-2,(22,22,34),LINE,r=4)
                    name=chunk[ci]
                    if message_counts_named and name in message_counts_named:
                        cnt_str = f"({message_counts_named[name]})"
                        nw  = text_w(name, fN)
                        cw2 = text_w(cnt_str, fSS)
                        total_tw = nw + 4 + cw2
                        nx = cx + col_w//2 - total_tw//2
                        d.text((nx, y+ROW_H//2), name, font=fN, fill=WHITE, anchor="lm")
                        d.text((nx+nw+4, y+ROW_H//2), cnt_str, font=fSS, fill=MUTED, anchor="lm")
                    else:
                        d.text((cx+col_w//2,y+ROW_H//2),name,font=fN,fill=WHITE,anchor="mm")
                else:
                    d.rounded_rectangle([cx+2,y+2,cx+col_w-2,y+ROW_H-2],radius=4,fill=(15,15,22))
            y+=ROW_H
        y+=SEC_GAP

    fy=H-FOOTER_H-PAD
    d.line([(PAD,fy-3),(TABLE_W-PAD,fy-3)],fill=LINE,width=1)
    d.text((PAD+6,fy+FOOTER_H//2),f"Период: {start_date_str} — {end_date_str}   |   Система подсчета отчетов ☣",font=fFT,fill=MUTED,anchor="lm")

    cx0=TABLE_W+PAD; cw=W-cx0-PAD
    d.text((cx0+2,PAD+HEADER_H//2-8),"АКТИВНОСТЬ",font=fCT,fill=WHITE,anchor="lm")
    d.text((cx0+2,PAD+HEADER_H//2+9),"отчетов за период",font=fSub,fill=MUTED,anchor="lm")
    d.rounded_rectangle([cx0-3,PAD,cx0,PAD+HEADER_H],radius=1,fill=PURPLE)
    d.line([(cx0,PAD+HEADER_H+8),(W-PAD,PAD+HEADER_H+8)],fill=LINE,width=1)

    if message_counts_named:
        all_members=promotion+met_norm+not_met
        bar_data=[(n,message_counts_named.get(n,0)) for n in all_members]
        bar_data.sort(key=lambda x:-x[1])
        chart_top=PAD+HEADER_H+PAD; chart_bottom=H-PAD-FOOTER_H-PAD-16
        chart_h=chart_bottom-chart_top
        n=len(bar_data)
        if n>0:
            bar_h=max(11,min(24,(chart_h-(n-1)*3)//n)); gap=3
            label_w=82; num_w=24; bar_area=cw-label_w-num_w-6
            max_c=max(c for _,c in bar_data) if bar_data else 1; max_c=max(max_c,1)
            for gi in range(1,5):
                gx=cx0+label_w+int(bar_area*gi/4)
                for gy in range(chart_top,chart_bottom,5): d.point((gx,gy),fill=LINE)
            by=chart_top
            for name,count in bar_data:
                bx=cx0+label_w
                if name in promotion: bc=GOLD
                elif name in met_norm: bc=GREEN
                else: bc=RED
                display=name if len(name)<=11 else name[:10]+"…"
                d.text((bx-6,by+bar_h//2),display,font=fCL,fill=WHITE,anchor="rm")
                d.rounded_rectangle([bx,by+3,bx+bar_area,by+bar_h-3],radius=3,fill=(20,20,30))
                bl=int(bar_area*count/max_c)
                if bl>0:
                    d.rounded_rectangle([bx,by+3,bx+bl,by+bar_h-3],radius=3,fill=bc)
                    sh=max(1,(bar_h-6)//3); sc=tuple(min(255,c+70) for c in bc)
                    d.rounded_rectangle([bx,by+3,bx+bl,by+3+sh],radius=3,fill=sc)
                d.text((bx+bar_area+num_w//2,by+bar_h//2),str(count),font=fCN,fill=bc,anchor="mm")
                by+=bar_h+gap
        leg_y=H-PAD-FOOTER_H+2; lx=cx0
        for ltxt,lc in [(f"{PROMOTE_MIN}+",GOLD),(f"{NORM_MIN}-{PROMOTE_MIN-1}",GREEN),(f"<{NORM_MIN}",RED)]:
            d.rounded_rectangle([lx,leg_y,lx+8,leg_y+8],radius=2,fill=lc)
            d.text((lx+12,leg_y+4),ltxt,font=fFT,fill=MUTED,anchor="lm"); lx+=46

    buf=io.BytesIO(); img.save(buf,format="PNG"); buf.seek(0)
    return buf


# Хранилище логов (последние 200 событий)
_bot_logs: list[str] = []
_MAX_LOGS = 200

def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%d.%m %H:%M:%S")
    entry = f"[{ts}] {msg}"
    _bot_logs.append(entry)
    if len(_bot_logs) > _MAX_LOGS:
        _bot_logs.pop(0)
    print(entry)


# ═══════════════════════════════════════════════════
#  СЛЭШ-КОМАНДА /итоги
# ═══════════════════════════════════════════════════

@bot.tree.command(name="итоги", description="Подвести итоги активности за последние 14 дней")
async def itogi(interaction: discord.Interaction):

    record_command_use()
    _log(f"/итоги вызван: {interaction.user} (ID:{interaction.user.id})")
    user_role_ids = {r.id for r in interaction.user.roles}
    if not (user_role_ids & ALLOWED_ROLE_IDS):
        await interaction.response.send_message(
            "❌ У вас нет прав для использования этой команды.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    guild          = interaction.guild
    report_channel = guild.get_channel(REPORT_CHANNEL_ID)
    output_channel = guild.get_channel(OUTPUT_CHANNEL_ID)

    if not report_channel:
        await interaction.followup.send(f"❌ Канал отчётов (ID: {REPORT_CHANNEL_ID}) не найден.", ephemeral=True)
        return
    if not output_channel:
        await interaction.followup.send(f"❌ Канал для публикации (ID: {OUTPUT_CHANNEL_ID}) не найден.", ephemeral=True)
        return

    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=14)

    ignored_member_ids: set[int] = set()
    non_vacation_ignored = IGNORED_ROLE_IDS - VACATION_ROLE_IDS
    for member in guild.members:
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & non_vacation_ignored:
            ignored_member_ids.add(member.id)

    await interaction.followup.send("⏳ Читаю историю канала, это может занять время...", ephemeral=True)

    message_counts: dict[int, int] = {}

    retries = 0
    MAX_RETRIES = 5
    while retries < MAX_RETRIES:
        try:
            message_counts = {}
            async for message in report_channel.history(
                after=cutoff,
                limit=None,
                oldest_first=True
            ):
                if is_valid_message(message, ignored_member_ids):
                    message_counts[message.author.id] = message_counts.get(message.author.id, 0) + 1
            break
        except Exception as e:
            retries += 1
            if retries >= MAX_RETRIES:
                await interaction.followup.send(f"❌ Ошибка при чтении истории: {e}", ephemeral=True)
                return
            await asyncio.sleep(2 * retries)

    tracked_role = guild.get_role(TRACKED_ROLE_ID)
    if not tracked_role:
        await interaction.followup.send(f"❌ Отслеживаемая роль (ID: {TRACKED_ROLE_ID}) не найдена.", ephemeral=True)
        return

    vacation:  list[str] = []
    not_met:   list[str] = []
    met_norm:  list[str] = []
    promotion: list[str] = []

    for member in tracked_role.members:
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & non_vacation_ignored:
            continue
        if member_role_ids & VACATION_ROLE_IDS:
            vacation.append(clean_name(member.display_name))
            continue
        count = message_counts.get(member.id, 0)
        if count >= PROMOTE_MIN:
            promotion.append(clean_name(member.display_name))
        elif count >= NORM_MIN:
            met_norm.append(clean_name(member.display_name))
        else:
            not_met.append(clean_name(member.display_name))

    vacation.sort(key=str.lower)
    not_met.sort(key=str.lower)
    met_norm.sort(key=str.lower)
    promotion.sort(key=str.lower)

    next_date_str  = (now + timedelta(days=14)).strftime("%d.%m.%Y")
    start_date_str = cutoff.strftime("%d.%m.%Y")
    end_date_str   = now.strftime("%d.%m.%Y")

    name_to_id: dict[str, int] = {}
    for member in tracked_role.members:
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & non_vacation_ignored:
            continue
        if member_role_ids & VACATION_ROLE_IDS:
            continue
        name_to_id[clean_name(member.display_name)] = member.id

    message_counts_named = {
        name: message_counts.get(uid, 0)
        for name, uid in name_to_id.items()
    }

    img_buf = generate_table_image(
        promotion, met_norm, not_met, vacation,
        start_date_str, end_date_str,
        message_counts_named,
        mascot_path=MASCOT
    )

    header_text = (
        f"<@&{MENTION_ROLE_ID}>\n"
        f"Написанные отчеты зафиксированы за период {start_date_str} — {end_date_str} (включительно). Инактив наказуем.\n"
        f"Следующие итоги будут {next_date_str}"
    )

    await output_channel.send(
        content=header_text,
        file=discord.File(img_buf, filename="itogi.png")
    )
    _log(f"/итоги опубликованы: повышение={len(promotion)}, норма={len(met_norm)}, не хватает={len(not_met)}, отпуск={len(vacation)}")
    await interaction.followup.send("✅ Итоги успешно опубликованы!", ephemeral=True)


# ═══════════════════════════════════════════════════
#  СЛЭШ-КОМАНДА /итоги_тест
# ═══════════════════════════════════════════════════

@bot.tree.command(name="итоги_тест", description="Тестовый вывод итогов в текущий канал (без пинга)")
async def itogi_test(interaction: discord.Interaction):

    record_command_use()
    _log(f"/итоги_тест вызван: {interaction.user} (ID:{interaction.user.id})")
    user_role_ids = {r.id for r in interaction.user.roles}
    if not (user_role_ids & ALLOWED_ROLE_IDS):
        await interaction.response.send_message(
            "❌ У вас нет прав для использования этой команды.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    guild          = interaction.guild
    report_channel = guild.get_channel(REPORT_CHANNEL_ID)
    output_channel = interaction.channel

    if not report_channel:
        await interaction.followup.send(f"❌ Канал отчётов (ID: {REPORT_CHANNEL_ID}) не найден.", ephemeral=True)
        return

    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=14)

    ignored_member_ids: set[int] = set()
    non_vacation_ignored = IGNORED_ROLE_IDS - VACATION_ROLE_IDS
    for member in guild.members:
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & non_vacation_ignored:
            ignored_member_ids.add(member.id)

    await interaction.followup.send("⏳ Читаю историю канала...", ephemeral=True)

    message_counts: dict[int, int] = {}
    retries = 0
    MAX_RETRIES = 5
    while retries < MAX_RETRIES:
        try:
            message_counts = {}
            async for message in report_channel.history(
                after=cutoff,
                limit=None,
                oldest_first=True
            ):
                if is_valid_message(message, ignored_member_ids):
                    message_counts[message.author.id] = message_counts.get(message.author.id, 0) + 1
            break
        except Exception as e:
            retries += 1
            if retries >= MAX_RETRIES:
                await interaction.followup.send(f"❌ Ошибка при чтении истории: {e}", ephemeral=True)
                return
            await asyncio.sleep(2 * retries)

    tracked_role = guild.get_role(TRACKED_ROLE_ID)
    if not tracked_role:
        await interaction.followup.send(f"❌ Отслеживаемая роль (ID: {TRACKED_ROLE_ID}) не найдена.", ephemeral=True)
        return

    vacation:  list[str] = []
    not_met:   list[str] = []
    met_norm:  list[str] = []
    promotion: list[str] = []

    for member in tracked_role.members:
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & non_vacation_ignored:
            continue
        if member_role_ids & VACATION_ROLE_IDS:
            vacation.append(clean_name(member.display_name))
            continue
        count = message_counts.get(member.id, 0)
        if count >= PROMOTE_MIN:
            promotion.append(clean_name(member.display_name))
        elif count >= NORM_MIN:
            met_norm.append(clean_name(member.display_name))
        else:
            not_met.append(clean_name(member.display_name))

    vacation.sort(key=str.lower)
    not_met.sort(key=str.lower)
    met_norm.sort(key=str.lower)
    promotion.sort(key=str.lower)

    start_date_str = cutoff.strftime("%d.%m.%Y")
    end_date_str   = now.strftime("%d.%m.%Y")
    next_date_str  = (now + timedelta(days=14)).strftime("%d.%m.%Y")

    name_to_id: dict[str, int] = {}
    for member in tracked_role.members:
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & non_vacation_ignored:
            continue
        if member_role_ids & VACATION_ROLE_IDS:
            continue
        name_to_id[clean_name(member.display_name)] = member.id

    message_counts_named = {
        name: message_counts.get(uid, 0)
        for name, uid in name_to_id.items()
    }

    img_buf = generate_table_image(
        promotion, met_norm, not_met, vacation,
        start_date_str, end_date_str,
        message_counts_named,
        mascot_path=MASCOT
    )

    header_text = (
        f"🧪 ТЕСТ — Итоги за период {start_date_str} — {end_date_str} (включительно)\n"
        f"Следующие итоги будут {next_date_str}"
    )

    await output_channel.send(
        content=header_text,
        file=discord.File(img_buf, filename="itogi_test.png")
    )
    _log(f"/итоги_тест опубликованы в #{output_channel.name}")
    await interaction.followup.send("✅ Тестовые итоги опубликованы в этот канал!", ephemeral=True)


# ═══════════════════════════════════════════════════
#  СТАТУС / ЛОГИ / Б-Д КОМАНДЫ
# ═══════════════════════════════════════════════════

@bot.tree.command(name="статус", description="Статус системы и бота")
async def status_cmd(interaction: discord.Interaction):
    record_command_use()
    _log(f"/статус вызван: {interaction.user}")
    await interaction.response.defer(ephemeral=False, thinking=True)

    dc_ws = round(bot.latency * 1000)
    ping_ff = await tcp_ping_ms("apifreellm.com", 443)
    ping_dc = await tcp_ping_ms("discord.com", 443)

    cpu               = await asyncio.get_event_loop().run_in_executor(None, lambda: _cgroup_cpu(0.4))
    ram_used, ram_tot = _cgroup_ram()
    disk_used, disk_tot = _cgroup_disk()
    uptime            = uptime_str()

    guild          = interaction.guild
    report_channel = guild.get_channel(REPORT_CHANNEL_ID)
    total_reports  = 0

    if report_channel:
        now_t  = datetime.now(timezone.utc)
        cutoff = now_t - timedelta(days=14)
        non_vacation_ignored = IGNORED_ROLE_IDS - VACATION_ROLE_IDS
        ignored_ids: set[int] = set()
        for m in guild.members:
            if {r.id for r in m.roles} & non_vacation_ignored:
                ignored_ids.add(m.id)
        try:
            async for msg in report_channel.history(after=cutoff, limit=None):
                if is_valid_message(msg, ignored_ids):
                    total_reports += 1
        except Exception:
            total_reports = -1

    img_buf = generate_status_image(
        ping_ff=ping_ff,
        ping_dc=ping_dc,
        discord_ws_ms=dc_ws,
        cpu=cpu,
        ram_used=ram_used,
        ram_total=ram_tot,
        disk_used=disk_used,
        disk_total=disk_tot,
        uptime=uptime,
        total_reports=total_reports,
        cmd_history=_cmd_history,
        font_path=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "RussoOne-Regular.ttf"),
    )

    await interaction.followup.send(file=discord.File(img_buf, filename="status.png"))


@bot.tree.command(name="логи", description="Последние логи бота")
async def logs_cmd(interaction: discord.Interaction):
    user_role_ids = {r.id for r in interaction.user.roles}
    if not (user_role_ids & ALLOWED_ROLE_IDS):
        await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        return

    if not _bot_logs:
        await interaction.response.send_message("Логов пока нет.", ephemeral=True)
        return

    lines = _bot_logs[-50:]
    text  = "\n".join(lines)
    chunks = []
    while len(text) > 1900:
        split = text[:1900].rfind("\n")
        chunks.append(text[:split])
        text = text[split+1:]
    chunks.append(text)

    await interaction.response.send_message(f"```\n{chunks[0]}\n```", ephemeral=True)
    for chunk in chunks[1:]:
        await interaction.followup.send(f"```\n{chunk}\n```", ephemeral=True)


@bot.tree.command(name="б-д", description="База данных подразделения")
async def bd_cmd(interaction: discord.Interaction):
    user_role_ids = {r.id for r in interaction.user.roles}
    if TRACKED_ROLE_ID not in user_role_ids:
        await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        return

    embed = discord.Embed(
        title="☣  База Данных Подразделения BIO",
        color=0x1a1a2e
    )
    embed.add_field(
        name="🟢  Актуально",
        value="[Открыть сайт подразделения](https://sites.google.com/view/rhbzdivision)",
        inline=False
    )
    embed.add_field(
        name="─────────────────────────────",
        value="** **",
        inline=False
    )
    embed.add_field(
        name="📦  Архив",
        value=(
            "📋  [Памятка РХБЗ](https://docs.google.com/spreadsheets/d/1DASoVrtLwkVlN9gI-ztw2pymln79kSYpX2YyIlccTVU/edit?pli=1&gid=0#gid=0)\n"
            "🏥  [Мед. регламент РХБЗ](https://docs.google.com/document/d/1UpoVa_sK90113e79vpmQ347KS0t4TEmkoHGySbljNGc/edit?tab=t.0#heading=h.5y0vhd7b53eh)\n"
            "⚠️  [Справочник Угроз](https://docs.google.com/document/d/13cY4fcS6I3KnWu22SWopnlU6tpbISsRdjV-hrcybE0A/edit?tab=t.0#heading=h.cf7gu2hdtz0r)\n"
            "🗄️  [База Данных (Старая)](https://sites.google.com/view/rhbz-data-base)"
        ),
        inline=False
    )
    embed.set_footer(text="Только вы видите это сообщение  •  Подразделение BIO")

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Открыть сайт", url="https://sites.google.com/view/rhbzdivision", emoji="🌐", style=discord.ButtonStyle.link))
    view.add_item(discord.ui.Button(label="Памятка", url="https://docs.google.com/spreadsheets/d/1DASoVrtLwkVlN9gI-ztw2pymln79kSYpX2YyIlccTVU/edit?pli=1&gid=0#gid=0", emoji="📋", style=discord.ButtonStyle.link))
    view.add_item(discord.ui.Button(label="Мед. регламент", url="https://docs.google.com/document/d/1UpoVa_sK90113e79vpmQ347KS0t4TEmkoHGySbljNGc/edit?tab=t.0#heading=h.5y0vhd7b53eh", emoji="🏥", style=discord.ButtonStyle.link))
    view.add_item(discord.ui.Button(label="Справочник Угроз", url="https://docs.google.com/document/d/13cY4fcS6I3KnWu22SWopnlU6tpbISsRdjV-hrcybE0A/edit?tab=t.0#heading=h.cf7gu2hdtz0r", emoji="⚠️", style=discord.ButtonStyle.link))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ═══════════════════════════════════════════════════
#  ЕЖЕДНЕВНЫЕ ШУТКИ
# ═══════════════════════════════════════════════════

JOKES_CHANNEL_ID = 1288900851640828006

JOKES = [
    "Учёные выяснили, что человек использует мозг только на 10%. Остальные 90% заняты мыслями о том, что в случае ошибки, которая привела к катастрофе",
    "CASTLE просят реанимировать пострадавшего, Подразделение РХБЗ просить не мешать наблюдению за экспериментом.",
    "В ЛБ-НН всё под контролем. Если не считать последних трёх экспериментов.",
    "Согласно протоколу, перед входом в зону ИУ следует включить СЗД. Согласно статистике, большинство вспоминают об этом после входа.",
    "Уровень загрязнения — малый. Это значит, что вы, вероятно, выживете. Вероятно.",
    "Деконтаминатор весит около пятидесяти килограмм, в сумме с устройством распыления. Если вы не знали — теперь знаете. Ваши спина и руки тоже скоро об этом узнают.",
    "Плановый осмотр показал: всё в норме. Предыдущий плановый осмотр тоже показал, что всё в норме. Тогда это был склад с антротоксином.",
    "Мозговые паразиты похожи по структуре мяса на курицу. Это не означает, что их следует есть",
    "Трупный паразит не представляет угрозы на расстоянии. Держите это в уме, пока он не залез внутрь в вас.",
    "Антидот NI-X нейтрализует некротизирующие токсины. Инструкция по применению рекомендует вводить его до наступления некроза. Записали?",
    "СК-У обнаруживает угрозы на расстоянии до четырёхсот метров. То, что уже у вас за спиной, в зону покрытия не входит.",
    "Алидовое гнездо классифицируется как высокая угроза. Тот факт, что вы читаете это определение прямо сейчас, вселяет в меня определённые опасения.",
    "СЗД обеспечивает постоянный приток свежего воздуха. Сотрудники, которые её отключили 'ненадолго', больше не нуждаются в воздухе.",
    "Опыленный спор безопасен на расстоянии. Приновый распылитель обнаруживает вас в десяти метрах. Пожалуйста, оцените разницу самостоятельно.",
    "Подразделение РХБЗ существует для нейтрализации угроз. Угрозы существуют для проверки эффективности подразделения. Один из нас справляется лучше.",
    "П-Л предназначена для оперативного анализа угроз на месте. Оперативного — это значит до того, как угроза завершит анализ вас.",
    "Цеплийский цветок привлекает насекомых своим запахом и заражает их спорами. Эволюция — увлекательная наука. Особенно когда наблюдаешь её со стороны.",
    "Органиевый глаз направляет разрастание флоры Зена в благоприятном направлении. Направление 'к вам' он считает весьма благоприятным.",
    "Антротоксин создан для мучительных непубличных казней. Публичных казней он тоже не исключает. Просто изначально не для этого проектировался.",
    "Сотрудник РХБЗ обязан знать классификацию всех угроз. Угрозы, к сожалению, с классификацией не ознакомлены и действуют по собственному усмотрению.",
    "Закупоренный спор содержит питательные вещества флоры Зена. Не рекомендуется проверять это лично. Хотя некоторые проверяли. Один раз.",
    "Счётчик Гейгера сканирует местность от одной до трёх минут. Если за это время вы не двигались — либо вы очень дисциплинированы, либо уже поздно.",
    "Дегазация — это процесс удаления опасных химических веществ из окружающей среды. Дегазация сотрудника — процесс значительно более неприятный для сотрудника.",
    "Биологические агенты могут вызывать болезни у людей, животных и растений. Флора Зена совмещает все три категории. Это называется эффективностью.",
    "Защитный костюм полностью изолирует тело от внешних воздействий. Внутренние воздействия — паника, сомнения, желание уволиться — костюм не блокирует.",
    "Приновый распылитель поедает жертву живьём. Это задокументировано. Документировал сотрудник, которого впоследствии тоже задокументировали.",
    "Зона строгого контроля закрыта для гражданского населения. Гражданское население об этом, как правило, узнаёт уже находясь в зоне строгого контроля.",
    "Органиевый яичник формируется на гниющих трупах и распространяет заразу через запах. Это одна из причин, по которой МЗ пахнет именно так.",
    "Калибровка сканера обязательна перед каждым использованием. Сотрудники, пропускающие калибровку, как правило, не нуждаются в повторной калибровке.",
    "Суринам блокирует передачу нервных импульсов, обездвиживая жертву. Хорошая новость: вы всё ещё будете осознавать происходящее. Плохая новость: та же самая.",
    "Чрезвычайная ситуация отличается от чрезвычайного происшествия масштабом последствий. На практике сотрудники узнают разницу уже в процессе.",
    "СК-С точнее универсального и охватывает вдвое большую дальность. Это особенно полезно знать тем, кто взял с собой только универсальный.",
    "Плазменный подавитель способен сдержать объект высокого уровня опасности. К свободному использованию запрещён. Причины засекречены. Их было семь.",
    "Вирум является основой производства чистящего раствора. Альянс обнаружил это случайно. Подробности того случая засекречены.",
    "Инвазивная угроза может спровоцировать биологическое, химическое или радиационное заражение одновременно. Флора Зена не признаёт понятия избыточности.",
    "Второй этап проверки людей включает анализ крови на наличие опасных веществ. Первый этап — визуальный осмотр. Иногда первого этапа достаточно.",
    "Карантинная зона закрыта для всех, кроме специализированного персонала. Специализированный персонал также предпочитает там не находиться.",
    "Система раннего предупреждения предназначена для своевременного оповещения об угрозах. Своевременно — это до контакта. Не во время. Уточняю на всякий случай.",
    "Сектор 8 функционирует в штатном режиме. Это официальная формулировка. Неофициальную формулировку данная система не уполномочена воспроизводить.",
    "Рицин вызывает быструю безболезненную смерть. Разработчики антротоксина сочли это недостаточно информативным и предложили альтернативу.",
    "Отросток тентакла в невыросшем виде неподвижен и безопасен. В выросшем — подвижен и нет. Среднее время роста при наличии питательных веществ не публикуется.",
    "Изолированная зона отличается от зоны карантина степенью ограничений. Сотрудникам внутри обеих зон разница кажется несущественной.",
]

import random as _random

async def _post_daily_joke():
    await bot.wait_until_ready()
    channel = bot.get_channel(JOKES_CHANNEL_ID)
    if not channel or not JOKES:
        return
    joke = _random.choice(JOKES)
    try:
        await channel.send(joke)
        _log(f"Шутка дня отправлена в #{channel.name}")
    except Exception as e:
        _log(f"Ошибка отправки шутки: {e}")


async def _joke_scheduler():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now   = datetime.now(timezone.utc)
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_sec = (target - now).total_seconds()
        _log(f"Следующая шутка через {int(wait_sec//3600)}ч {int((wait_sec%3600)//60)}м")
        await asyncio.sleep(wait_sec)
        await _post_daily_joke()


@bot.tree.command(name="шутка", description="Случайная шутка дня")
async def joke_cmd(interaction: discord.Interaction):
    if not JOKES:
        await interaction.response.send_message("Список шуток пуст!", ephemeral=True)
        return
    await interaction.response.send_message(_random.choice(JOKES))


# ═══════════════════════════════════════════════════
#  ИИ: APF
# ═══════════════════════════════════════════════════

import aiohttp
import json as _json

GEMINI_KEYS    = []
GEMINI_URL     = ""
GEMINI_TIMEOUT = 30

APF_KEYS = [
    "apf_your_api_key_here",
]
APF_URL = "https://apifreellm.com/api/v1/chat"
_APF_KEY_TIMEOUT = 25

_DB_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "db_context.txt")

def _load_db_context() -> str:
    try:
        with open(_DB_PATH, encoding="utf-8") as f:
            content = f.read()
        print(f"[ИИ] База знаний загружена: {len(content)} символов")
        return content[:105000]
    except FileNotFoundError:
        print("⚠️ [ИИ] db_context.txt не найден — бот будет работать без базы знаний")
        return ""

_db_context: str = _load_db_context()


# ═══════════════════════════════════════════════════
#  ТАБЛИЦА АЛИАСОВ ДЛЯ ПОИСКА ИЗОБРАЖЕНИЙ
#  Все варианты написания → каноническое имя в db_context.txt
# ═══════════════════════════════════════════════════

_IMAGE_ALIASES: dict[str, str] = {
    # ═══ Я.Б.Х ═══
    "ябх":          "Я.Б.Х",
    "я.б.х":        "Я.Б.Х",
    "яbх":          "Я.Б.Х",
    "ybh":          "Я.Б.Х",
    "y.b.h":        "Я.Б.Х",
    "ядерно биологический": "Я.Б.Х",
    "ядерно-биологический": "Я.Б.Х",

    # ═══ ПЛ ═══
    "пл":           "ПЛ",
    "противогаз":   "ПЛ",

    # ═══ СК-У ═══
    "ску":          "СК-У",
    "ск-у":         "СК-У",
    "ск у":         "СК-У",
    "скафандр у":   "СК-У",

    # ═══ СК-С ═══
    "скс":          "СК-С",
    "ск-с":         "СК-С",
    "ск с":         "СК-С",
    "скафандр с":   "СК-С",

    # ═══ ОВ ═══
    "ов":                   "ОВ",
    "отравляющее":          "ОВ",
    "очиститель воздуха":   "ОВ",
    "очиститель":           "ОВ",
    "воздухоочиститель":    "ОВ",

    # ═══ СГ ═══
    "сг":           "СГ",
    "световая граната": "СГ",
    "светошумовая": "СГ",

    # ═══ УДАВ / U.D.A.V ═══
    "удав":         "UDAV",
    "udav":         "UDAV",
    "у.д.а.в":      "UDAV",
    "u.d.a.v":      "UDAV",
    "пульсар":      "UDAV",
    "боевой пульсар": "UDAV",

    # ═══ pH-метр ═══
    "ph метр":      "pH - метр",
    "ph-метр":      "pH - метр",
    "пх метр":      "pH - метр",
    "phmeter":      "pH - метр",
    "кислотомер":   "pH - метр",
    "ph":           "pH - метр",

    # ═══ Оковы Гром ═══
    "оковы":        "Оковы Гром",
    "гром":         "Оковы Гром",
    "оковы гром":   "Оковы Гром",

    # ═══ Хвататель "Клешня" ═══
    "клешня":       "Хвататель \"Клешня\"",
    "хвататель":    "Хвататель \"Клешня\"",
    "клешни":       "Хвататель \"Клешня\"",

    # ═══ Униформа сотрудника ═══
    "униформа":     "Униформа сотрудника",
    "форма сотрудника": "Униформа сотрудника",
    "костюм сотрудника": "Униформа сотрудника",

    # ═══ Термо-плащ ═══
    "термоплащ":    "Термо-плащ",
    "термо плащ":   "Термо-плащ",
    "плащ":         "Термо-плащ",

    # ═══ Медицинский Рюкзак ═══
    "мед рюкзак":   "Медицинский Рюкзак",
    "медрюкзак":    "Медицинский Рюкзак",
    "медицинский рюкзак": "Медицинский Рюкзак",
    "медицинский":  "Медицинский Рюкзак",

    # ═══ Инженерный Рюкзак ═══
    "инж рюкзак":   "Инженерный Рюкзак",
    "инженерный рюкзак": "Инженерный Рюкзак",
    "инженерный":   "Инженерный Рюкзак",

    # ═══ Технический Рюкзак ═══
    "тех рюкзак":   "Технический Рюкзак",
    "технический рюкзак": "Технический Рюкзак",
    "технический":  "Технический Рюкзак",

    # ═══ Чистящий Раствор ═══
    "чистящий раствор": "Чистящий Раствор",
    "раствор":      "Чистящий Раствор",
    "чистящий":     "Чистящий Раствор",

    # ═══ Деконтаминатор ═══
    "деконтаминатор": "Деконтоминатор",
    "деконтоминатор": "Деконтоминатор",
    "деконт":       "Деконтоминатор",
    "дезактиватор": "Деконтоминатор",

    # ═══ Оксиновые Капли ═══
    "оксиновые":    "Оксиновые Капли",
    "оксин":        "Оксиновые Капли",
    "капли":        "Оксиновые Капли",
    "оксиновые капли": "Оксиновые Капли",

    # ═══ Отросток Тентакла ═══
    "тентакл":      "Отросток Тентакла",
    "отросток":     "Отросток Тентакла",
    "тентакла":     "Отросток Тентакла",

    # ═══ Органиевый Глаз ═══
    "органиевый глаз":      "Органиевый Глаз",
    "орган глаз":           "Органиевый Глаз",
    "органиевый глаза":     "Органиевый Глаз",

    # ═══ Закупоренный Спор ═══
    "закупоренный спор":    "Закупореный Спор",
    "закупоренный":         "Закупореный Спор",
    "закупореный спор":     "Закупореный Спор",
    "закупореный":          "Закупореный Спор",

    # ═══ Опылённый Спор ═══
    "опыленный спор":       "Опыленный Спор",
    "опылённый спор":       "Опыленный Спор",
    "опыленный":            "Опыленный Спор",
    "опылённый":            "Опыленный Спор",

    # ═══ Цеплийский Цветок ═══
    "цеплийский":           "Цеплийский Цветок",
    "цеплийский цветок":    "Цеплийский Цветок",
    "цветок":               "Цеплийский Цветок",

    # ═══ Органиевый Мешок ═══
    "органиевый мешок":     "Органиевый Мешок",
    # "органиевый" один — убран, слишком широкий (матчил глаз и мешок одновременно)

    # ═══ Алидовое гнездо ═══
    "алидовое":     "Алидовое гнездо",
    "алидово":      "Алидовое гнездо",
    "аллидовое":    "Алидовое гнездо",    # частая опечатка с двойной л
    "аллидово":     "Алидовое гнездо",
    "алидовое гнездо": "Алидовое гнездо",
    "аллидовое гнездо": "Алидовое гнездо",

    # ═══ Трупный Паразит ═══
    "трупный":              "Трупный Паразит",
    "паразит":              "Трупный Паразит",
    "трупный паразит":      "Трупный Паразит",

    # ═══ БТР / APC Подразделения BIO ═══
    "бтр":                  "БТР (APC) Подразделения BIO",
    "apc":                  "БТР (APC) Подразделения BIO",
    "апс":                  "БТР (APC) Подразделения BIO",
    "бронетранспортёр":     "БТР (APC) Подразделения BIO",
    "бронетранспортер":     "БТР (APC) Подразделения BIO",
    "броня":                "БТР (APC) Подразделения BIO",
    "бронемашина":          "БТР (APC) Подразделения BIO",
    "транспортёр":          "БТР (APC) Подразделения BIO",
    "транспортер":          "БТР (APC) Подразделения BIO",
    "bio бтр":              "БТР (APC) Подразделения BIO",
    "бтр bio":              "БТР (APC) Подразделения BIO",
    "бтр подразделения":    "БТР (APC) Подразделения BIO",
}


def _extract_images_from_context(db_text: str) -> list[tuple[str, list[str]]]:
    """
    Извлекает пары (название, [url, ...]) из базы знаний.
    Поддерживает несколько URL на одной строке (через пробел).
    Формат: Название (Изображение) - https://url1 https://url2
    """
    results = []
    pattern = re.compile(
        r"^(.+?)\s*\(Изображение\)\s*[-–—]\s*((?:https?://\S+\s*)+)",
        re.IGNORECASE | re.MULTILINE
    )
    for m in pattern.finditer(db_text):
        name = m.group(1).strip()
        urls = re.findall(r"https?://\S+", m.group(2))
        if urls:
            results.append((name, urls))
    return results


def _strip_image_lines(db_text: str) -> str:
    """Убирает строки с изображениями из базы знаний перед отправкой ИИ."""
    pattern = re.compile(
        r"^.+?\s*\(Изображение\)\s*[-–—]\s*(?:https?://\S+\s*)+$",
        re.IGNORECASE | re.MULTILINE
    )
    return pattern.sub("", db_text).strip()

def _find_relevant_images(query: str, ai_response: str, db_text: str) -> list[str]:
    images = _extract_images_from_context(db_text)
    if not images:
        return []

    # ⚠️ Матчим ТОЛЬКО по запросу пользователя — не по тексту ИИ.
    # Иначе описание в ответе ("органиевую соту", "закупоренного спора")
    # тянет лишние картинки.
    query_raw = query.lower()

    query_aliased = query_raw
    for alias, canonical in _IMAGE_ALIASES.items():
        query_aliased = query_aliased.replace(alias, canonical.lower())

    scored: list[tuple[int, list[str], str]] = []

    def _match(word: str, text: str) -> bool:
        if re.search(r'\b' + re.escape(word) + r'\b', text):
            return True
        if len(word) >= 4 and re.search(r'\b' + re.escape(word), text):
            return True
        if len(word) >= 6:
            stem = word[:-2]
            if len(stem) >= 4 and re.search(r'\b' + re.escape(stem), text):
                return True
        return False

    for name, urls in images:
        name_lower = name.lower()

        # Полное вхождение названия в запрос
        base_score = 3 if _match(name_lower, query_aliased) else 0

        # Совпадение по словам названия (мин. 4 символа во избежание мусора)
        parts = re.findall(r"[а-яёa-z0-9][а-яёa-z0-9.\-]*", name_lower)
        word_score = sum(
            1 for p in parts
            if len(p) >= 4 and _match(p, query_aliased)
        )

        # Алиасы — проверяем в сыром запросе пользователя
        alias_score = 0
        for alias, canonical in _IMAGE_ALIASES.items():
            if canonical.lower() == name_lower and _match(alias, query_raw):
                alias_score += 4
                break

        total = base_score + word_score + alias_score
        if total > 0:
            scored.append((total, urls, name))

    scored.sort(key=lambda x: -x[0])

    for sc, urls, name in scored[:3]:
        _log(f"[IMG] Найдено: «{name}» (score={sc}) → {urls}")

    # Разворачиваем все URL найденных предметов (максимум 3 предмета)
    result_urls: list[str] = []
    for _, urls, _ in scored[:3]:
        result_urls.extend(urls)
    return result_urls


# ═══════════════════════════════════════════════════
#  MEMORY.TXT
# ═══════════════════════════════════════════════════

_MEMORY_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "memory.txt")
_MEMORY_MAX_CHARS = 512

def _load_memory() -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        with open(_MEMORY_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                key, _, val = line.partition(":")
                data[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return data


def _save_memory(data: dict[str, str]):
    with open(_MEMORY_PATH, "w", encoding="utf-8") as f:
        for key, val in sorted(data.items()):
            val = val[:_MEMORY_MAX_CHARS]
            f.write(f"{key}: {val}\n")


def _update_memory(callsign: str, topic: str, ai_impression: str = ""):
    mem = _load_memory()
    new_entry = f"Тема: {topic[:200]}"
    if ai_impression:
        new_entry += f" | {ai_impression[:250]}"
    mem[callsign] = new_entry[:_MEMORY_MAX_CHARS]
    _save_memory(mem)


def _get_memory_for(callsign: str) -> str:
    mem = _load_memory()
    return mem.get(callsign, "")


_ai_history: dict[int, list] = {}
_AI_MAX_HISTORY = 10


async def _ask_gemini(prompt: str) -> str | None:
    if not GEMINI_KEYS or GEMINI_KEYS[0].startswith("ВСТАВЬ"):
        return None
    for key in GEMINI_KEYS:
        timeout = aiohttp.ClientTimeout(total=GEMINI_TIMEOUT)
        try:
            url = f"{GEMINI_URL}?key={key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.85,
                    "maxOutputTokens": 1024,
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        try:
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            _log(f"[Gemini] Ответ получен ({len(text)} симв.)")
                            return text.strip()
                        except (KeyError, IndexError) as e:
                            _log(f"[Gemini] Неожиданный формат ответа: {e}")
                    elif resp.status == 429:
                        _log(f"[Gemini] Ключ {key[:12]}... — rate limit")
                    else:
                        body = await resp.text()
                        _log(f"[Gemini] HTTP {resp.status}: {body[:100]}")
        except asyncio.TimeoutError:
            _log(f"[Gemini] Ключ {key[:12]}... — таймаут")
        except Exception as e:
            _log(f"[Gemini] Ошибка: {e}")
    return None


async def _ask_apf(message: str) -> str | None:
    last_error = None
    for key in APF_KEYS:
        timeout = aiohttp.ClientTimeout(total=_APF_KEY_TIMEOUT)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    APF_URL,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {key}"},
                    json={"message": message, "model": "premium-default"},
                    timeout=timeout
                ) as resp:
                    data = await resp.json(content_type=None)
                    if data.get("success"):
                        return data["response"]
                    err_msg = data.get("error", str(data)[:100])
                    last_error = err_msg
                    if "rate limit" in str(err_msg).lower():
                        continue
        except asyncio.TimeoutError:
            last_error = "таймаут"
        except Exception as e:
            last_error = str(e)[:80]
    _log(f"[APF] Все ключи исчерпаны. Последняя ошибка: {last_error}")
    return None


async def _ask_ai(message: str) -> str:
    result = await _ask_apf(message)
    if result:
        return result
    raise RuntimeError("Все APF серверы недоступны.")


# ═══════════════════════════════════════════════════
#  VIP СПИСОК
# ═══════════════════════════════════════════════════

_VIP_CALLSIGNS = {"Вставьте Ваших Вип - Персон"}

_VIP_INFO = """Вип список сотрудников"""

_VIP_GENDER = {
    "Укажите пол Персоны": "м", ,
}


# ═══════════════════════════════════════════════════
#  on_message — ГЛАВНЫЙ ОБРАБОТЧИК
# ═══════════════════════════════════════════════════

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    is_mention = bot.user in message.mentions
    is_reply   = (
        message.reference is not None
        and message.reference.resolved is not None
        and isinstance(message.reference.resolved, discord.Message)
        and message.reference.resolved.author == bot.user
    )

    if not (is_mention or is_reply):
        await bot.process_commands(message)
        return

    # ── Проверка доступа по ролям ──
    if message.guild and isinstance(message.author, discord.Member):
        user_role_ids = {r.id for r in message.author.roles}
        if not (user_role_ids & AI_CHAT_ROLE_IDS):
            await message.reply("❌ У вас нет доступа к ИИ-чату.")
            return

    text = re.sub(rf"<@!?(?:{bot.user.id})>", "", message.content).strip()
    voice_action = _parse_voice_action(text)
    if voice_action:
        await _handle_voice_command(message, voice_action)
        return

    if not text:
        await message.reply("Слушаю. Какая информация требуется?")
        return

    sent = await message.reply("⏳ _Обработка запроса..._")

    # ── Серверный ник и позывной ──
    if message.guild and isinstance(message.author, discord.Member):
        server_nick = message.author.display_name
        clean_nick  = clean_name(message.author.display_name)
        bio_number  = extract_bio_number(message.author.display_name)
    else:
        server_nick = message.author.display_name
        clean_nick  = server_nick
        bio_number  = server_nick

    # ── Загрузка всей памяти ──
    all_memory = _load_memory()
    memory_block = ""
    if all_memory:
        lines = [f"  {k}: {v}" for k, v in sorted(all_memory.items())]
        memory_block = "\n[ДОСЬЕ ПЕРСОНАЛА — память о сотрудниках]\n" + "\n".join(lines) + "\n"

    is_vip = clean_nick in _VIP_CALLSIGNS

    history = _ai_history.setdefault(message.channel.id, [])
    history.append(f"{bio_number}: {text}")
    history_text = "\n".join(history[-_AI_MAX_HISTORY:])

    full_message = (
        "Ваш промпт ИИ тут.\n"
        "Отвечаешь по-русски\n"

        "═══ ОБРАЩЕНИЕ ═══\n"
        "Обращайся к сотрудникам так: .\n"
        "Если .\n\n"

        "═══ ПАМЯТЬ ═══\n"
        "В блоке [ДОСЬЕ ПЕРСОНАЛА] хранятся сведения о сотрудниках из прошлых разговоров.\n"
        "Если тебя спрашивают о конкретном сотруднике — ОБЯЗАТЕЛЬНО используй эти данные в ответе.\n"
        "В конце ответа ОБЯЗАТЕЛЬНО добавь строку в формате:\n"
        "[MEMORY_UPDATE] тема: <краткая тема разговора> | заметка: <твоё впечатление о сотруднике, до 200 символов>\n"
        "Эта строка будет вырезана и сохранена автоматически. Пиши её ВСЕГДА.\n\n"

        f"[ДОСЬЕ ПОДРАЗДЕЛЕНИЯ]\n{_VIP_INFO}\n\n"
        f"[СОТРУДНИК]\nСерверный ник: {server_nick}\nПозывной: {clean_nick}\nНомер: {bio_number}\n"
    )

    if is_vip:
        full_message += "⚠️ РЕЖИМ 1 АКТИВЕН — МАКСИМАЛЬНОЕ УВАЖЕНИЕ, БЕЗ САРКАЗМА\n\n"
    else:
        full_message += "РЕЖИМ 2 АКТИВЕН — лёгкий сарказм и снисходительность (без грубости)\n\n"

    full_message += (
        f"{memory_block}"
        f"[БАЗА ЗНАНИЙ РХБЗ]\n{_strip_image_lines(_db_context)}\n\n"
        f"[ИСТОРИЯ ДИАЛОГА]\n{history_text}\n\n"
        f"[ВОПРОС]\n{text}\n\n"
        "[ОТВЕТ SILICIUM]"
    )

    try:
        full_text = await _ask_ai(full_message)
        display_text = full_text
        if "[MEMORY_UPDATE]" in full_text:
            parts = full_text.split("[MEMORY_UPDATE]", 1)
            display_text = parts[0].rstrip()
            mem_line = parts[1].strip()
            topic = ""
            impression = ""
            for segment in mem_line.split("|"):
                segment = segment.strip()
                if segment.lower().startswith("тема:"):
                    topic = segment[5:].strip()
                elif segment.lower().startswith("заметка:"):
                    impression = segment[8:].strip()
            if topic or impression:
                try:
                    _update_memory(clean_nick, topic, impression)
                    _log(f"[MEMORY] Обновлена запись для {clean_nick}")
                except Exception as e:
                    _log(f"[MEMORY] Ошибка записи: {e}")

        for i in range(0, len(display_text), 5):
            if i % 25 == 0:
                await sent.edit(content=display_text[:i + 5] + "✍")
                await asyncio.sleep(0.05)

        final = display_text[:1990] + ("…" if len(display_text) > 1990 else "")
        await sent.edit(content=final)
        history.append(f"SILICIUM: {display_text}")

        image_urls = _find_relevant_images(text, display_text, _db_context)
        has_images = bool(image_urls)
        if image_urls:
            import hashlib
            _IMAGES_DIR = _os.path.join(_BOT_DIR, "images_db")
            _os.makedirs(_IMAGES_DIR, exist_ok=True)

            # Файл маппинга: url -> имя файла в images_db
            _URL_MAP_PATH = _os.path.join(_IMAGES_DIR, "_url_map.txt")

            def _load_url_map():
                mapping = {}
                try:
                    with open(_URL_MAP_PATH, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if "|" in line:
                                u, fname = line.split("|", 1)
                                mapping[u.strip()] = fname.strip()
                except FileNotFoundError:
                    pass
                return mapping

            def _save_url_map(mapping):
                with open(_URL_MAP_PATH, "w", encoding="utf-8") as f:
                    for u, fname in mapping.items():
                        f.write(f"{u}|{fname}\n")

            url_map = _load_url_map()

            for img_url in image_urls:
                try:
                    cached_path = None
                    ext = "png"

                    # Проверяем маппинг
                    if img_url in url_map:
                        candidate = _os.path.join(_IMAGES_DIR, url_map[img_url])
                        if _os.path.exists(candidate):
                            cached_path = candidate
                            ext = candidate.rsplit(".", 1)[-1] if "." in candidate else "png"
                            _log(f"[IMG] Из images_db (маппинг): {cached_path}")

                    # Проверяем по хешу
                    if not cached_path:
                        url_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
                        for ext_try in ("png", "jpg", "gif"):
                            candidate = _os.path.join(_IMAGES_DIR, f"{url_hash}.{ext_try}")
                            if _os.path.exists(candidate):
                                cached_path = candidate
                                ext = ext_try
                                _log(f"[IMG] Из images_db (хеш): {cached_path}")
                                break

                    # Скачиваем если нет в кеше
                    if not cached_path:
                        url_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
                        _log(f"[IMG] Скачиваю: {img_url}")
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
                        }
                        async with aiohttp.ClientSession() as session:
                            async with session.get(img_url, headers=headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                _log(f"[IMG] HTTP {resp.status} | Content-Type: {resp.headers.get('Content-Type','?')} | URL финальный: {resp.url}")
                                if resp.status != 200:
                                    _log(f"[IMG] ❌ Неудача HTTP {resp.status} для {img_url}")
                                    continue
                                img_data = await resp.read()
                                _log(f"[IMG] Получено байт: {len(img_data)}")
                                content_type = resp.headers.get("Content-Type", "image/png")
                                ext = "jpg" if "jpeg" in content_type else "gif" if "gif" in content_type else "png"
                                fname = f"{url_hash}.{ext}"
                                cached_path = _os.path.join(_IMAGES_DIR, fname)
                                with open(cached_path, "wb") as f:
                                    f.write(img_data)
                                url_map[img_url] = fname
                                _save_url_map(url_map)
                                _log(f"[IMG] ✅ Сохранено: {cached_path}")

                    if not cached_path:
                        _log(f"[IMG] ❌ cached_path пустой, пропускаем {img_url}")
                        continue

                    img_data = open(cached_path, "rb").read()
                    img_file = discord.File(io.BytesIO(img_data), filename=f"image.{ext}")
                    embed = discord.Embed(color=0xC8A84B)
                    embed.set_image(url=f"attachment://image.{ext}")
                    await message.channel.send(embed=embed, file=img_file)
                    _log(f"[IMG] ✅ Отправлено в Discord: image.{ext}")
                except Exception as e:
                    import traceback
                    _log(f"[IMG] ❌ Исключение для {img_url}: {e}\n{traceback.format_exc()}")

        if not has_images:
            await _handle_voice_response(message, display_text)

    except asyncio.TimeoutError:
        await sent.edit(content="⚠️ Сервер ИИ не ответил вовремя.")
    except Exception as e:
        await sent.edit(content=f"⚠️ Ошибка: {str(e)[:100]}")

    await bot.process_commands(message)



# ═══════════════════════════════════════════════════
#  ВОЙС-ЧАТ
# ═══════════════════════════════════════════════════

import edge_tts
import tempfile

VOICE_TRIGGER_ROLE_ID = 1288901873503436872
_voice_state: dict[int, dict] = {}


async def _generate_tts_audio(text: str) -> str:
    # Убираем markdown-изображения: ![alt](url)
    clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    
    # Убираем обычные ссылки в markdown: [text](url)
    clean_text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', clean_text)
    
    # Убираем голые URL
    clean_text = re.sub(r'https?://\S+', '', clean_text)
    
    # Убираем markdown-форматирование
    clean_text = clean_text.replace("**", "").replace("*", "").replace("_", "").replace("`", "")
    
    # Убираем лишние пробелы
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    if len(clean_text) > 1500:
        clean_text = clean_text[:1500] + "... текст обрезан для озвучивания."
    
    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()
    try:
        communicate = edge_tts.Communicate(clean_text, "ru-RU-DmitryNeural")
        await communicate.save(tmp_path)
        _log(f"[TTS] Сгенерирован аудио: {len(clean_text)} символов → {tmp_path}")
        return tmp_path
    except Exception as e:
        _log(f"[TTS] Ошибка генерации: {e}")
        raise


async def _play_audio_in_voice(voice_client: discord.VoiceClient, audio_path: str):
    try:
        while voice_client.is_playing():
            await asyncio.sleep(0.5)
        audio_source = discord.FFmpegPCMAudio(audio_path)
        voice_client.play(
            audio_source,
            after=lambda e: _log(f"[ВОЙС] Воспроизведение завершено{': ' + str(e) if e else ''}")
        )
        _log(f"[ВОЙС] Начато воспроизведение: {audio_path}")
        while voice_client.is_playing():
            await asyncio.sleep(1)
    except Exception as e:
        _log(f"[ВОЙС] Ошибка воспроизведения: {e}")
    finally:
        try:
            _os.remove(audio_path)
            _log(f"[TTS] Удалён временный файл: {audio_path}")
        except Exception:
            pass


def _get_voice_channel_with_trigger_role(guild: discord.Guild) -> discord.VoiceChannel | None:
    for channel in guild.voice_channels:
        for member in channel.members:
            if VOICE_TRIGGER_ROLE_ID in [r.id for r in member.roles]:
                return channel
    return None


async def _auto_voice_manager():
    await bot.wait_until_ready()
    _log("[ВОЙС] Менеджер автоподключения запущен")

    while not bot.is_closed():
        try:
            for guild in bot.guilds:
                voice_client = guild.voice_client
                target_channel = _get_voice_channel_with_trigger_role(guild)

                state = _voice_state.setdefault(guild.id, {"last_check": time.time(), "waiting_disconnect": False})

                if target_channel:
                    state["waiting_disconnect"] = False
                    if not voice_client or not voice_client.is_connected():
                        try:
                            await target_channel.connect()
                            _log(f"[ВОЙС] Подключён к '{target_channel.name}' на сервере '{guild.name}'")
                        except Exception as e:
                            _log(f"[ВОЙС] Ошибка подключения к '{target_channel.name}': {e}")
                    elif voice_client.channel.id != target_channel.id:
                        try:
                            await voice_client.move_to(target_channel)
                            _log(f"[ВОЙС] Перемещён в '{target_channel.name}' на сервере '{guild.name}'")
                        except Exception as e:
                            _log(f"[ВОЙС] Ошибка перемещения: {e}")
                else:
                    if voice_client and voice_client.is_connected():
                        if not state["waiting_disconnect"]:
                            state["waiting_disconnect"] = True
                            state["last_check"] = time.time()
                            _log(f"[ВОЙС] Сервер '{guild.name}': нет целевых участников, жду 3 сек...")
                        elif time.time() - state["last_check"] >= 3:
                            try:
                                await voice_client.disconnect()
                                _log(f"[ВОЙС] Отключён от войса на сервере '{guild.name}'")
                            except Exception as e:
                                _log(f"[ВОЙС] Ошибка отключения: {e}")
                            finally:
                                state["waiting_disconnect"] = False

        except Exception as e:
            _log(f"[ВОЙС] Ошибка в менеджере: {e}")

        await asyncio.sleep(5)


async def _handle_voice_response(message: discord.Message, ai_response: str):
    if not message.guild or not isinstance(message.author, discord.Member):
        return
    user_role_ids = {r.id for r in message.author.roles}
    if VOICE_TRIGGER_ROLE_ID not in user_role_ids:
        return
    if not message.author.voice or not message.author.voice.channel:
        return
    voice_client = message.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        return
    if voice_client.channel.id != message.author.voice.channel.id:
        return
    
    try:
        # Убираем всю markdown-разметку изображений для озвучки
        voice_text = re.sub(r'!\[.*?\]\(.*?\)', '', ai_response)
        voice_text = re.sub(r'https?://\S+', '', voice_text)
        voice_text = voice_text.strip()
        
        if not voice_text:
            _log(f"[ВОЙС] Текст пустой после очистки, пропускаем озвучку")
            return
            
        _log(f"[ВОЙС] Генерация TTS для {message.author.display_name}...")
        audio_path = await _generate_tts_audio(voice_text)
        _log(f"[ВОЙС] Воспроизведение TTS для {message.author.display_name}...")
        await _play_audio_in_voice(voice_client, audio_path)
        _log(f"[ВОЙС] TTS успешно воспроизведён для {message.author.display_name}")
    except Exception as e:
        _log(f"[ВОЙС] Ошибка озвучивания для {message.author.display_name}: {e}")


# ═══════════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user} (ID: {bot.user.id})")
    _log(f"Бот запущен: {bot.user}")

    bot.loop.create_task(_joke_scheduler())
    bot.loop.create_task(_auto_voice_manager())
    bot.loop.create_task(_preload_vosk())

    try:
        synced = await bot.tree.sync()
        print(f"✅ Синхронизировано {len(synced)} команд(а): {[c.name for c in synced]}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")


bot.run(BOT_TOKEN)
