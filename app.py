from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"textgoboom is running")

if __name__ == "__main__":
    print(f"Starting textgoboom on port 8124")
    HTTPServer(("127.0.0.1", 8124), Handler).serve_forever()
