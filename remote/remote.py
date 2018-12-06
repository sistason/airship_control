#!/usr/bin/env python3
import time

from control import Control
from sensors import Sensors


class Remote:
    CONTROL_PORT = 8081
    VIDEO_PORT = 8082
    TUN_INTERFACE = "ptp-control"
    BIND_ADDRESS = "172.31.31.33"
    CLIENT_ADDRESS = "172.31.31.34"

    def __init__(self):
        self._shutdown = False

        self._sensors = Sensors(self)
        self._control = Control(self, self._sensors)

    def fly(self):
        while not self._shutdown:
            try:
                time.sleep(.1)
            except KeyboardInterrupt:
                self._shutdown = True

        self._control.stop()


if __name__ == '__main__':
    airship = Remote()
    airship.fly()
