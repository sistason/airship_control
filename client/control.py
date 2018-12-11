import pygame
import subprocess
import socket
import select
import threading
import json
import time
import copy


FUNCTIONS = {
    119: "throttle_more",   # w
    115: "throttle_less",   # s
     97: "yaw_left",        # a
    100: "yaw_right",       # d
    101: "climb_up",        # e
    113: "climb_down",      # q
    276: "yaw_left",        # ARROW_LEFT
    275: "yaw_right",       # ARROW_RIGHT
    273: "throttle_more",   # ARROW_UP
    274: "throttle_less",   # ARROW_DOWN
}


class State:
    def __init__(self, throttle, yaw, climb, font=None):
        self.throttle = throttle
        self.yaw = yaw
        self.climb = climb

        if font:
            self.font = font
        else:
            self.font = pygame.font.Font(None, 20)

    def to_json(self):
        return {"throttle": self.throttle/100.0, "yaw": self.yaw/100.0, "climb": self.climb/100.0}

    def to_data(self):
        return bytes(json.dumps(self.to_json()), 'utf-8')

    @staticmethod
    def from_json_data(data):
        return State(**json.loads(data.decode('utf-8')))

    def draw(self):
        return self.font.render("Throttle: {}  Yaw: {}  Pitch: {}".format(self.throttle, self.yaw, self.climb),
                                True, (255, 255, 255))

    def __eq__(self, other):
        return self.throttle == other.throttle and self.yaw == other.yaw and self.climb == other.climb


class TargetState(State):
    THROTTLE_SPEED = 1
    YAW_SPEED = 1
    CLIMB_SPEED = 1

    def __init__(self, throttle, yaw, climb, font=None):
        super().__init__(throttle, yaw, climb, font=font)

        self.functions = {
            "throttle_more": self.throttle_more,
            "throttle_less": self.throttle_down,
            "yaw_left": self.yaw_left,
            "yaw_right": self.yaw_right,
            "climb_up": self.climb_up,
            "climb_down": self.climb_down
        }

    def execute_functions(self, functions):
        [self.functions.get(f_, lambda: 1)() for f_ in functions]

    def throttle_more(self):
        self.throttle += self.THROTTLE_SPEED if self.throttle < 100 else 0

    def throttle_down(self):
        self.throttle -= self.THROTTLE_SPEED if self.throttle > -100 else 0

    def yaw_left(self):
        self.yaw -= self.YAW_SPEED if self.throttle > -100 else 0

    def yaw_right(self):
        self.yaw += self.YAW_SPEED if self.throttle < 100 else 0

    def climb_up(self):
        self.climb += self.CLIMB_SPEED if self.throttle < 100 else 0

    def climb_down(self):
        self.climb -= self.CLIMB_SPEED if self.throttle > -100 else 0


class AirshipController:
    def __init__(self, host="192.168.8.100"):
        self.shutdown = False
        self.host = host

        pygame.init()

        pygame.display.set_caption(str(self.__class__))

        # Set the width and height of the screen [width,height]
        size = [800, 600]
        self.screen = pygame.display.set_mode(size)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 20)

        # Initialize the joysticks
        pygame.joystick.init()

        self.pressed_functions = []

        self.target_state = TargetState(0, 0, 0, font=self.font)
        self.current_state = None

        self.tunnel = Tunnel(self)
        self.communicator = Communicator(self)
        self.video = Video(self)

        self.tunnel_thread = threading.Thread(target=self.tunnel.run)
        self.tunnel_thread.start()
        self.communicator_thread = threading.Thread(target=self.communicator.run)
        self.communicator_thread.start()
        self.video_thread = threading.Thread(target=self.video.run)
        self.video_thread.start()

    def run(self):
        try:
            while not self.shutdown:

                self.screen.fill((0, 0, 0))

                for event in pygame.event.get():  # User did something
                    if event.type == pygame.QUIT:  # If user clicked close
                        self.shutdown = True  # Flag that we are done so we exit this loop

                    # Possible joystick actions: JOYAXISMOTION JOYBALLMOTION JOYBUTTONDOWN JOYBUTTONUP JOYHATMOTION
                    if event.type == pygame.JOYBUTTONDOWN or event.type == pygame.KEYDOWN:
                        print("Joystick button '{}' pressed.".format(str(event.__dict__)))
                        function = FUNCTIONS.get(event.key)
                        self.pressed_functions.append(function)

                    if event.type == pygame.JOYBUTTONUP or event.type == pygame.KEYUP:
                        print("Joystick button released.")
                        try:
                            function = FUNCTIONS.get(event.key)
                            self.pressed_functions.remove(function)
                        except ValueError:
                            pass

                _old_state = copy.copy(self.target_state)
                self.target_state.execute_functions(self.pressed_functions)

                self.screen.blit(self.font.render("Target State:", True, (255, 255, 255)), [10, 10])
                self.screen.blit(self.target_state.draw(), [10, 20])
                if _old_state != self.target_state:
                    self.communicator.send_queue.append(self.target_state.to_data())

                self.screen.blit(self.font.render("Current State:", True, (255, 255, 255)), [10, 40])
                if self.current_state:
                    self.screen.blit(self.current_state.draw(), [10, 20])
                else:
                    self.screen.blit(self.font.render(" - ", True, (255, 255, 255)), [10, 20])


                # Go ahead and update the screen with what we've drawn.
                pygame.display.flip()

                # Limit to 20 frames per second
                self.clock.tick(20)

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        self.shutdown = True
        print("Stopping client...")

        self.tunnel_thread.join()
        self.communicator_thread.join()
        self.video_thread.join()


class Tunnel:
    def __init__(self, controller):
        self.controller = controller

    def run(self):
        proc = None
        while not self.controller.shutdown:
            if not proc:
                try:
                    proc = subprocess.Popen(["/usr/sbin/openvpn",
                                     "--proto", "tcp-client",
                                     "--dev-type", "tun",
                                     "--dev", "ptp-control",
                                     "--ifconfig", "172.31.31.34", "172.31.31.33",
                                     "--remote", self.controller.host,
                                     "--persist-key", "--persist-tun",
                                     "--secret", "secret.key",
                                     "--keepalive", "2", "5"])
                except subprocess.SubprocessError:
                    print("Error in VPN: {}".format(proc.communicate()))

            time.sleep(0.5)

        if proc:
            proc.kill()


class Communicator:
    CONTROL_PORT = 8081

    def __init__(self, controller):
        self.controller = controller
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_queue = []

    def run(self):
        while not self.controller.shutdown:
            try:
                self.control_socket.bind(("172.31.31.34", self.CONTROL_PORT))
            except OSError:
                time.sleep(0.5)
            break

        while not self.controller.shutdown:
            time.sleep(0.01)
            readable, writable, exceptional = select.select([self.control_socket], [self.control_socket], [self.control_socket])
            if self.send_queue and self.control_socket in writable:
                data = self.send_queue.pop()
                print('Sending {}...'.format(data))
                self.control_socket.sendto(data, ("172.31.31.33", self.CONTROL_PORT))
            if self.control_socket in readable:
                data = self.control_socket.recv(1024)
                if data:
                    self.controller.current_state = State.from_json_data(data)
                else:
                    self.control_socket.close()
                    return


class Video:
    VIDEO_PORT = 8082

    def __init__(self, controller):
        self.controller = controller
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def run(self):
        while not self.controller.shutdown:
            try:
                self.video_socket.bind(('172.31.31.34', self.VIDEO_PORT))
            except OSError:
                time.sleep(0.5)
            break

        while not self.controller.shutdown:
            time.sleep(0.5)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        ctrl = AirshipController(sys.argv[1])
    else:
        ctrl = AirshipController()
    ctrl.run()
