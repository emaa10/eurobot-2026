import socket

def send(f, cmd):
    f.write(cmd + '\n')
    f.flush()
    print('>', cmd)
    while True:
        line = f.readline().strip()
        if not line:
            continue
        print('<', line)
        if line.startswith('OK') or line.startswith('ERR'):
            return

with socket.create_connection(('127.0.0.1', 5001), timeout=60) as s:
    s.settimeout(60)
    f = s.makefile('rw')
    # drain welcome message
    while True:
        line = f.readline().strip()
        print('<', line)
        if '───' in line and 'Status' not in line:
            break

    send(f, 'servo 7 3473')   # rechter Winker (ID 7) runter
    send(f, 'servo 8 158')    # linker  Winker (ID 8) runter
