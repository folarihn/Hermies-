"""Standalone server: auth, origin protection and the pet API."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import hermie_web


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), hermie_web.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host = "127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"HERMIE_HOME": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def req(self, method, path, headers=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.read(), response.status, response.getheader("Content-Security-Policy")
        connection.close()
        return result

    def post(self, payload, **extra):
        headers = {"X-Hermie-Token": hermie_web.TOKEN, "Content-Type": "application/json",
                   "Origin": "http://" + self.host, "Host": self.host}
        headers.update(extra)
        body, status, _ = self.req("POST", "/api/action", headers, json.dumps(payload))
        return status, json.loads(body)

    def test_status_requires_token(self):
        self.assertEqual(self.req("GET", "/api/pet")[1], 401)
        self.assertEqual(self.req("GET", "/api/pet", {"X-Hermie-Token": "wrong"})[1], 401)

    def test_status_with_token(self):
        body, status, _ = self.req("GET", "/api/pet", {"X-Hermie-Token": hermie_web.TOKEN})
        self.assertEqual(status, 200)
        pet = json.loads(body)
        self.assertEqual((pet["name"], pet["recent"]), ("Hermie", []))

    def test_static_assets_are_served_with_csp(self):
        for path in ("/", "/app.js", "/hermie-view.js", "/style.css"):
            body, status, csp = self.req("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body)
            self.assertIn("default-src 'self'", csp)
        self.assertEqual(self.req("GET", "/../hermie.py")[1], 404)

    def test_mutation_requires_matching_local_origin(self):
        self.assertEqual(self.post({"action": "feed"}, Origin="")[0], 403)
        self.assertEqual(self.post({"action": "feed"}, Origin="http://evil.example")[0], 403)

    def test_mutation_with_local_origin(self):
        status, pet = self.post({"action": "feed"})
        self.assertEqual(status, 200)
        self.assertEqual(pet["snacks"], 2)
        self.assertEqual(pet["recent"][0]["kind"], "feed")

    def test_bad_input_is_a_400_not_a_crash(self):
        for payload in ({"action": "rename", "name": 5}, {"action": "rename", "name": ["x"]},
                        {"action": "nope"}, {"action": ["feed"]}, {}, [1, 2]):
            status, data = self.post(payload)
            self.assertEqual(status, 400, payload)
            self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
