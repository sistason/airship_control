#!/usr/bin/env python3
import time

from control import Control
from sensors import Sensors


class Airship:
    def __init__(self):
        self._shutdown = False

        self._sensors = Sensors()
        self._control = Control(self._sensors)

    def fly(self):
        while not self._shutdown:
            try:
                time.sleep(.1)
            except KeyboardInterrupt:
                self._shutdown = True

        self._control.stop()

if __name__ == '__main__':
    airship = Airship()
    airship.fly()
