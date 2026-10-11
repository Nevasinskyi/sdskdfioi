
import asyncio
import os
import random
from pathlib import Path
from datetime import datetime, timezone

from telethon import TelegramClient, events, utils
from telethon.errors import FloodWaitError
from telethon.tl.types import DocumentAttributeFilename

API_ID = 38637856
API_HASH = '0d04315595d268f6d6f5179a181f7c74'

SESSION = "user_session"
TEMPLATES_DIR = "templates"
MEDIA_DIR = Path("/storage/emulated/0/Download/exteraGram/troll")
os.makedirs(TEMPLATES_DIR, exist_ok=True)

client = TelegramClient(SESSION, API_ID, API_HASH)

async def finish(event, message):
    await event.respond(message)
    try:
        await event.delete()
    except Exception:
        pass

auto_replies = {}

tasks = {}


processed_messages = set()

async def send_long_message(target, text, reply_to=None, limit=4000):
    """Отправляет длинный текст несколькими сообщениями, не теряя содержимое."""
    if text is None:
        return
    text = str(text)
    if not text:
        await client.send_message(target, "", reply_to=reply_to)
        return

    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit + 1)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit + 1)
        if cut < limit // 2:
            cut = limit
        else:
            cut += 1
        chunks.append(text[:cut])
        text = text[cut:]
    if text:
        chunks.append(text)

    for index, chunk in enumerate(chunks):
        kwargs = {"reply_to": reply_to} if index == 0 and reply_to is not None else {}
        await client.send_message(target, chunk, **kwargs)


def load_template(name):
    if not name:
        return None
    path = os.path.join(TEMPLATES_DIR, name)
    if not os.path.exists(path):
        path2 = os.path.join(TEMPLATES_DIR, name + ".txt")
        if os.path.exists(path2):
            path = path2
        else:
            return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception:
        return None

def load_random_template_line(name):
    """Берёт одну непустую фразу из файла шаблона — одну строку за раз."""
    if not name:
        return None
    path = os.path.join(TEMPLATES_DIR, name)
    if not os.path.isfile(path) and os.path.isfile(path + ".txt"):
        path += ".txt"
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
        return random.choice(lines) if lines else ""
    except Exception:
        return None


def list_templates():
    return sorted([name for name in os.listdir(TEMPLATES_DIR)
                   if os.path.isfile(os.path.join(TEMPLATES_DIR, name))])

def resolve_template_name(arg):
    files = list_templates()
    if arg.isdigit():
        index = int(arg) - 1
        if 0 <= index < len(files):
            return files[index]
        return None
    if arg in files:
        return arg
    if arg + ".txt" in files:
        return arg + ".txt"
    return None

def parse_text_or_template(content_arg, quick_name):
    files = list_templates()
    if content_arg in files:
        return content_arg
    if content_arg + ".txt" in files:
        return content_arg + ".txt"
    with open(os.path.join(TEMPLATES_DIR, quick_name), "w", encoding="utf-8") as file:
        file.write(content_arg)
    return quick_name


async def save_command_media(event):
    if not event.message.media:
        return None
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    suffix = ".bin"
    if event.message.photo:
        suffix = ".jpg"
    elif event.message.video:
        suffix = ".mp4"
    elif event.message.document:
        name = getattr(event.message.file, "name", None)
        if name and "." in name:
            suffix = "." + name.rsplit(".", 1)[-1][:10]
    destination = MEDIA_DIR / f"media_{event.chat_id}_{event.id}{suffix}"
    try:
        return await event.message.download_media(file=str(destination))
    except Exception as exc:
        print(f"Не удалось сохранить вложение команды: {exc}")
        return None

async def resolve_target(event, value=None):
    """Получить пользователя из reply, ID или username."""
    if value:
        value = value.strip()

        if value.startswith("@"):
            value = value[1:]

        try:
            return await client.get_entity(value)
        except (ValueError, TypeError):
            return None
        except Exception:
            return None

    reply = await event.get_reply_message()

    if reply:
        sender = await reply.get_sender()

        if sender and getattr(sender, "id", None):
            return sender

    return None

def remember_task(name, coroutine):
    old_task = tasks.get(name)

    if old_task and not old_task.done():
        old_task.cancel()

    task = asyncio.create_task(coroutine)
    tasks[name] = task
    return task

def stop_all_tasks():
    for task in list(tasks.values()):
        if not task.done():
            task.cancel()

    tasks.clear()
    auto_replies.clear()

def make_message_link(chat, message):
    username = getattr(chat, "username", None)

    if username:
        return f"https://t.me/{username}/{message.id}"

    chat_id = utils.get_peer_id(chat)

    if chat_id < 0 and str(chat_id).startswith("-100"):
        return (
            f"https://t.me/c/"
            f"{str(chat_id)[4:]}/{message.id}"
        )

    return None

MENU = """⛧ mentaxy - system menu ⛧

⛧ !add reply / username / id + {шаблон / текст} + {задержка в секундах} - автоответчик
⛧ !sp reply / id / username + {шаблон / текст} + {задержка в секундах} - спам
⛧ !dl {количество сообщений} - удалить свои сообщения
⛧ !cf - меню с шаблонами
⛧ !scf + reply на сообщение - добавить текстовый шаблон
⛧ !dcf {номер / название шаблона} - удалить шаблон
⛧ !acf {номер / название шаблона} - выбрать шаблон
⛧ !kill - остановить активные задачи
⛧ !trk {шаблон / текст} - автоответчик чата
⛧ !check {reply / id / username} - последнее сообщение пользователя
⛧ !status - список активных задач
⛧ !tag {reply / id / username + текст / шаблон + задержка} - отложенный ответ
⛧ !infa - показывает это меню

⛧ own / dev t.me/ruharded
"""

@client.on(events.NewMessage(outgoing=True, pattern=r"^!infa$"))
async def cmd_info(event):
    await finish(event, MENU)

@client.on(events.NewMessage(outgoing=True, pattern=r"^!cf$"))
async def cmd_templates(event):
    files = list_templates()
    if not files:
        await finish(event, "шаблонов нет.\n\nдобавь через !scf + reply на файл.")
        return
    lines = ["шаблоны:\n"]
    for index, name in enumerate(files, 1):
        size = os.path.getsize(os.path.join(TEMPLATES_DIR, name))
        lines.append(f"{index}. {name}  -  {size} b")
    lines.append("\n!dcf номер/название - удалить")
    lines.append("!acf номер/название - выбрать")
    await finish(event, "\n".join(lines))

@client.on(events.NewMessage(outgoing=True, pattern=r"^!scf$"))
async def cmd_save_template(event):
    if not event.is_reply:
        await finish(event, "ответь на сообщение с файлом (.txt)")
        return
    reply = await event.get_reply_message()
    if not reply or not reply.document:
        await finish(event, "в реплае нет файла.")
        return
    name = None
    for attr in reply.document.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            name = attr.file_name
            break
    if not name:
        name = f"template_{int(time.time())}.txt"
    if not name.endswith(".txt"):
        name += ".txt"
    path = os.path.join(TEMPLATES_DIR, name)
    try:
        await reply.download_media(file=path)
        await finish(event, f"шаблон сохранён: {name}")
    except Exception as exc:
        await finish(event, f"ошибка: {exc}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^!dcf\s+(.+)$"))
async def cmd_delete_template(event):
    arg = event.pattern_match.group(1).strip()
    name = resolve_template_name(arg)
    if not name:
        await finish(event, "шаблон не найден.")
        return
    try:
        os.remove(os.path.join(TEMPLATES_DIR, name))
        await finish(event, f"удалён: {name}")
    except Exception as exc:
        await finish(event, f"{exc}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^!acf\s+(.+)$"))
async def cmd_activate_template(event):
    arg = event.pattern_match.group(1).strip()
    name = resolve_template_name(arg)
    if not name:
        await finish(event, "шаблон не найден.")
        return
    content = load_template(name)
    if content is None:
        await finish(event, "не удалось прочитать.")
        return
    chat_id = event.chat_id
    try:
        await event.delete()
    except Exception:
        pass
    await send_long_message(chat_id, content)

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r"^!add(?:\s+(.+))?$"
))
async def cmd_add(event):
    args = (event.pattern_match.group(1) or "").strip()

    if not args:
        await finish(event, 
            "Использование:\n"
            "!add @username имя_шаблона 2\n"
            "!add @username Ваш произвольный текст 2\n"
            "Или ответьте на сообщение:\n"
            "!add шаблон 2"
        )
        return

    parts = args.split()

    try:
        delay = float(parts[-1])
        if not 0 <= delay <= 3600:
            raise ValueError
    except ValueError:
        await finish(event, 
            "Последним аргументом укажите задержку от 0 до 3600 секунд."
        )
        return

    body = args[:args.rfind(parts[-1])].strip()

    if not body:
        await finish(event, "Укажите шаблон или текст.")
        return

    first = body.split(maxsplit=1)
    target = None

    if first[0].startswith("@") or first[0].lstrip("-").isdigit():
        target = await resolve_target(event, first[0])

        if target:
            body = first[1] if len(first) > 1 else ""

    if target is None:
        target = await resolve_target(event)

    if not target:
        await finish(event, 
            "Не удалось определить пользователя. "
            "Укажите username/ID или ответьте на его сообщение."
        )
        return

    if not body:
        await finish(event, "Укажите шаблон или текст.")
        return

    template_name = parse_text_or_template(body, f"quick_{target.id}.txt")
    content = load_template(template_name)

    if content is None:
        await finish(event, "Не удалось прочитать шаблон.")
        return

    key = (event.chat_id, target.id)

    media_path = await save_command_media(event)
    auto_replies[key] = {
        "text": content,
        "media": media_path,
        "delay": delay,
        "template": template_name,
        "last_message_id": None,
    }

    await finish(event, 
        f"Автоответчик включён.\n"
        f"Пользователь: {target.id}\n"
        f"Задержка: {delay} сек."
    )

@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    key = (event.chat_id, event.sender_id)

    if event.sender_id is None:
        return

    config = auto_replies.get(key)

    if not config:
        return

    if event.id == config["last_message_id"]:
        return

    if event.id in processed_messages:
        return

    processed_messages.add(event.id)

    if len(processed_messages) > 2000:
        processed_messages.clear()
        processed_messages.add(event.id)

    config["last_message_id"] = event.id
    delay = config["delay"]
    text = config["text"]
    template_name = config.get("template")
    # Для настоящего файла-шаблона выбираем одну фразу (одну строку) на ответ.
    # Текст, введённый прямо в команду (!add ...), остаётся без изменений.
    if template_name and not template_name.startswith("quick_"):
        line = load_random_template_line(template_name)
        if line is not None:
            text = line
    media_path = config.get("media")

    try:
        await asyncio.sleep(delay)

        if auto_replies.get(key) is not config:
            return

        if media_path and os.path.isfile(media_path):
            if len(text) <= 1024:
                await client.send_file(event.chat_id, media_path, caption=text, reply_to=event.id)
            else:
                await client.send_file(event.chat_id, media_path, reply_to=event.id)
                await send_long_message(event.chat_id, text)
        else:
            await send_long_message(event.chat_id, text, reply_to=event.id)

    except asyncio.CancelledError:
        raise
    except FloodWaitError as exc:
        print(f"Telegram FloodWait: ожидание {exc.seconds} сек.")
    except Exception as exc:
        print(f"Ошибка автоответчика: {exc}")

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r"^!check(?:\s+(.+))?$"
))
async def cmd_check(event):
    value = (event.pattern_match.group(1) or "").strip()

    target = await resolve_target(event, value or None)

    if not target:
        await finish(event, 
            "Укажите username/ID или ответьте на сообщение пользователя."
        )
        return

    try:
        messages = await client.get_messages(
            event.chat_id,
            limit=1,
            from_user=target,
        )

        if not messages:
            await finish(event, 
                f"Сообщения пользователя {target.id} не найдены "
                f"в текущем чате."
            )
            return

        msg = messages[0]
        sender_chat = await event.get_chat()
        link = make_message_link(sender_chat, msg)

        sent_at = (
            msg.date.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            if msg.date else "неизвестно"
        )

        result = [
            f"Пользователь: {target.id}",
            f"Последнее сообщение: {sent_at}",
            f"Текст: {(msg.raw_text or '[медиа]')[:500]}",
        ]

        if link:
            result.append(f"Ссылка: {link}")

        await finish(event, "\n".join(result))

    except Exception as exc:
        await finish(event, f"Ошибка проверки: {exc}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^!status$"))
async def cmd_status(event):
    lines = ["⛧ Статус ⛧", "", "Автоответчики:"]

    if auto_replies:
        for (chat_id, user_id), cfg in auto_replies.items():
            lines.append(
                f"Чат {chat_id}, пользователь {user_id}, "
                f"задержка {cfg['delay']} сек."
            )
    else:
        lines.append("Активных автоответчиков нет.")

    lines.extend(["", "Фоновые задачи:"])

    running = [
        name for name, task in tasks.items()
        if not task.done()
    ]

    lines.extend(running or ["Активных фоновых задач нет."])

    await finish(event, "\n".join(lines))

@client.on(events.NewMessage(outgoing=True, pattern=r"^!kill$"))
async def cmd_kill(event):
    count = len(auto_replies) + sum(
        1 for task in tasks.values() if not task.done()
    )

    stop_all_tasks()

    await finish(event, f"Остановлено процессов: {count}")

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r"^!dl\s+(\d+)$"
))
async def cmd_delete_messages(event):
    count = int(event.pattern_match.group(1))

    if not 1 <= count <= 100:
        await finish(event, "Укажите число от 1 до 100.")
        return

    chat = await event.get_input_chat()
    ids = []

    async for msg in client.iter_messages(chat, limit=200):
        if msg.out and msg.id != event.id:
            ids.append(msg.id)

            if len(ids) >= count:
                break

    try:
        if ids:
            await client.delete_messages(chat, ids)

        await event.delete()

    except Exception as exc:
        await finish(event, f"Не удалось удалить сообщения: {exc}")

@client.on(events.NewMessage(
    outgoing=True,
    pattern=r"^!(?:tag|sp)(?:\s+(.+))?$"
))
async def cmd_tag(event):
    args = (event.pattern_match.group(1) or "").strip()

    if not args:
        await finish(event, 
            "Использование:\n"
            "!tag @username Привет 5\n"
            "Или ответьте на сообщение:\n"
            "!tag имя_шаблона 5"
        )
        return

    parts = args.split()

    try:
        delay = float(parts[-1])
        if not 0 <= delay <= 3600:
            raise ValueError
    except ValueError:
        await finish(event, 
            "Последним аргументом укажите задержку от 0 до 3600 секунд."
        )
        return

    body = args[:args.rfind(parts[-1])].strip()
    first = body.split(maxsplit=1)

    target = None

    if first and (
        first[0].startswith("@")
        or first[0].lstrip("-").isdigit()
    ):
        target = await resolve_target(event, first[0])

        if target:
            body = first[1] if len(first) > 1 else ""

    if target is None:
        target = await resolve_target(event)

    if not target:
        await finish(event, 
            "Укажите username/ID или ответьте на сообщение пользователя."
        )
        return

    if not body:
        await finish(event, "Укажите шаблон или текст.")
        return

    template_name = parse_text_or_template(body, f"tag_{target.id}.txt")
    content = load_template(template_name)
    if content is not None and not template_name.startswith("tag_"):
        line = load_random_template_line(template_name)
        if line is not None:
            content = line

    if content is None:
        await finish(event, "Не удалось прочитать шаблон.")
        return

    media_path = await save_command_media(event)

    async def delayed_reply():
        await asyncio.sleep(delay)
        if media_path and os.path.isfile(media_path):
            if len(content) <= 1024:
                await client.send_file(target, media_path, caption=content)
            else:
                await client.send_file(target, media_path)
                await send_long_message(target, content)
        else:
            await send_long_message(target, content)

    task_name = f"tag:{target.id}:{event.id}"
    remember_task(task_name, delayed_reply())

    await finish(event, 
        f"Ответ запланирован пользователю {target.id} "
        f"через {delay} сек."
    )

async def main():
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    await client.start()

    me = await client.get_me()

    print("Mentaxion запущен.")
    print(f"Аккаунт: {me.id}")
    print("Команды: !infa")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Mentaxion остановлен.")

