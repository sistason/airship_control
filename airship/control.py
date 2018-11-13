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
                                                target_state.get("climb", 0),
                                                type_=target_state.get("type", "perc")))
            self.send_response(201)
        else:
            self.send_response(404)


class State(object):
    def __init__(self, throttle, yaw, climb):
        self.throttle = throttle
        self.yaw = yaw
        self.climb = climb


class ControlState:
    def __init__(self, throttle, yaw, climb, type_='perc'):
        if type_ == 'perc':
            self.perc = State(throttle, yaw, climb)
            self.pwm = State(self.percentage_to_pwm(throttle),
                             self.percentage_to_pwm(yaw),
                             self.percentage_to_pwm(climb))
        else:
            self.pwm = State(throttle, yaw, climb)
            self.perc = State(self.pwm_to_percentage(throttle),
                              self.pwm_to_percentage(yaw),
                              self.pwm_to_percentage(climb))

        self._convert_to_motors()

    def _convert_to_motors(self):
        left_motor = self.perc.throttle + self.perc.yaw
        right_motor = self.perc.throttle - self.perc.yaw

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

        self.motor_left = self.percentage_to_pwm(left_motor)
        self.motor_right = self.percentage_to_pwm(right_motor)
        self.servo_pitch = self.pwm.climb

    def pwm_to_percentage(self, pwm):
        perc = pwm*10 - 1
        if perc <= 0:
            return 0
        if perc >= 1:
            return 1
        return perc

    def percentage_to_pwm(self, percentage):
        pwm = (percentage + 1) / 10
        if pwm <= 0:
            return 0
        if pwm >= 1:
            return 1
        return pwm


class Control:
    CONTROL_LOOP_HERTZ = 50

    def __init__(self, sensors):
        self.motor_left = PWMLED(22)
        self.motor_left.value = 0
        self.motor_right = PWMLED(23)
        self.motor_right.value = 0

        self.servo_pitch = PWMLED(24)
        self.servo_pitch.value = 0

        self.target_state = ControlState(0, 0, 0)

        self.sensors = sensors

        self._shutdown = False
        self._control_loop = threading.Timer(1.0/self.CONTROL_LOOP_HERTZ, self._loop_once, args=[self])
        self._control_loop.start()

        ControlHandler.control = self
        self._control_server = HTTPServer(('localhost', 8080), ControlHandler)
        self._control_server_thread = threading.Thread(target=self._control_server.serve_forever)
        self._control_server_thread.daemon = True
        self._control_server_thread.start()

    def get_state(self):
        return {"motor_left": self.motor_left.value,
                "motor_right": self.motor_right.value,
                "servo_pitch": self.servo_pitch.value,
                "target_state": self.target_state}

    def set_state(self, input):
        self.target_state = input

    def _loop_once(self):
        target_state = copy(self.target_state)
        self.motor_left.value = target_state.motor_left
        self.motor_right.value = target_state.motor_right
        self.servo_pitch.value = target_state.servo_pitch

    def stop(self):
        self._shutdown = True
        self._control_loop.cancel()
        self._control_server.shutdown()
        self._control_server_thread.join()
