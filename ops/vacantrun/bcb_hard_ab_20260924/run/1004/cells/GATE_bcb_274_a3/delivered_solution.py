import cgi
import http.server
import smtplib
from email.mime.text import MIMEText
import json

def task_func(smtp_server, smtp_port, smtp_username, smtp_password):
    class EmailHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                return

            if not all(key in data for key in ('subject', 'message', 'to')):
                self.send_response(400)
                self.end_headers()
                return

            try:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.login(smtp_username, smtp_password)
                    msg = MIMEText(data['message'])
                    msg['Subject'] = data['subject']
                    msg['To'] = data['to']
                    server.sendmail(None, [data['to']], msg.as_string())
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Email sent successfully")
            except smtplib.SMTPAuthenticationError:
                self.send_response(535)
                self.end_headers()
            except ValueError:
                self.send_response(400)
                self.end_headers()
            except Exception as e:
                self.send_error(500, str(e))

    return EmailHandler
