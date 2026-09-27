from flask import Flask
import os
from flask_mail import Mail

def task_func(app_name):
    # Get environment variables or use defaults
    mail_server = os.environ.get('MAIL_SERVER', 'localhost')
    mail_port = int(os.environ.get('MAIL_PORT', 25))
    
    # Handle MAIL_USE_TLS which might be a string in env vars
    mail_use_tls_raw = os.environ.get('MAIL_USE_TLS', 'False')
    if mail_use_tls_raw.lower() == 'true':
        mail_use_tls = True
    else:
        mail_use_tls = False

    mail_username = os.environ.get('MAIL_USERNAME')
    mail_password = os.environ.get('MAIL_PASSWORD')

    # Create Flask app instance
    app = Flask(app_name)

    # Configure mail settings
    app.config['MAIL_SERVER'] = mail_server
    app.config['MAIL_PORT'] = mail_port
    app.config['MAIL_USE_TLS'] = mail_use_tls
    app.config['MAIL_USERNAME'] = mail_username
    app.config['MAIL_PASSWORD'] = mail_password

    # Initialize Flask-Mail instance
    mail = Mail(app)

    return mail, app.config
