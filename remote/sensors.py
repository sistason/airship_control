import subprocess
import threading
import time
import re


class Sensors:
    def __init__(self, remote):
        #TODO: IMU?
        self.remote = remote

        self._camera_stream_thread = threading.Thread(target=self._stream_video)
        self._camera_stream_thread.daemon = True
        self._camera_stream_thread.start()

    def _stream_video(self):
        proc = None
        while not self.remote.shutdown:
            try:
                if proc is None:
                    check_ip = subprocess.check_output(["ip", "ro"])
                    if str(check_ip).find(self.remote.BIND_ADDRESS):
                        proc = subprocess.Popen(["/usr/bin/raspivid","-t", "0", "-fps", "30", "-l",
                                                 "-h", "720", "-w", "1280",
                                                 "-o", "tcp://{}:{}".format(self.remote.BIND_ADDRESS,
                                                                            self.remote.VIDEO_PORT)],
                                                stdout=subprocess.DEVNULL)

                time.sleep(0.5)
                proc.poll()
                if proc.returncode:
                    proc = None

            except subprocess.CalledProcessError as e:
                print("CalledProcessError while streaming: {}".format(e))
                proc = None
            except KeyboardInterrupt:
                return
            except Exception as e:
                print("Exception while streaming: {}".format(e))
                proc = None

    @staticmethod
    def get_wifi_rssi():
        wifi_link = subprocess.check_output(["/sbin/iw",  "dev", "wlan0", "link"])
        match = re.search(r'Signal: (-?\d+) dBm', wifi_link)
        if match:
            return match.group(1)
