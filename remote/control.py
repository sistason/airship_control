import threading
from copy import copy

from gpiozero import PWMLED, exc, Servo


class ControlState:
    THREE_D = False # Allow throttle unter 0?

    def __init__(self, throttle, yaw, climb):
        self.throttle = throttle
        self.yaw = yaw
        self.climb = climb

        #self._convert_to_motors_directional()
        self._convert_to_motors()
        self.servo_pitch = self.climb

    def _convert_to_motors_directional(self):
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

    def _convert_to_motors(self):
        self.motor_left = self.percentage_2d_to_pwm(self.throttle if self.THREE_D else self._3d_to_2d(self.throttle))
        self.motor_right = self.motor_left

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
        self._control_loop = None

        self.motor_left = PWMLED(22, frequency=1000)
        self.motor_left.value = 0
        #self.motor_right = PWMLED(24)
        #self.motor_right.value = 0

        self.servo_pitch = Servo(23)
        self.servo_pitch.value = 0

        self.target_state = ControlState(0, 0, 0)

        self.sensors = sensors
        self.remote = remote

        self._loop()

    def get_state(self):
        return {"current_state": {"motor_left": self.motor_left.value,
                                  #"motor_right": self.motor_right.value,
                                  "servo_pitch": self.servo_pitch.value},
                "target_state": self.target_state.to_json()}

    def set_state(self, input):
        self.target_state = input

    def _loop(self):
        target_state = copy(self.target_state)
        try:
            self.motor_left.value = target_state.motor_left
            #self.motor_right.value = target_state.motor_right
            self.servo_pitch.value = target_state.servo_pitch
        except exc.OutputDeviceBadValue:
            pass

        self.remote.control_server.send_telemetry()
        self._control_loop = threading.Timer(1.0 / self.CONTROL_LOOP_HERTZ, self._loop)
        self._control_loop.start()

    def stop(self):
        self._control_loop.cancel()

