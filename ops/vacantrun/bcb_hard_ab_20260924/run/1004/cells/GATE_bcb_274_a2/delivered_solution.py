import cgi
import http.server
import smtplib
from email.mime.text import MIMEText
import json

def task_func(smtp_server, smtp_port, smtp_username, smtp_password):
    class EmailHandler(http.server.BaseHTTPRequestHandler):
        smtp_server = smtp_server
        smtp_port = smtp_port
        smtp_username = smtp_username
        smtp_password = smtp_password

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            if not all(key in data for key in ('subject', 'message', 'to')):
                # The goal says ValueError if keys are missing, leading to 400 Bad Request response.
                # In http.server, send_error(400) is the standard way to return a 400 error.
                self.send_error(400, "Missing keys")
                return

            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    msg = MIMEText(data['message'])
                    msg['Subject'] = data['subject']
                    msg['To'] = data['to']
                    server.sendmail(self.smtp_username, data['to'], msg.as_string())
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Email sent successfully")
            except smtplib.SMTPAuthenticationError:
                # The goal says 535 Authentication Failed response.
                # send_error(535) will set the status code to 535.
                self.send_error(535, "Authentication Failed")
            except Exception as e:
                self.send_error(500, str(e))

    return EmailHandler
