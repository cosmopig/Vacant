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
    class DataHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            content_type = self.headers.get('Content-Type')
            if content_type != 'application/json':
                self.send_error(400, 'Content-Type header is not application/json')
                return

            try:
                content_length = int(self.headers.get('Content-Length', 0))
            except ValueError:
                content_length = 0

            body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                self.send_error(400, 'Invalid JSON')
                return

            if not isinstance(data, dict) or 'data' not in data:
                self.send_error(400, 'No data key in request')
                return

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps(SUCCESS_RESPONSE).encode('utf-8')
            self.wfile.write(response)

    return DataHandler
