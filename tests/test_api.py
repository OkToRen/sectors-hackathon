import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from sectors.api import TransportError, urllib_transport


class Handler(BaseHTTPRequestHandler):
    seen: list[str | None] = []

    def do_GET(self) -> None:
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/landing")
            self.end_headers()
        elif self.path.startswith("/truncated"):
            self.send_response(503 if self.path.endswith("error") else 200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"{")
        else:
            Handler.seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

    def log_message(self, *args: object) -> None:
        pass


class TransportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        Handler.seen = []

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_redirect_is_returned_not_followed_with_the_key(self) -> None:
        response = urllib_transport(f"{self.base}/redirect", {"Authorization": "secret"})
        self.assertEqual(response.status, 302)
        self.assertEqual(Handler.seen, [])

    def test_truncated_body_is_a_transport_error(self) -> None:
        with self.assertRaises(TransportError):
            urllib_transport(f"{self.base}/truncated", {})
        with self.assertRaises(TransportError):
            urllib_transport(f"{self.base}/truncated-error", {})


if __name__ == "__main__":
    unittest.main()
