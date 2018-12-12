#!/usr/bin/env python3
import time
import json
import threading
import subprocess
import socketserver

from control import Control, ControlState
from sensors import Sensors


class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass


class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):
    control = None
    sensors = None
    client_socket = None

    def handle(self):
        self.client_socket = self.request[1]
        data = self.request[0].strip()
        target_state = json.loads(str(data, 'utf-8'))
        print(target_state)
        self.control.set_state(ControlState(target_state.get("throttle", 0),
                                            target_state.get("yaw", 0),
                                            target_state.get("climb", 0)))

    def send_telemetry(self):
        if self.client_socket is None:
            return
        telemetry = self.control.get_state()
        telemetry['wifi_rssi'] = self.sensors.get_wifi_rssi()

        self.client_socket.sendto(bytes(json.dumps(telemetry), "utf-8"), self.control.remote.CLIENT_ADDRESS)


class Remote:
    CONTROL_PORT = 8081
    VIDEO_PORT = 8082
    VPN_INTERFACE = "ptp-control"
    BIND_ADDRESS = "172.31.31.33"
    CLIENT_ADDRESS = "172.31.31.34"

    def __init__(self):
        self.shutdown = False

        self._start_vpn()

        timeout = 4
        while timeout > 0:
            try:
                self._control_server = ThreadedUDPServer((self.BIND_ADDRESS, self.CONTROL_PORT),
                                                         ThreadedUDPRequestHandler)
                break
            except OSError:
                timeout -= 1
                time.sleep(0.5)
        else:
            print("Timeout while connecting to remote...")
            return

        self.sensors = Sensors(self)
        self.control = Control(self, self.sensors)

        self._control_server.control = self.control
        self._control_server.sensors = self.sensors

        self._control_server_thread = threading.Thread(target=self._control_server.serve_forever)
        self._control_server_thread.daemon = True
        self._control_server_thread.start()

    def _check_vpn(self):
        if self.vpn_proc.returncode:
            print("restarting vpn...")
            self._start_vpn()

    def _start_vpn(self):
        self.vpn_proc = subprocess.Popen(["/usr/sbin/openvpn",
                                          "--proto", "tcp-server",
                                          "--dev-type", "tun",
                                          "--dev", self.VPN_INTERFACE,
                                          "--resolv-retry", "infinite",
                                          "--ifconfig", self.BIND_ADDRESS, self.CLIENT_ADDRESS,
                                          "--persist-key", "--persist-tun",
                                          "--secret", "secret.key",
                                          "--keepalive", "2", "5",
                                          "--verb", "1"])

    def fly(self):
        while not self.shutdown:
            try:
                time.sleep(1)
                self._check_vpn()
            except KeyboardInterrupt:
                self.shutdown = True

        self.stop()

    def stop(self):
        self.control.stop()
        self._control_server.shutdown()
        self._control_server_thread.join()
        self.vpn_proc.terminate()


if __name__ == '__main__':
    airship = Remote()
    airship.fly()
