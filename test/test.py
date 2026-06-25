import socket

from DataConverter import BUFFER_SIZE, DataConverter


SERVER_HOST = "127.0.0.1"
SERVER_PORT = 4848


def receive_packet(client_socket: socket.socket) -> bytes:
    data = b""
    while len(data) < BUFFER_SIZE:
        chunk = client_socket.recv(BUFFER_SIZE - len(data))
        if not chunk:
            raise ConnectionError("server closed the connection")
        data += chunk

    return data


def action_name(action_value: int) -> str:
    return {value: key for key, value in DataConverter.player_action.items()}[action_value]


def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER_HOST, SERVER_PORT))
    print("Connected to server")

    data = DataConverter(receive_packet(client_socket))
    print(data)

    while True:
        raw_message = input("send action number, or exit -> ").strip()
        if raw_message == "exit":
            break

        try:
            action = action_name(int(raw_message))
        except (ValueError, KeyError):
            print("invalid action")
            continue

        client_socket.sendall(data.send(action))
        data.recv(receive_packet(client_socket))
        print(data)

    client_socket.close()


if __name__ == "__main__":
    main()
