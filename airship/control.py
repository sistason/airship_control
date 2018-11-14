import threading
import urllib
from urllib.parse import unquote
import json
import time
from copy import copy
from http.server import HTTPServer, BaseHTTPRequestHandler

from gpiozero import PWMLED


class ControlHandler(BaseHTTPRequestHandler):
    control = None

    def do_GET(self):
        # Telemetry
        self.send_response(200)
        self.send_header('Content-type', "text/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps(self.control.get_state()), "utf-8"))
        pass

    def do_POST(self):
        # Control
        content_length = int(self.headers['Content-Length'])    # Länge der Daten
        post_input = self.rfile.read(content_length)
        post_json = json.loads(unquote(str(post_input)[2:-1]))

        if "target_state" in post_json:
            target_state = post_json.get("target_state")
            self.control.set_state(ControlState(target_state.get("throttle", 0),
                                                target_state.get("yaw", 0),
                                                target_state.get("climb", 0)))
            self.send_response(201)
        else:
            self.send_response(404)


class ControlState:
    THREE_D = False # Allow throttle unter 0?

    def __init__(self, throttle, yaw, climb):
        self.throttle = throttle
        self.yaw = yaw
        self.climb = climb

        self._convert_to_motors()

    def _convert_to_motors(self):
        left_motor = self.throttle*100 + self.yaw*100
        right_motor = self.throttle*100 - self.yaw*100

        scale_factor = 1

        # Calculate scale factor
        if abs(left_motor) > 100 or abs(right_motor) > 100:
            # Find highest of the 2 values, since both could be above 100
            x = max(abs(left_motor), abs(right_motor))

            # Calculate scale factor
            scale_factor = 100.0 / x

        # Use scale factor, and turn values back into integers
        left_motor = int(left_motor * scale_factor)
        right_motor = int(right_motor * scale_factor)

        self.motor_left = self.percentage_2d_to_pwm(left_motor if self.THREE_D else self._3d_to_2d(left_motor))
        self.motor_right = self.percentage_2d_to_pwm(right_motor  if self.THREE_D else self._3d_to_2d(right_motor))
        self.servo_pitch = self.percentage_2d_to_pwm(self._3d_to_2d(self.climb))

    def _convert_to_2d(self, value):
        return value if self.THREE_D else self._3d_to_2d(value)

    def _2d_to_3d(self, value):
        return -1 + (value * 2)

    def _3d_to_2d(self, value):
        return (value + 1) / 2.0

    def pwm_to_percentage(self, pwm):
        perc = pwm*10 - 1
        if perc <= 0:
            return 0
        if perc >= 1:
            return 1
        return perc

    def percentage_2d_to_pwm(self, percentage):
        pwm = (percentage + 1) / 10
        if pwm < 0.800:
            return 0
        if pwm > 0.2200:
            return 0.2200
        return pwm

    def to_json(self):
        return {"throttle": self.throttle,
                "yaw": self.yaw,
                "climb": self.climb,
                "motor_left": self.motor_left,
                "motor_right": self.motor_right,
                "servo_pitch": self.servo_pitch}

    def __str__(self):
        return "L:{s.motor_left:3f} R:{s.motor_right:3f} P:{s.servo_pitch:3f}".format(s=self)


class Control:
    CONTROL_LOOP_HERTZ = 50

    def __init__(self, sensors):
        self._shutdown = False
        self._control_loop = None

        self.motor_left = PWMLED(22)
        self.motor_left.value = 0
        self.motor_right = PWMLED(23)
        self.motor_right.value = 0

        self.servo_pitch = PWMLED(24)
        self.servo_pitch.value = 0

        self.target_state = ControlState(0, 0, 0)

        self.sensors = sensors

        ControlHandler.control = self
        self._control_server = HTTPServer(('localhost', 8080), ControlHandler)
        self._control_server_thread = threading.Thread(target=self._control_server.serve_forever)
        self._control_server_thread.daemon = True
        self._control_server_thread.start()

        self._loop()

    def get_state(self):
        return {"current_state": {"motor_left": self.motor_left.value,
                                  "motor_right": self.motor_right.value,
                                  "servo_pitch": self.servo_pitch.value},
                "target_state": self.target_state.to_json()}

    def set_state(self, input):
        self.target_state = input

    def _loop(self):
        print(self.target_state)

        target_state = copy(self.target_state)
        self.motor_left.value = target_state.motor_left
        self.motor_right.value = target_state.motor_right
        self.servo_pitch.value = target_state.servo_pitch

        self._control_loop = threading.Timer(1.0 / self.CONTROL_LOOP_HERTZ, self._loop)
        self._control_loop.start()

    def stop(self):
        self._shutdown = True
        self._control_loop.cancel()
        self._control_server.shutdown()
        self._control_server_thread.join()
