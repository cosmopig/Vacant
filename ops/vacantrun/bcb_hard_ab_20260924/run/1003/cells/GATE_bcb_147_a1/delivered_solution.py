import socket
from ipaddress import IPv4Network
from threading import Thread

def task_func(ip_range, port):
    network = IPv4Network(ip_range)
    results = {}
    threads = []
    # Since we need to write to a dictionary from multiple threads, 
    # and Python's dict assignment is atomic for single keys, it might be okay.
    # However, using a lock is safer if I were doing more complex operations.

    def check_ip(ip):
        ip_str = str(ip)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)  # Short timeout for scanning
                result = s.connect_ex((ip_str, port))
                results[ip_str] = (result == 0)
        except Exception:
            results[ip_str] = False

    for ip in network:
        t = Thread(target=check_ip, args=(ip,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results
