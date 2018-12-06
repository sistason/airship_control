import subprocess
import threading
import socket


class Sensors:
    def __init__(self, remote):
        #TODO: init IMU
        #TODO: init Wifi RSSI?
        #TODO: Start Camera Stream
        #TODO: Start thread for data update (100Hz?)

        self.remote = remote

        #self._camera_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self._camera_socket.bind((self.airship.BIND_ADDRESS, self.airship.VIDEO_PORT))

        self._camera_stream_thread = threading.Thread(target=self._stream_video)
        self._camera_stream_thread.daemon = True
        self._camera_stream_thread.start()

    def _stream_video(self):
        while not self.remote._shutdown:
            try:
                check_ip = subprocess.check_output([
                    "ip ro | grep {}".format(self.remote.CLIENT_ADDRESS),
                ])
                if str(check_ip, "utf-8"):
                    ping = subprocess.check_output([
                        "ping -c 1 -w 1 {}".format(self.remote.CLIENT_ADDRESS),
                    ])
                    if str(ping, "utf-8"):
                        video = subprocess.run(["raspivid", "-o-"], stdout=subprocess.PIPE)
                        stream = subprocess.call(["nc", "-u", self.remote.CLIENT_ADDRESS, str(self.remote.VIDEO_PORT)], stdin=video.stdout)
            except subprocess.CalledProcessError as e:
                print("CalledProcessError while streaming: {}".format(e))
            except KeyboardInterrupt:
                return
            except Exception as e:
                print("Exception while streaming: {}".format(e))
