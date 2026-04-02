"""
plugins/__init__.py
~~~~~~~~~~~~~~~~~~~
Exposes the aiohttp health-check web server used by bot.py.
All Pyrogram plugin handlers live in sibling modules and are loaded
automatically via plugins={"root": "plugins"}.
"""
from aiohttp import web


async def web_server():
    routes = web.RouteTableDef()

    @routes.get("/", allow_head=True)
    async def root_handler(request):
        return web.Response(text="LinkShareBot is alive ✅")

    @routes.get("/health")
    async def health_handler(request):
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.add_routes(routes)
    return app
