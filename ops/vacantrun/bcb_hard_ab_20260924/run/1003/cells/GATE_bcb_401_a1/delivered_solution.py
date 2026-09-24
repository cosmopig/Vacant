from flask import Flask
import os
from flask_mail import Mail

def task_func(app_name):
    app = Flask(app_name)
    
    # Retrieve configurations from environment variables or use defaults
    mail_server = os.environ.get('MAIL_SERVER', 'localhost')
    
    mail_port_str = os.environ.get('MAIL_PORT', '25')
    try:
        mail_port = int(mail_port_str)
    except ValueError:
        mail_port = 25

    mail_use_tls_env = os.environ.get('MAIL_USE_TLS')
    if mail_use_tls_env is None:
        mail_use_tls = False
    else:
        # Common ways to represent boolean in env vars
        mail_use_tls = mail_use_tls_env.lower() in ('true', '1', 't', 'y', 'yes')

    mail_username = os.environ.get('MAIL_USERNAME', None)
    mail_password = os.environ.get('MAIL_PASSWORD', None)

    # Configure the app's mail configuration
    app.config['MAIL_SERVER'] = mail_server
    app.config['MAIL_PORT'] = mail_port
    app.config['MAIL_USE_TLS'] = mail_use_tls
    app.config['MAIL_USERNAME'] = mail_username
    app.config['MAIL_PASSWORD'] = mail_password

    # Initialize Flask-Mail instance
    mail = Mail(app)

    # The goal says: "The function should output with: tuple: A tuple containing the Flask-Mail instance and the app's mail configurations."
    # We need to extract the mail configuration from app.config.
    mail_configs = {
        'MAIL_SERVER': app.config['MAIL_SERVER'],
        'MAIL_PORT': app.config['MAIL_PORT'],
        'MAIL_USE_TLS': app.config['MAIL_USE_TLS'],
        'MAIL_USERNAME': app.config['MAIL_USERNAME'],
        'MAIL_PASSWORD': app.config['MAIL_PASSWORD'],
    }

    return mail, mail_configs
