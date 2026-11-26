from __future__ import annotations

import gzip
import json
import struct
import threading
import uuid
import wave
from pathlib import Path
from queue import Queue

from ...models import Settings


def _packet(message_type: int, flags: int, sequence: int, payload: bytes) -> bytes:
    # Doubao SAUC v3 binary framing, protocol version 1, JSON + gzip.
    header = bytes([0x11, (message_type << 4) | flags, 0x11 if message_type == 1 else 0x01, 0])
    body = struct.pack(">iI", sequence, len(payload)) + payload
    return header + body


def _response_text(packet: bytes) -> tuple[str, bool]:
    if not isinstance(packet, bytes) or len(packet) < 4:
        raise RuntimeError("豆包流式 ASR 连接提前关闭")
    header_size = (packet[0] & 0x0F) * 4
    flags = packet[1] & 0x0F
    message_type = packet[1] >> 4
    payload = packet[header_size:]
    last = bool(flags & 0x02)
    if message_type == 0xF:
        code = struct.unpack(">i", payload[:4])[0] if len(payload) >= 4 else 0
        raise RuntimeError(f"豆包流式 ASR 返回错误（{code}）")
    if flags & 0x01:
        payload = payload[4:]
    if len(payload) < 4:
        return "", last
    size = struct.unpack(">I", payload[:4])[0]
    data = payload[4:4 + size]
    if packet[2] & 0x0F:
        data = gzip.decompress(data)
    value = json.loads(data.decode("utf-8"))
    result = value.get("result", value)
    if isinstance(result, dict):
        text = result.get("text")
        if isinstance(text, str):
            return text, last
        utterances = result.get("utterances")
        if isinstance(utterances, list):
            return "".join(str(item.get("text", "")) for item in utterances if isinstance(item, dict)), last
    return "", last


class DoubaoStream:
    chunk_size = 6400  # 200 ms of 16 kHz mono PCM16

    def __init__(self, connect):
        self.text = ""
        self.error: Exception | None = None
        self._audio: Queue[bytes | None] = Queue()
        self._cancelled = threading.Event()
        self._done = threading.Event()
        self._socket = None
        threading.Thread(target=self._receive, args=(connect,), daemon=True).start()

    def feed(self, data: bytes) -> None:
        if not self._done.is_set() and not self._cancelled.is_set():
            self._audio.put(data)

    def finish(self) -> str:
        self._audio.put(None)
        if not self._done.wait(8):
            self.cancel()
            raise TimeoutError("豆包流式 ASR 等待最终结果超时")
        if self.error is not None:
            raise self.error
        return self.text.strip()

    def cancel(self) -> None:
        self._cancelled.set()
        self._audio.put(None)
        if self._socket is not None:
            self._socket.abort()

    def _send(self, socket) -> None:
        buffer = bytearray()
        sequence = 2
        try:
            while not self._cancelled.is_set():
                data = self._audio.get()
                if self._cancelled.is_set():
                    return
                if data is None:
                    tail = bytes(buffer) or bytes(640)
                    socket.send_binary(_packet(2, 3, -sequence, gzip.compress(tail, compresslevel=1)))
                    return
                buffer.extend(data)
                while len(buffer) >= self.chunk_size:
                    chunk = bytes(buffer[:self.chunk_size])
                    del buffer[:self.chunk_size]
                    socket.send_binary(_packet(2, 1, sequence, gzip.compress(chunk, compresslevel=1)))
                    sequence += 1
        except Exception as exc:
            self.error = exc
            socket.abort()

    def _receive(self, connect) -> None:
        socket = None
        try:
            socket = self._socket = connect()
            if self._cancelled.is_set():
                return
            threading.Thread(target=self._send, args=(socket,), daemon=True).start()
            while not self._cancelled.is_set():
                current, last = _response_text(socket.recv())
                if current:
                    self.text = current
                if last:
                    return
        except Exception as exc:
            if self.error is None:
                self.error = exc
        finally:
            self._cancelled.set()
            self._audio.put(None)
            self._done.set()
            if socket is not None:
                socket.shutdown()


class DoubaoTranscriber:
    name = "doubao-asr"
    status = "ready"
    progress = 100
    is_ready = True
    last_error = ""

    def __init__(self, settings: Settings):
        self.settings = settings

    def load_model(self, status_callback=None):
        if status_callback:
            status_callback("豆包流式语音识别已就绪")

    def transcribe(self, audio_path: Path, status_callback=None) -> str:
        if status_callback:
            status_callback("豆包正在转写")
        with wave.open(str(audio_path), "rb") as source:
            if source.getparams()[:3] != (1, 2, 16000):
                raise RuntimeError("豆包流式 ASR 需要 16kHz 单声道 PCM")
            stream = self.open_stream()
            try:
                while frames := source.readframes(3200):
                    stream.feed(frames)
                return stream.finish()
            finally:
                stream.cancel()

    def open_stream(self) -> DoubaoStream:
        return DoubaoStream(self._connect)

    def _connect(self):
        key = self.settings.asr_api_key.strip()
        if not key:
            raise RuntimeError("请配置豆包 ASR_API_KEY")
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError("豆包流式 ASR 需要 websocket-client") from exc
        headers = {
            "X-Api-Key": key,
            "X-Api-Resource-Id": self.settings.asr_resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
        }
        request = json.dumps({
            "user": {"uid": "aura"},
            "audio": {"format": "pcm", "codec": "raw", "rate": 16000, "bits": 16, "channel": 1},
            "request": {"model_name": "bigmodel", "enable_itn": True, "enable_punc": True, "enable_ddc": True},
        }).encode()
        ws = websocket.create_connection(self.settings.asr_ws_url, header=[f"{k}: {v}" for k, v in headers.items()], timeout=5, enable_multithread=True)
        try:
            ws.send_binary(_packet(1, 1, 1, gzip.compress(request)))
            ws.settimeout(None)
            return ws
        except Exception:
            ws.shutdown()
            raise
