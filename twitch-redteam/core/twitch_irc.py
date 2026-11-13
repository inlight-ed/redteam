import asyncio
import websockets
import time

class TwitchIRCClient:
    def __init__(self, nickname: str, oauth_token: str = None):
        self.nickname = nickname
        self.oauth_token = oauth_token
        self.ws = None
        self.connected = False
    
    async def connect(self):
        self.ws = await websockets.connect("wss://irc-ws.chat.twitch.tv:443")
        if self.oauth_token:
            await self.ws.send(f"PASS oauth:{self.oauth_token}")
        else:
            await self.ws.send("PASS SCHMOOPIIE")
        await self.ws.send(f"NICK {self.nickname}")
        while True:
            msg = await self.ws.recv()
            if "001" in msg:
                self.connected = True
                print(f"✅ Подключено к Twitch IRC как {self.nickname}")
                break
    
    async def join_channel(self, channel: str):
        channel = channel.lstrip("#").lower()
        await self.ws.send(f"JOIN #{channel}")
        print(f"✅ Присоединился к #{channel}")
    
    async def send_message(self, channel: str, message: str):
        """Отправляет сообщение в чат."""
        if not self.connected or not self.ws:
            raise RuntimeError("Не подключено к IRC")
        channel = channel.lstrip("#").lower()
        await self.ws.send(f"PRIVMSG #{channel} :{message}")
        # print(f"💬 Отправлено в чат: '{message}'") # Убрал дублирующий принт, так как он есть в основном скрипте
    
    async def listen(self, duration_sec: int = 10):
        try:
            start = time.time()
            while (time.time() - start) < duration_sec:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                if "PING" in msg:
                    await self.ws.send("PONG :tmi.twitch.tv")
                elif "PRIVMSG" in msg:
                    parts = msg.split(" ", 3)
                    if len(parts) >= 4:
                        user = parts[0].split("!")[0].lstrip(":")
                        ch = parts[2]
                        text = parts[3].lstrip(":").strip()
                        print(f"💬 [{ch}] {user}: {text}")
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
    
    async def close(self):
        if self.ws:
            await self.ws.close()
            print("✅ IRC соединение закрыто")
