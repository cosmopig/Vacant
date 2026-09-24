import cgi
import http.server
import smtplib
from email.mime.text import MIMEText
import json

def task_func(smtp_server, smtp_port, smtp_username, smtp_password):
    class EmailHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length).decode('utf-8')
                
                try:
                    data = json.loads(post_data)
                except json.JSONDecodeError:
                    self.send_error(400, "Invalid JSON")
                    return

                subject = data.get('subject')
                message = data.get('message')
                to = data.get('to')

                if subject is None or message is None or to is None:
                    raise ValueError("Missing keys")

                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    try:
                        server.login(smtp_username, smtp_password)
                    except smtplib.SMTPAuthenticationError:
                        self.send_response(535)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b"Authentication Failed")
                        return

                    msg = MIMEText(message)
                    msg['Subject'] = subject
                    msg['To'] = to
                    server.sendmail(smtp_username, to, msg.as_string())

                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Success")

            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
            except ValueError:
                self.send_error(400, "Missing keys")
            except Exception as e:
                pass

    server = http.server.HTTPServer(('127.0.0.1', 8080), EmailHandler)
    server.serve_forever()
