"""Access gateway: policy decisions, token lifecycle, auth switch, console login and isolation."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import httpx
from fastapi.testclient import TestClient

import access_gateway
from access_policy import api_decision, console_decision, mcp_level
from access_store import AccessStore


class PolicyTest(unittest.TestCase):
    def test_api_routes(self):
        cases = [
            ("GET", "/v1/default/banks/a/documents", ["a"], "read"),
            ("POST", "/v1/default/banks/a/memories/recall", ["a"], "read"),
            ("POST", "/v1/default/banks/a/memories", ["a"], "write"),
            ("DELETE", "/v1/default/banks/a/documents/x", ["a"], "write"),
            ("DELETE", "/v1/default/banks/a", ["a"], "manage"),
            ("PUT", "/v1/default/banks/new", ["new"], "manage"),
            ("PATCH", "/v1/default/banks/a/config", ["a"], "manage"),
            ("DELETE", "/v1/default/banks/a/memories", ["a"], "manage"),
            ("POST", "/v1/default/banks/a/webhooks", ["a"], "manage"),
            ("POST", "/ext/ingest/banks/a/sessions", ["a"], "write"),
            ("GET", "/ext/ingest/banks/a/jobs", ["a"], "read"),
        ]
        for method, path, banks, level in cases:
            with self.subTest(path=path, method=method):
                decision = api_decision(method, path)
                self.assertEqual((decision.kind, decision.banks, decision.level), ("bank", banks, level))

    def test_unknown_and_multi_bank_routes_are_admin_only(self):
        for method, path in [("POST", "/mcp/"), ("POST", "/mcp"), ("GET", "/metrics"), ("GET", "/docs"),
                             ("POST", "/v1/default/banks"), ("GET", "/v1/default/chunks/zzz_1")]:
            with self.subTest(path=path):
                self.assertEqual(api_decision(method, path).kind, "admin")

    def test_mcp_tool_levels_fail_closed(self):
        call = lambda name: json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name}})
        self.assertEqual(mcp_level(call("recall")), "read")
        self.assertEqual(mcp_level(call("list_documents")), "read")
        self.assertEqual(mcp_level(call("retain")), "write")
        self.assertEqual(mcp_level(call("some_new_tool")), "write")
        self.assertEqual(mcp_level(call("delete_bank")), "manage")
        self.assertEqual(mcp_level(b"not json"), "manage")
        self.assertEqual(mcp_level(json.dumps([json.loads(call("recall")), json.loads(call("retain"))])), "write")
        self.assertEqual(api_decision("POST", "/mcp/a/", call("retain")).level, "write")

    def test_chunks_and_downloads_resolve_their_bank(self):
        self.assertEqual(api_decision("GET", "/v1/default/chunks/my_bank_doc_3", grants=["my_bank"]).banks, ["my_bank"])
        self.assertEqual(api_decision("GET", "/v1/default/files/download/tenants/public/banks/b1/x.zip").banks, ["b1"])

    def test_console_routes(self):
        self.assertEqual(console_decision("GET", "/api/documents", "bank_id=a").banks, ["a"])
        self.assertEqual(console_decision("POST", "/api/recall", "", b'{"bank_id": "a"}').level, "read")
        self.assertEqual(console_decision("POST", "/api/memories/retain", "", b'{"bank_id": "a"}').level, "write")
        form = b'--x\r\nContent-Disposition: form-data; name="request"\r\n\r\n{"bank_id": "f"}\r\n--x--\r\n'
        self.assertEqual(console_decision("POST", "/api/files/retain", "", form, "multipart/form-data; boundary=x").banks, ["f"])
        self.assertEqual(console_decision("GET", "/zh-CN/banks/a").banks, ["a"])
        self.assertEqual(console_decision("DELETE", "/api/banks/a").level, "manage")
        self.assertEqual(console_decision("GET", "/api/stats/a").banks, ["a"])
        self.assertEqual(console_decision("POST", "/api/memories/retain", "", b"{}").kind, "admin")
        self.assertEqual(console_decision("GET", "/_next/static/x.js").kind, "public")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AccessStore(Path(self.tmp.name) / "access.sqlite")
        self.user = self.store.create_user("t", "alice", "correct-horse", "user")

    def tearDown(self):
        self.tmp.cleanup()

    def test_token_lifecycle_and_cap(self):
        self.store.set_grant("t", self.user["id"], "a", "manage")
        issued = self.store.issue_token("t", self.user["id"], "laptop", cap="read")
        principal = self.store.principal_for_token(issued["token"])
        self.assertTrue(principal.allows("a", "read"))
        self.assertFalse(principal.allows("a", "write"))
        self.assertFalse(principal.visible("b"))
        self.assertNotIn(issued["token"], (Path(self.tmp.name) / "access.sqlite").read_bytes().decode("latin-1"))
        self.store.revoke_token("t", issued["id"])
        self.assertIsNone(self.store.principal_for_token(issued["token"]))

    def test_expired_disabled_and_unknown_tokens_fail(self):
        expired = self.store.issue_token("t", self.user["id"], "old", days=0.000001)
        time.sleep(0.2)
        self.assertIsNone(self.store.principal_for_token(expired["token"]))
        live = self.store.issue_token("t", self.user["id"], "live")
        self.store.update_user("t", self.user["id"], disabled=True)
        self.assertIsNone(self.store.principal_for_token(live["token"]))
        self.assertIsNone(self.store.principal_for_token("hs_unknown"))

    def test_last_admin_cannot_be_removed(self):
        admin = self.store.create_user("t", "root", "correct-horse", "admin")
        with self.assertRaises(ValueError):
            self.store.update_user("t", admin["id"], role="user")
        with self.assertRaises(ValueError):
            self.store.delete_user("t", admin["id"])

    def test_password_rules_and_login(self):
        with self.assertRaises(ValueError):
            self.store.create_user("t", "bob", "short")
        self.assertIsNone(self.store.login("alice", "wrong-password"))
        session = self.store.login("alice", "correct-horse")
        principal, csrf = self.store.session(session)
        self.assertEqual(principal.username, "alice")
        self.store.update_user("t", self.user["id"], password="another-password")
        self.assertEqual(self.store.session(session), (None, None))

    def test_bootstrap_admin_writes_private_file_once(self):
        path = self.store.bootstrap_admin(Path(self.tmp.name) / "pw.txt")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertIsNone(self.store.bootstrap_admin(Path(self.tmp.name) / "pw2.txt"))


BANKS = {"banks": [{"bank_id": "a", "name": "A"}, {"bank_id": "b", "name": "B"}], "total": 2}


def mock_upstream(seen):
    def handler(request):
        seen.append(request)
        if request.url.path in ("/v1/default/banks", "/api/banks"):
            return httpx.Response(200, json=BANKS)
        return httpx.Response(200, json={"path": request.url.path})
    upstream = access_gateway.Upstream("http://upstream")
    upstream.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return upstream


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AccessStore(Path(self.tmp.name) / "access.sqlite")
        self.admin = self.store.create_user("t", "root", "correct-horse", "admin")
        self.alice = self.store.create_user("t", "alice", "alice-password", "user")
        self.bob = self.store.create_user("t", "bob", "bobby-password", "user")
        self.store.set_grant("t", self.alice["id"], "a", "write")
        self.store.set_grant("t", self.bob["id"], "b", "read")
        self.seen = []
        api = mock_upstream(self.seen)
        self.api = TestClient(access_gateway.api_app(self.store, api))
        self.console = TestClient(access_gateway.console_app(self.store, mock_upstream(self.seen), api))

    def tearDown(self):
        self.tmp.cleanup()

    def token(self, user, **kw):
        return {"Authorization": "Bearer " + self.store.issue_token("t", user["id"], "t", **kw)["token"]}

    def login(self, username, password):
        client = self.console
        client.cookies.clear()
        self.assertEqual(client.post("/access/login", json={"username": username, "password": password}).status_code, 200)
        return {"x-csrf-token": client.get("/access/api/me").json()["csrf"]}

    def test_api_requires_token_and_switch_bypasses(self):
        self.assertEqual(self.api.get("/v1/default/banks/a/documents").status_code, 401)
        self.assertEqual(self.api.post("/mcp/a/", json={}).json()["error"]["code"], -32001)
        self.assertEqual(self.api.get("/health").status_code, 200)
        self.store.set_auth_enabled("t", False)
        self.assertEqual(self.api.get("/v1/default/banks/a/documents").status_code, 200)
        self.store.set_auth_enabled("t", True)
        self.assertEqual(self.api.get("/v1/default/banks/a/documents").status_code, 401)

    def test_bank_scoping_levels_and_header_hygiene(self):
        alice = self.token(self.alice)
        self.assertEqual(self.api.get("/v1/default/banks/a/documents", headers=alice).status_code, 200)
        self.assertEqual(self.api.post("/ext/ingest/banks/a/sessions", headers=alice, content=b"x").status_code, 200)
        self.assertEqual(self.api.get("/v1/default/banks/b/documents", headers=alice).status_code, 403)
        self.assertEqual(self.api.delete("/v1/default/banks/a", headers=alice).status_code, 403)
        bob = self.token(self.bob)
        self.assertEqual(self.api.post("/v1/default/banks/b/memories", headers=bob, json={}).status_code, 403)
        capped = self.token(self.alice, cap="read")
        self.assertEqual(self.api.post("/ext/ingest/banks/a/sessions", headers=capped, content=b"x").status_code, 403)
        self.seen.clear()
        self.api.get("/v1/default/banks/a/documents", headers=dict(alice, **{"X-Hindsight-Account": "root"}))
        forwarded = self.seen[-1].headers
        self.assertNotIn("authorization", forwarded)
        self.assertEqual(forwarded["x-hindsight-account"], "alice")

    def test_bank_list_is_filtered_except_for_admin(self):
        listed = self.api.get("/v1/default/banks", headers=self.token(self.alice)).json()
        self.assertEqual(([b["bank_id"] for b in listed["banks"]], listed["total"]), (["a"], 1))
        listed = self.api.get("/v1/default/banks", headers=self.token(self.admin)).json()
        self.assertEqual(len(listed["banks"]), 2)
        self.assertEqual(self.api.post("/v1/default/banks", headers=self.token(self.alice), json={}).status_code, 403)

    def test_console_requires_login_and_isolates_banks(self):
        self.assertEqual(self.console.get("/api/banks").status_code, 401)
        page = self.console.get("/zh-CN/banks/a", follow_redirects=False)
        self.assertEqual((page.status_code, page.headers["location"].startswith("/access/login")), (303, True))
        csrf = self.login("alice", "alice-password")
        self.assertEqual([b["bank_id"] for b in self.console.get("/api/banks").json()["banks"]], ["a"])
        self.assertEqual(self.console.get("/api/documents?bank_id=a").status_code, 200)
        self.assertEqual(self.console.get("/api/documents?bank_id=b").status_code, 403)
        self.assertEqual(self.console.get("/zh-CN/banks/b", follow_redirects=False).status_code, 303)
        self.assertEqual(self.console.get("/access/api/state").status_code, 403)
        self.assertEqual(self.console.post("/access/api/users", json={}, headers=csrf).status_code, 403)
        self.seen.clear()
        self.console.get("/api/documents?bank_id=a")
        self.assertNotIn("hs_session", self.seen[-1].headers.get("cookie", ""))

    def test_console_off_switch_does_not_open_console(self):
        self.store.set_auth_enabled("t", False)
        self.assertEqual(self.console.get("/api/banks").status_code, 401)

    def test_upstream_redirects_and_cookies_survive_proxying(self):
        def handler(request):
            return httpx.Response(307, headers=[("location", "http://localhost:19998/dashboard?x=1"),
                                                ("set-cookie", "NEXT_LOCALE=en; Path=/"),
                                                ("set-cookie", "other=1; Path=/")])
        upstream = access_gateway.Upstream("http://127.0.0.1:19998")
        upstream.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        console = TestClient(access_gateway.console_app(self.store, upstream, mock_upstream(self.seen)))
        console.post("/access/login", json={"username": "root", "password": "correct-horse"})
        page = console.get("/", follow_redirects=False)
        self.assertEqual((page.status_code, page.headers["location"]), (307, "/dashboard?x=1"))
        self.assertEqual(len(page.headers.get_list("set-cookie")), 2)
        self.assertEqual(upstream.relative_location("https://example.com/x"), "https://example.com/x")

    def test_admin_flow_with_csrf(self):
        csrf = self.login("root", "correct-horse")
        self.assertEqual(self.console.post("/access/api/users", json={"username": "carol", "password": "carol-password"}).status_code, 403)
        created = self.console.post("/access/api/users", headers=csrf, json={
            "username": "carol", "password": "carol-password", "bank_id": "c", "permission": "read"}).json()
        issued = self.console.post(f"/access/api/users/{created['id']}/tokens", headers=csrf, json={"name": "cli"}).json()
        self.assertTrue(issued["token"].startswith("hs_"))
        carol = {"Authorization": "Bearer " + issued["token"]}
        self.assertEqual(self.api.get("/v1/default/banks/c/documents", headers=carol).status_code, 200)
        self.assertEqual(self.api.get("/v1/default/banks/a/documents", headers=carol).status_code, 403)
        state = self.console.get("/access/api/state").json()
        self.assertNotIn(issued["token"], json.dumps(state))
        self.assertEqual(len(state["banks"]), 2)
        self.assertEqual(self.console.put("/access/api/settings", headers=csrf, json={"auth_enabled": False}).json(),
                         {"auth_enabled": False})
        self.assertEqual(self.api.get("/v1/default/banks/a/documents").status_code, 200)
        self.assertEqual(self.console.delete(f"/access/api/users/{self.admin['id']}", headers=csrf).status_code, 400)
        self.console.delete(f"/access/api/tokens/{issued['id']}", headers=csrf)
        self.store.set_auth_enabled("t", True)
        self.assertEqual(self.api.get("/v1/default/banks/c/documents", headers=carol).status_code, 401)

    def test_admin_cannot_reset_own_password_and_lose_session(self):
        csrf = self.login("root", "correct-horse")
        own = self.console.patch(f"/access/api/users/{self.admin['id']}", headers=csrf, json={"password": "new-password-123"})
        self.assertEqual(own.status_code, 400)
        self.assertEqual(self.console.get("/access/api/me").status_code, 200)
        other = self.console.patch(f"/access/api/users/{self.alice['id']}", headers=csrf, json={"password": "new-password-123"})
        self.assertEqual(other.status_code, 200)

    def test_user_can_revoke_only_own_tokens(self):
        other = self.store.issue_token("t", self.bob["id"], "bob")
        own = self.store.issue_token("t", self.alice["id"], "alice")
        csrf = self.login("alice", "alice-password")
        self.assertEqual(self.console.delete(f"/access/api/tokens/{other['id']}", headers=csrf).status_code, 404)
        self.assertEqual(self.console.delete(f"/access/api/tokens/{own['id']}", headers=csrf).status_code, 200)
        self.assertIsNotNone(self.store.principal_for_token(other["token"]))
        self.assertIsNone(self.store.principal_for_token(own["token"]))


if __name__ == "__main__":
    unittest.main()
