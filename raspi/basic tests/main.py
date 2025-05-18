import asyncio
import sys

HOST = '127.0.0.1'
PORT = 5001

client_writer = None

async def send_message(writer: asyncio.StreamWriter, msg: str) -> bool:
    try:
        writer.write(msg.encode())
        await writer.drain()
        print(f"Sent to client: {msg}")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

async def terminal_input_handler():
    global client_writer
    while True:
        user_input = await asyncio.to_thread(input, "Enter message to send: ")
        if user_input.lower() == 'exit':
            print("Exiting input handler...")
            break
        if client_writer is not None:
            await send_message(client_writer, user_input)
        else:
            print("No client connected. Wait for connection.")
        await asyncio.sleep(0.1)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global client_writer
    addr = writer.get_extra_info('peername')
    print(f"Connected to client at {addr}")
    client_writer = writer
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                print(f"Client {addr} disconnected")
                break
            message = data.decode().strip()
            print(f"Received from {addr}: {message}")
            cmd = message[0]
            if cmd == 't':
                startpos = int(message[1:message.index(",")])
                tactic = int(message[message.index(",")+1:])
                print(f"Tactic set: Startpos: {startpos} - tactic: {tactic}")
            elif cmd == 'p':
                pcmd = message[1:]
                print(f"pico command: {pcmd}")
            elif cmd == 'd':
                dist = int(message[1:])
                print(f"drive distance: {dist}")
            elif cmd == 'a':
                angle = int(message[1:])
                print(f"angle: {angle}")
            elif message.startswith('e0'):
                print("emergency stop")
            else:
                print(f"got shit: {message}")
    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        client_writer = None

async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addr = server.sockets[0].getsockname()
    print(f"Server running on {addr}")

    asyncio.create_task(terminal_input_handler())

    async with server:
        try:
            await server.serve_forever()
        except KeyboardInterrupt:
            print("Server shutting down...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)
