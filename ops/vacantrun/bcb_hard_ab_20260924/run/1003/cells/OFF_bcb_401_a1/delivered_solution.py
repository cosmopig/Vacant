from flask import Flask
import os
from flask_mail import Mail

def task_func(app_name):
    app = Flask(app_name)
    
    mail_server = os.environ.get('MAIL_SERVER', 'localhost')
    mail_port = int(os.environ.get('MAIL_PORT', 25))
    mail_use_tls = os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true'
    mail_username = os.environ.get('MAIL_USERNAME')
    mail_password = os.environ.get('MAIL_PASSWORD')

    app.config['MAIL_SERVER'] = mail_server
    app.config['MAIL_PORT'] = mail_port
    app.config['MAIL_USE_TLS'] = mail_use_tls
    app.config['MAIL_USERNAME'] = mail_username
    app.config['MAIL_PASSWORD'] = mail_password

    mail = Mail(app)
    return mail, app.config
