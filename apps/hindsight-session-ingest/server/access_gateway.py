"""Hindsight access gateway: authentication, bank-level authorization and the admin console.

One process, two listeners:
  API port      Bearer tokens for /v1, /mcp and /ext; forwards to the loopback Hindsight API.
  Console port  Login session; /access/* is the admin console, everything else is the
                native control plane with every bank reference checked.

The auth switch only affects the API port. The console always requires a login.
Run: python access_gateway.py   (configuration via HS_GATEWAY_* environment variables)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import time
from urllib.parse import quote, urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse

from access_policy import ADMIN, PUBLIC, api_decision, console_decision, filter_banks
from access_store import AccessStore

MAX_BODY = 64_000_000
COOKIE = "hs_session"
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "content-length"}
STATIC = Path(__file__).resolve().parent / "access_console"
log = logging.getLogger("hindsight.access")


def with_headers(response, headers):
    # Append one by one: a dict would keep only the last of several Set-Cookie headers.
    for key, value in headers:
        response.headers.append(key, value)
    return response


def bearer(request):
    value = request.headers.get("authorization", "")
    return value[7:].strip() if value.lower().startswith("bearer ") else value.strip()


def denied(status, message, mcp=False):
    if mcp:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": message}},
                            status_code=status, headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)
    return JSONResponse({"detail": message}, status_code=status,
                        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)


def authorize(principal, decision):
    """None when allowed, else an error message."""
    if decision.kind == PUBLIC:
        return None
    if decision.kind == ADMIN:
        return None if principal.admin_allows(decision.level) else "需要管理员权限"
    if not decision.banks:
        return "无法确定访问的数据仓"
    for bank in decision.banks:
        if not principal.allows(bank, decision.level):
            return f"没有数据仓 {bank} 的 {decision.level} 权限"
    return None


class Upstream:
    def __init__(self, base):
        self.base = base.rstrip("/")
        parsed = urlsplit(self.base)
        # Absolute redirects to the loopback upstream must stay on the public gateway address.
        self.origins = {f"{parsed.scheme}://{host}:{parsed.port}" for host in
                        (parsed.hostname, "localhost", "127.0.0.1", "0.0.0.0")} if parsed.port else {self.base}
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10), trust_env=False)

    def relative_location(self, value):
        for origin in self.origins:
            if value == origin or value.startswith(origin + "/") or value.startswith(origin + "?"):
                return value[len(origin):] or "/"
        return value

    async def forward(self, request, body, principal=None, strip_cookie=None, filter_for=None):
        headers = [(k, v) for k, v in request.headers.items()
                   if k.lower() not in HOP and k.lower() != "authorization" and not k.lower().startswith("x-hindsight-")]
        if strip_cookie:
            headers = [(k, v) if k.lower() != "cookie" else
                       (k, "; ".join(p for p in v.split("; ") if not p.startswith(strip_cookie + "=")))
                       for k, v in headers]
        if principal is not None:
            headers.append(("x-hindsight-account", principal.username))
        url = self.base + request.url.path + ("?" + request.url.query if request.url.query else "")
        upstream = await self.client.send(
            self.client.build_request(request.method, url, headers=headers, content=body), stream=True)
        response_headers = [(k, v) for k, v in upstream.headers.multi_items() if k.lower() not in HOP
                            and k.lower() != "content-encoding"]
        response_headers = [(k, self.relative_location(v) if k.lower() == "location" else v)
                            for k, v in response_headers]
        if filter_for is not None and upstream.status_code == 200 \
                and "json" in upstream.headers.get("content-type", ""):
            raw = await upstream.aread()
            await upstream.aclose()
            try:
                data = filter_banks(json.loads(raw), filter_for)
            except ValueError:
                return Response(status_code=502)
            response_headers = [(k, v) for k, v in response_headers if k.lower() != "content-type"]
            return with_headers(JSONResponse(data), response_headers)

        async def stream():
            try:
                # Decoded bytes, matching the dropped content-encoding header.
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
        return with_headers(StreamingResponse(stream(), status_code=upstream.status_code), response_headers)


async def read_body(request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            raise ValueError("Request body is too large")
    return bytes(body)


def api_app(store, upstream):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    async def gateway(request: Request, path: str):
        mcp = request.url.path.startswith("/mcp")
        try:
            body = await read_body(request)
        except ValueError:
            return denied(413, "请求过大", mcp)
        if not store.auth_enabled():
            return await upstream.forward(request, body)
        decision = api_decision(request.method, request.url.path, body)
        if decision.kind == PUBLIC and not decision.filter_list:
            return await upstream.forward(request, body)
        principal = store.principal_for_token(bearer(request))
        if principal is None:
            return denied(401, "缺少或无效的访问令牌", mcp)
        decision = api_decision(request.method, request.url.path, body, principal.grants)
        problem = authorize(principal, decision)
        if problem:
            return denied(403, problem, mcp)
        filter_for = principal if decision.filter_list and not principal.is_admin else None
        return await upstream.forward(request, body, principal, filter_for=filter_for)

    return app


class LoginLimiter:
    """At most 8 failed logins per address within 10 minutes."""

    def __init__(self):
        self.failures = {}

    def blocked(self, address):
        recent = [t for t in self.failures.get(address, []) if time.time() - t < 600]
        self.failures[address] = recent
        return len(recent) >= 8

    def fail(self, address):
        self.failures.setdefault(address, []).append(time.time())


def console_app(store, control_plane, api, secure_cookie=False):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    limiter = LoginLimiter()

    async def bank_list(principal):
        try:
            listed = (await api.client.get(api.base + "/v1/default/banks")).json()
            listed = filter_banks(listed, principal).get("banks", [])
        except (httpx.HTTPError, ValueError, AttributeError):
            return []
        keys = ("bank_id", "name", "fact_count", "last_write_at", "created_at")
        return [{key: bank.get(key) for key in keys} for bank in listed if isinstance(bank, dict)]

    def current(request):
        return store.session(request.cookies.get(COOKIE))

    def require(request, admin=False):
        principal, csrf = current(request)
        if principal is None:
            return None, JSONResponse({"detail": "请先登录"}, status_code=401)
        if request.method not in ("GET", "HEAD") and request.headers.get("x-csrf-token") != csrf:
            return None, JSONResponse({"detail": "页面已过期，请刷新"}, status_code=403)
        if admin and not principal.is_admin:
            return None, JSONResponse({"detail": "需要管理员权限"}, status_code=403)
        return principal, None

    async def payload(request):
        try:
            data = await request.json()
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    def run(action):
        try:
            return JSONResponse(action() or {"ok": True})
        except KeyError:
            return JSONResponse({"detail": "对象不存在"}, status_code=404)
        except ValueError as error:
            return JSONResponse({"detail": str(error)}, status_code=400)

    @app.get("/access/login")
    async def login_page():
        return FileResponse(STATIC / "login.html", headers={"Cache-Control": "no-store"})

    @app.post("/access/login")
    async def login(request: Request):
        address = request.client.host if request.client else "?"
        if limiter.blocked(address):
            return JSONResponse({"detail": "失败次数过多，请 10 分钟后再试"}, status_code=429)
        data = await payload(request)
        session = store.login(str(data.get("username", "")), str(data.get("password", "")))
        if session is None:
            limiter.fail(address)
            await asyncio.sleep(0.5)
            return JSONResponse({"detail": "用户名或密码错误"}, status_code=401)
        response = JSONResponse({"ok": True})
        response.set_cookie(COOKIE, session, httponly=True, samesite="lax", secure=secure_cookie,
                            max_age=12 * 3600, path="/")
        return response

    @app.post("/access/logout")
    async def logout(request: Request):
        store.logout(request.cookies.get(COOKIE))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/access")
    @app.get("/access/")
    async def console_page(request: Request):
        if current(request)[0] is None:
            return RedirectResponse("/access/login?next=/access/", status_code=303)
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/access/static/{name}")
    async def static(name: str):
        path = (STATIC / name).resolve()
        if path.parent != STATIC.resolve() or not path.is_file():
            return Response(status_code=404)
        # Revalidate via ETag so console updates reach browsers immediately.
        return FileResponse(path, headers={"Cache-Control": "no-cache"})

    @app.get("/access/api/me")
    async def me(request: Request):
        principal, csrf = current(request)
        if principal is None:
            return JSONResponse({"detail": "请先登录"}, status_code=401)
        return {"id": principal.user_id, "username": principal.username, "role": principal.role,
                "grants": principal.grants, "csrf": csrf, "auth_enabled": store.auth_enabled(),
                "tokens": store.tokens(principal.user_id),
                "banks": [] if principal.is_admin else await bank_list(principal)}

    @app.get("/access/api/state")
    async def state(request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        return {"users": store.users(), "tokens": store.tokens(), "banks": await bank_list(principal),
                "auth_enabled": store.auth_enabled(), "audit": store.audit(100)}

    @app.post("/access/api/users")
    async def create_user(request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        data = await payload(request)

        def action():
            user = store.create_user(principal.username, str(data.get("username", "")).strip(),
                                     str(data.get("password", "")), str(data.get("role") or "user"),
                                     str(data.get("note") or ""))
            bank = str(data.get("bank_id") or "").strip()
            if bank:
                store.set_grant(principal.username, user["id"], bank, str(data.get("permission") or "write"))
            return user
        return run(action)

    @app.patch("/access/api/users/{user_id}")
    async def update_user(user_id: int, request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        data = await payload(request)
        if data.get("password") is not None and user_id == principal.user_id:
            # Resetting yourself ends your session before the new password can be copied.
            return JSONResponse({"detail": "请用顶栏的“修改密码”修改自己的密码"}, status_code=400)
        return run(lambda: store.update_user(principal.username, user_id, role=data.get("role"),
                                             disabled=data.get("disabled"), note=data.get("note"),
                                             password=data.get("password")))

    @app.delete("/access/api/users/{user_id}")
    async def delete_user(user_id: int, request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        if user_id == principal.user_id:
            return JSONResponse({"detail": "不能删除当前登录的账号"}, status_code=400)
        return run(lambda: store.delete_user(principal.username, user_id))

    @app.put("/access/api/users/{user_id}/grants")
    async def set_grant(user_id: int, request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        data = await payload(request)
        return run(lambda: store.set_grant(principal.username, user_id, str(data.get("bank_id", "")).strip(),
                                           str(data.get("permission", ""))))

    @app.delete("/access/api/users/{user_id}/grants/{bank_id:path}")
    async def remove_grant(user_id: int, bank_id: str, request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        return run(lambda: store.remove_grant(principal.username, user_id, bank_id))

    @app.post("/access/api/users/{user_id}/tokens")
    async def issue_token(user_id: int, request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        data = await payload(request)
        return run(lambda: store.issue_token(principal.username, user_id, str(data.get("name") or ""),
                                             data.get("days") or None, data.get("cap") or None))

    @app.delete("/access/api/tokens/{token_id}")
    async def revoke_token(token_id: int, request: Request):
        principal, error = require(request)
        if error:
            return error
        # Users may revoke their own tokens; administrators may revoke any.
        owner = None if principal.is_admin else principal.user_id
        return run(lambda: store.revoke_token(principal.username, token_id, owner))

    @app.put("/access/api/settings")
    async def settings(request: Request):
        principal, error = require(request, admin=True)
        if error:
            return error
        data = await payload(request)
        if not isinstance(data.get("auth_enabled"), bool):
            return JSONResponse({"detail": "auth_enabled 必须是布尔值"}, status_code=400)
        store.set_auth_enabled(principal.username, data["auth_enabled"])
        return {"auth_enabled": store.auth_enabled()}

    @app.post("/access/api/password")
    async def change_password(request: Request):
        principal, error = require(request)
        if error:
            return error
        data = await payload(request)
        if not store.verify_password(principal.user_id, str(data.get("current", ""))):
            return JSONResponse({"detail": "当前密码不正确"}, status_code=400)
        return run(lambda: store.update_user(principal.username, principal.user_id,
                                             password=str(data.get("password", ""))) and None)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    async def control_plane_proxy(request: Request, path: str):
        principal, csrf = current(request)
        is_api = request.url.path.startswith("/api/")
        if principal is None:
            if is_api or request.method != "GET":
                return JSONResponse({"detail": "请先登录"}, status_code=401)
            return RedirectResponse("/access/login?next=" + quote(request.url.path), status_code=303)
        try:
            body = await read_body(request)
        except ValueError:
            return JSONResponse({"detail": "请求过大"}, status_code=413)
        decision = console_decision(request.method, request.url.path, request.url.query, body,
                                    request.headers.get("content-type", ""), principal.grants)
        problem = authorize(principal, decision)
        if problem:
            if is_api:
                return JSONResponse({"detail": problem, "error": problem}, status_code=403)
            return RedirectResponse("/access/?denied=" + quote(problem), status_code=303)
        filter_for = principal if decision.filter_list and not principal.is_admin else None
        return await control_plane.forward(request, body, principal, strip_cookie=COOKIE, filter_for=filter_for)

    return app


async def serve():
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    env = os.environ.get
    root = Path(env("HS_GATEWAY_HOME", "/opt/hindsight-research/access"))
    store = AccessStore(root / "access.sqlite")
    created = store.bootstrap_admin(root / "admin-initial-password.txt")
    if created:
        log.warning("Created administrator 'admin'; initial password is in %s", created)
    api = Upstream(env("HS_GATEWAY_API_UPSTREAM", "http://127.0.0.1:18887"))
    control_plane = Upstream(env("HS_GATEWAY_CONSOLE_UPSTREAM", "http://127.0.0.1:19998"))
    servers = []
    for listen, app in ((env("HS_GATEWAY_API_LISTEN", "0.0.0.0:18888"), api_app(store, api)),
                        (env("HS_GATEWAY_CONSOLE_LISTEN", "0.0.0.0:19999"),
                         console_app(store, control_plane, api, env("HS_GATEWAY_SECURE_COOKIE") == "1"))):
        host, port = listen.rsplit(":", 1)
        config = uvicorn.Config(app, host=host, port=int(port), proxy_headers=False, access_log=False,
                                timeout_keep_alive=30)
        servers.append(uvicorn.Server(config))
    await asyncio.gather(*(server.serve() for server in servers))


def command(argv):
    """Operator commands that work even when nobody can log in:
    auth on|off|status     switch API token checks (takes effect within 2 seconds)
    reset-admin USER       write a new random password for an administrator to a 0600 file
    """
    import secrets
    root = Path(os.environ.get("HS_GATEWAY_HOME", "/opt/hindsight-research/access"))
    store = AccessStore(root / "access.sqlite")
    if argv[:1] == ["auth"] and argv[1:2] in (["on"], ["off"]):
        store.set_auth_enabled("cli", argv[1] == "on")
    elif argv[:1] == ["reset-admin"] and len(argv) == 2:
        user = next((u for u in store.users() if u["username"] == argv[1] and u["role"] == "admin"), None)
        if user is None:
            raise SystemExit("No administrator with that name")
        password = secrets.token_urlsafe(15)
        store.update_user("cli", user["id"], password=password, disabled=False)
        path = root / ("admin-reset-" + time.strftime("%Y%m%d%H%M%S") + ".txt")
        path.write_text("username: " + argv[1] + "\npassword: " + password + "\n")
        path.chmod(0o600)
        print("New password written to " + str(path))
        return
    elif argv[:1] != ["auth"]:
        raise SystemExit(command.__doc__)
    print("API auth is " + ("on" if store.auth_enabled() else "off"))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        command(sys.argv[1:])
    else:
        asyncio.run(serve())
