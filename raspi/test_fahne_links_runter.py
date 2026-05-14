import socket

with socket.create_connection(('127.0.0.1', 5001), timeout=60) as s:
    s.settimeout(60)
    f = s.makefile('rw')
    # drain welcome message
    while True:
        line = f.readline().strip()
        print('<', line)
        if '───' in line and 'Status' not in line:
            break

    f.write('servo 8 158\n')
    f.flush()
    print('> servo 8 158')

    while True:
        line = f.readline().strip()
        if not line:
            continue
        print('<', line)
        if line.startswith('OK') or line.startswith('ERR'):
            break
