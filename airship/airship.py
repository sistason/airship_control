#!/usr/bin/env python3
import time

from control import Control
from sensors import Sensors


class Airship:
    def __init__(self):
        self._shutdown = False

        self._sensors = Sensors()
        self._control = Control()

    def fly(self):
        while not self._shutdown:
            current_inputs = self._control.get_inputs()
            self._control.set_inputs(current_inputs)

            time.sleep(.01)


if __name__ == '__main__':
    airship = Airship()
    airship.fly()