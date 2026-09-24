import socket
from ipaddress import IPv4Network
from threading import Thread, Lock

def task_func(ip_range, port):
    network = IPv4Network(ip_range)
    results = {}
    lock = Lock()

    def check_port(ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)  # Short timeout for scanning
                result = s.connect_ex((str(ip), port))
                status = (result == 0)
        except Exception:
            status = False
        
        with lock:
            results[str(ip)] = status

    threads = []
    for ip in network:
        t = Thread(target=check_port, args=(ip,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results
