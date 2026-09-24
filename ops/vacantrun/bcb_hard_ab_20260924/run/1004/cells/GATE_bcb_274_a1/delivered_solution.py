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
                data = json.loads(post_data)
            except json.JSONDecodeError:
                # The goal says JSONDecodeError results in a 400 Bad Request response.
                self.send_response(400)
                self.end_headers()
                return

            try:
                if not all(key in data for key in ('subject', 'message', 'to')):
                    raise ValueError("Missing keys")
                
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.login(smtp_username, smtp_password)
                    msg = MIMEText(data['message'])
                    msg['Subject'] = data['subject']
                    msg['To'] = data['to']
                    server.sendmail(smtp_username, data['to'], msg.as_string())
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Email sent successfully")
            except ValueError:
                # The goal says ValueError results in a 400 Bad Request response.
                self.send_response(400)
                self.end_headers()
            except smtplib.SMTPAuthenticationError:
                # The goal says smtplib.SMTPAuthenticationError results in a 535 Authentication Failed response.
                self.send_response(535)
                self.end_headers()
            except Exception as e:
                self.send_error(500, str(e))

    return EmailHandler
