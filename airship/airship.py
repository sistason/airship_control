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
            time.sleep(.1)


if __name__ == '__main__':
    airship = Airship()
    airship.fly()
