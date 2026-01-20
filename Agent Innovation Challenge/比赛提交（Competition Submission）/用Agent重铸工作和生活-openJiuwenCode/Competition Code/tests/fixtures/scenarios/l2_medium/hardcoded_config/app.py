"""硬编码配置的代码 - 用于测试提取配置"""

import os


def connect_database():
    """连接数据库"""
    host = "localhost"
    port = 5432
    database = "myapp"
    user = "admin"
    password = "secret123"

    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    print(f"Connecting to {connection_string}")
    return connection_string


def send_email(to, subject, body):
    """发送邮件"""
    smtp_host = "smtp.gmail.com"
    smtp_port = 587
    sender = "noreply@myapp.com"

    print(f"Sending email from {sender} via {smtp_host}:{smtp_port}")
    print(f"To: {to}, Subject: {subject}")
    return True


def get_api_url(endpoint):
    """获取 API URL"""
    base_url = "https://api.myapp.com/v1"
    timeout = 30

    return f"{base_url}/{endpoint}"


def log_message(message, level="INFO"):
    """记录日志"""
    log_file = "/var/log/myapp/app.log"
    max_size = 10485760  # 10MB

    print(f"[{level}] {message} -> {log_file}")
