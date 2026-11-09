"""HTTP security and game API smoke tests."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
import hermie
import hermie_web

class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), hermie_web.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_root = hermie.ROOT
        hermie.ROOT = Path(self.tmp.name)

    def tearDown(self):
        hermie.ROOT = self.original_root
        self.tmp.cleanup()

    def req(self, method, path, headers=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.read()
        status = response.status
        connection.close()
        return status, result

    def test_status_requires_token(self):
        self.assertEqual(self.req("GET", "/api/pet")[0], 401)

    def test_status_with_token(self):
        code, body = self.req("GET", "/api/pet", {"X-Hermie-Token": hermie_web.TOKEN})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["name"], "Hermie")

    def test_mutation_requires_origin(self):
        body = json.dumps({"action": "feed"})
        headers = {"X-Hermie-Token": hermie_web.TOKEN, "Content-Type": "application/json"}
        self.assertEqual(self.req("POST", "/api/action", headers, body)[0], 403)

    def test_mutation_with_local_origin(self):
        body = json.dumps({"action": "feed"})
        host = "127.0.0.1:" + str(self.server.server_port)
        headers = {"X-Hermie-Token": hermie_web.TOKEN, "Content-Type": "application/json",
                   "Origin": "http://" + host, "Host": host}
        code, data = self.req("POST", "/api/action", headers, body)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)["snacks"], 2)

if __name__ == "__main__":
    unittest.main()
