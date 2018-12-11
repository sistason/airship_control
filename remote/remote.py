#!/usr/bin/env python3
import time
import json
import threading
import socketserver

from control import Control, ControlState
from sensors import Sensors


class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass


class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):
    control = None
    sensors = None

    def handle(self):
        data = self.request.recv(1024)
        target_state = json.loads(str(data, 'utf-8'))
        print(target_state)
        self.control.set_state(ControlState(target_state.get("throttle", 0),
                                            target_state.get("yaw", 0),
                                            target_state.get("climb", 0)))

    def send_telemetry(self):
        telemetry = self.control.get_state()
        telemetry['wifi_rssi'] = self.sensors.get_wifi_rssi()

        self.request.sendto(bytes(json.dumps(telemetry), "utf-8"), self.control.remote.CLIENT_ADDRESS)


class Remote:
    CONTROL_PORT = 8081
    VIDEO_PORT = 8082
    TUN_INTERFACE = "ptp-control"
    BIND_ADDRESS = "172.31.31.33"
    CLIENT_ADDRESS = "172.31.31.34"

    def __init__(self):
        self.shutdown = False

        self.sensors = Sensors(self)
        self.control = Control(self, self.sensors)

        self._control_server = ThreadedUDPServer((self.BIND_ADDRESS, self.CONTROL_PORT), ThreadedUDPRequestHandler)
        self._control_server.control = self.control
        self._control_server.sensors = self.sensors

        self._control_server_thread = threading.Thread(target=self._control_server.serve_forever)
        self._control_server_thread.daemon = True
        self._control_server_thread.start()

    def fly(self):
        while not self.shutdown:
            try:
                time.sleep(.1)
            except KeyboardInterrupt:
                self.shutdown = True

        self.control.stop()
        self._control_server.shutdown()
        self._control_server_thread.join()


if __name__ == '__main__':
    airship = Remote()
    airship.fly()
