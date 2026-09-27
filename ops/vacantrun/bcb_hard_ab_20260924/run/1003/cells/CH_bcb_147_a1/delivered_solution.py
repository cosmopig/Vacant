import socket
from ipaddress import IPv4Network
from threading import Thread

def task_func(ip_range, port):
    network = IPv4Network(ip_range)
    results = {}

    def check_ip(ip):
        ip_str = str(ip)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((ip_str, port))
            results[ip_str] = True
            s.close()
        except (socket.timeout, ConnectionRefusedError, OSError):
            results[ip_str] = False

    threads = []
    for ip in network:
        t = Thread(target=check_ip, args=(ip,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results
