import cgi
import http.server
import json

SUCCESS_RESPONSE = {
    'status': 'success',
    'message': 'Data received successfully.'
}
ERROR_RESPONSE = {
    'status': 'error',
    'message': 'Invalid data received.'
}

def task_func():
    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            content_type = self.headers.get('Content-Type')
            if content_type != 'application/json':
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'message': 'Content-Type header is not application/json'}).encode('utf-8'))
                return

            try:
                content_length = int(self.headers.get('Content-Length', 0))
            except (ValueError, TypeError):
                content_length = 0

            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
            except (json.JSONDecodeError, ValueError):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'message': 'Invalid JSON'}).encode('utf-8'))
                return

            if not isinstance(data, dict) or 'data' not in data:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'message': 'No data key in request'}).encode('utf-8'))
                return

            # Success
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(SUCCESS_RESPONSE).encode('utf-8'))

    return RequestHandler
