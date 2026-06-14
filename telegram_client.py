import asyncio
import sqlite3
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal
from telethon import TelegramClient
from telethon.tl.types import PeerChannel, Channel
from telethon.tl.functions.channels import CreateChannelRequest


class TelegramClientThread(QThread):
    connected = pyqtSignal(bool, str)
    file_list_ready = pyqtSignal(list)
    upload_progress = pyqtSignal(str, int, int)
    upload_done = pyqtSignal(str, bool, str)
    download_progress = pyqtSignal(str, int, int)
    download_done = pyqtSignal(str, bool, str)
    file_deleted = pyqtSignal(bool, str)
    otp_required = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    channels_ready = pyqtSignal(list)
    channel_created = pyqtSignal(dict)  # {id, title, username}

    def __init__(self, api_id: int, api_hash: str, session_path: str):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = str(session_path)
        self._client: Optional[TelegramClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._channel = None
        self._otp_event: Optional[asyncio.Event] = None
        self._otp_code = ""
        self._otp_phone = ""
        self._running = True

    def set_channel(self, channel_id: int):
        self._channel = channel_id

    def set_otp(self, code: str):
        self._otp_code = code
        if self._otp_event:
            self._otp_event.set()

    def set_phone(self, phone: str):
        self._otp_phone = phone

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._otp_event = asyncio.Event()
        self._client = TelegramClient(
            self.session_path, self.api_id, self.api_hash
        )

        try:
            for attempt in range(3):
                try:
                    self._loop.run_until_complete(self._client.connect())
                    break
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and attempt < 2:
                        self._loop.run_until_complete(asyncio.sleep(1))
                    else:
                        raise

            if not self._loop.run_until_complete(self._client.is_user_authorized()):
                self.otp_required.emit(
                    "Inserisci il codice OTP ricevuto su Telegram"
                )
                self._loop.run_until_complete(
                    self._client.send_code_request(self._otp_phone)
                )
                self._loop.run_until_complete(self._wait_for_otp())
                self._loop.run_until_complete(
                    self._client.sign_in(self._otp_phone, self._otp_code)
                )

            self.connected.emit(True, "Connesso")
            # Keep loop running until stop() is called
            while self._running:
                self._loop.run_until_complete(asyncio.sleep(0.1))
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.connected.emit(False, str(e))
        finally:
            try:
                self._loop.run_until_complete(self._client.disconnect())
            except Exception:
                pass
            self._loop.close()

    async def _wait_for_otp(self):
        await self._otp_event.wait()

    def _enqueue(self, coro):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        else:
            self.error_occurred.emit("Client non connesso")

    def list_files(self, channel: int):
        async def _list():
            try:
                results = []
                target = await self._client.get_entity(PeerChannel(channel))
                async for message in self._client.iter_messages(target):
                    if message.file:
                        results.append({
                            "message_id": message.id,
                            "filename": message.file.name or "unknown",
                            "size": message.file.size or 0,
                            "mime_type": message.file.mime_type or "",
                            "date": str(message.date),
                            "caption": message.message or "",
                        })
                self.file_list_ready.emit(results)
            except Exception as e:
                self.error_occurred.emit(str(e))

        self._enqueue(_list())

    def upload_file(self, channel: int, file_path: str, caption: str = "", op_id: str = ""):
        async def _upload():
            try:
                path = Path(file_path)
                target = await self._client.get_entity(PeerChannel(channel))

                def progress(current, total):
                    self.upload_progress.emit(op_id, current, total)

                await self._client.send_file(
                    target,
                    file_path,
                    caption=caption or path.name,
                    progress_callback=progress,
                )
                self.upload_done.emit(op_id, True, file_path)
            except Exception as e:
                self.error_occurred.emit(str(e))
                self.upload_done.emit(op_id, False, str(e))

        self._enqueue(_upload())

    def download_file(self, channel: int, message_id: int, output_dir: str, op_id: str = "", output_filename: str = ""):
        async def _download():
            try:
                target = await self._client.get_entity(PeerChannel(channel))
                message = await self._client.get_messages(target, ids=message_id)
                if not message or not message.file:
                    self.download_done.emit(op_id, False, "File non trovato")
                    return

                name = output_filename or message.file.name or f"file_{message_id}"
                out_path = Path(output_dir) / name
                out_path.parent.mkdir(parents=True, exist_ok=True)

                def progress(current, total):
                    self.download_progress.emit(op_id, current, total)

                await self._client.download_media(
                    message,
                    file=str(out_path),
                    progress_callback=progress,
                )
                self.download_done.emit(op_id, True, str(out_path))
            except Exception as e:
                self.error_occurred.emit(str(e))
                self.download_done.emit(op_id, False, str(e))

        self._enqueue(_download())

    def delete_file(self, channel: int, message_id: int):
        async def _delete():
            try:
                target = await self._client.get_entity(PeerChannel(channel))
                await self._client.delete_messages(target, [message_id])
                self.file_deleted.emit(True, str(message_id))
            except Exception as e:
                self.error_occurred.emit(str(e))
                self.file_deleted.emit(False, str(e))

        self._enqueue(_delete())

    def list_channels(self):
        async def _list():
            try:
                channels = []
                async for dialog in self._client.iter_dialogs():
                    if getattr(dialog, "is_channel", False):
                        channels.append({
                            "id": dialog.id,
                            "title": dialog.title,
                            "username": getattr(dialog.entity, "username", "") if dialog.entity else "",
                        })
                self.channels_ready.emit(channels)
            except Exception as e:
                self.error_occurred.emit(str(e))

        self._enqueue(_list())

    def create_channel(self, title: str, about: str = ""):
        """Crea un nuovo canale Telegram privato."""
        async def _create():
            try:
                result = await self._client(CreateChannelRequest(
                    title=title,
                    about=about,
                    megagroup=False,
                ))
                # result.chats contiene il canale creato
                ch = result.chats[0]
                self.channel_created.emit({
                    "id": ch.id,
                    "title": ch.title,
                    "username": getattr(ch, "username", "") or "",
                })
            except Exception as e:
                self.error_occurred.emit(str(e))

        self._enqueue(_create())

    def is_connected(self) -> bool:
        return self._running and self._loop is not None and self._loop.is_running()

    def stop(self):
        self._running = False
        self.wait(5000)
