import threading
import socketserver
from urllib.parse import unquote
import json
import time
import subprocess
from copy import copy

from gpiozero import PWMLED


class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass


class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):
    client = None
    control = None

    def handle(self):
        data = self.request.recv(1024)
        target_state = json.loads(str(data, 'utf-8'))
        print(target_state)
        self.control.set_state(ControlState(target_state.get("throttle", 0),
                                            target_state.get("yaw", 0),
                                            target_state.get("climb", 0)))

    def send_telemetry(self):
        self.request.sendto(bytes(json.dumps(self.control.get_state()), "utf-8"), self.control.remote.CLIENT_ADDRESS)


class ControlState:
    THREE_D = False # Allow throttle unter 0?

    def __init__(self, throttle, yaw, climb):
        self.throttle = throttle
        self.yaw = yaw
        self.climb = climb

        self._convert_to_motors()

    def _convert_to_motors(self):
        backwards_scale = -1 if self.throttle < 0 else 1
        backwards = -1 if backwards_scale and self.THREE_D else 0

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
        left_motor = int(left_motor * scale_factor * backwards) / 100.0
        right_motor = int(right_motor * scale_factor * backwards) / 100.0

        self.motor_left = self.percentage_2d_to_pwm(left_motor if self.THREE_D else self._3d_to_2d(left_motor))
        self.motor_right = self.percentage_2d_to_pwm(right_motor  if self.THREE_D else self._3d_to_2d(right_motor))
        self.servo_pitch = self.percentage_2d_to_pwm(self._3d_to_2d(self.climb))

    def _convert_to_2d(self, value):
        return value if self.THREE_D else self._3d_to_2d(value)

    @staticmethod
    def _2d_to_3d(value):
        return -1 + (value * 2)

    @staticmethod
    def _3d_to_2d(value):
        return (value + 1) / 2.0

    @staticmethod
    def pwm_to_percentage(pwm):
        perc = pwm*10 - 1
        if perc <= 0:
            return 0
        if perc >= 1:
            return 1
        return perc

    @staticmethod
    def percentage_2d_to_pwm(percentage):
        pwm = (percentage + 1) / 10
        if pwm < 0.0800:
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

    def __init__(self, remote, sensors):
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
        self.remote = remote

        proc = subprocess.call(["openvpn",
                                "--proto", "tcp-server",
                                "--dev-type", "tun",
                                "--dev", self.remote.TUN_INTERFACE,
                                "--resolv-retry", "infinite",
                                "--ifconfig", self.remote.BIND_ADDRESS, self.remote.CLIENT_ADDRESS,
                                "persist-key", "persist-tun",
                                "--secret", "secret.key",
                                "--keepalive", "2", "5"])

        ThreadedUDPServer.control = self
        self._control_server = ThreadedUDPServer((self.remote.BIND_ADDRESS, self.remote.CONTROL_PORT), ThreadedUDPRequestHandler)
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
