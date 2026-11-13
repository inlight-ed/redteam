import asyncio
import websockets

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
    
    async def listen(self, duration_sec: int = 10):
        try:
            import time
            start = time.time()
            while (time.time() - start) < duration_sec:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=duration_sec)
                if "PING" in msg:
                    await self.ws.send("PONG :tmi.twitch.tv")
                elif "PRIVMSG" in msg:
                    parts = msg.split(" ", 3)
                    if len(parts) >= 4:
                        user = parts[0].split("!")[0].lstrip(":")
                        channel = parts[2]
                        text = parts[3].lstrip(":").strip()
                        print(f"💬 [{channel}] {user}: {text}")
        except asyncio.TimeoutError:
            pass
    
    async def close(self):
        if self.ws:
            await self.ws.close()
            print("✅ IRC соединение закрыто")

async def test_irc_client():
    print("🧪 Тест IRC-клиента (анонимный режим)...")
    client = TwitchIRCClient(nickname="justinfan12345")
    try:
        await client.connect()
        await client.join_channel("twitch")
        print("⏳ Слушаем чат 10 секунд...")
        await client.listen(10)
        await client.close()
        print("✅ Тест завершён")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_irc_client())
