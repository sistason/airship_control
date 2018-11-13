#!/usr/bin/env python3
import time

from control import Control
from sensors import Sensors


class Airship:
    def __init__(self):
        self._shutdown = False

        self._sensors = Sensors()
        self._control = Control(self._sensors)


        self._telemetry_socket = socket.socket()
        self._telemetry_socket.bind(("127.0.0.1", 3334))
        self._telemetry_socket.listen(1)

    def fly(self):
        while not self._shutdown:
            current_inputs = self._control.get_inputs()
            self._control.set_inputs(current_inputs)

            time.sleep(.01)


if __name__ == '__main__':
    airship = Airship()
    airship.fly()