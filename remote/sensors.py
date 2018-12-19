import subprocess
import threading
import time
import re


class Sensors:
    def __init__(self, remote):
        #TODO: IMU?
        self.remote = remote

        self._create_camera()

        self._camera_stream_thread = threading.Thread(target=self._stream_video)
        self._camera_stream_thread.daemon = True
        self._camera_stream_thread.start()

    @staticmethod
    def _create_camera():
        subprocess.call(['modprobe', 'bcm2835-v4l2'])
        ret = subprocess.call(["v4l2-ctl", "-v", "width=1280,height=720,pixelformat=H264",
                               "--set-ctrl=exposure_dynamic_framerate=1",
                               "--set-ctrl=video_bitrate=1000000",
                               "--set-ctrl=scene_mode=8"])
        return ret

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
                break
            except Exception as e:
                print("Exception while streaming: {}".format(e))
                proc = None
        if proc:
            proc.terminate()

    @staticmethod
    def get_wifi_rssi():
        wifi_link = subprocess.check_output(["/sbin/iw",  "dev", "wlan0", "link"])
        match = re.search(r'Signal: (-?\d+) dBm', str(wifi_link, 'utf-8'))
        if match:
            return match.group(1)
