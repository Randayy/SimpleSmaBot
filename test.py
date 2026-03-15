import asyncio
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync


# Main part of the code

SSID = '42["auth",{"session":"a:4:{s:10:\\"session_id\\";s:32:\\"1f0727efe11eca3deff98a709d0a9678\\";s:10:\\"ip_address\\";s:15:\\"217.196.163.237\\";s:10:\\"user_agent\\";s:117:\\"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36\\";s:13:\\"last_activity\\";i:1772491534;}c22ef6f61cc271c2bc8cc8be07f145d4","isDemo":0,"uid":125821224,"platform":1,"isFastHistory":true,"isOptimized":true}]'




async def main():
    async with PocketOptionAsync(SSID) as api:
        assets = await api.active_assets()
        regular = [a for a in assets if not a.get("is_otc")]
        print(f"Звичайних пар: {len(regular)}")
        for a in regular:
            print(a["symbol"], a["is_active"])

asyncio.run(main())

