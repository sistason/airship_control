Simple control of an RC-airship via wifi and not much comfort.

### Hardware
- Raspberry Pi Zero W
- Raspberry ZeroCam (Fisheye)
- 2x Motors+ESC+Props
- 9g Servo for pitch-control
- BerryIMU

### Setup on Pi
- raspbian lite
- Wifi config via ifupd network/interfaces
- Control via python per interactive keyboard input
- Camerastream via raspivid (latency) wrapped in python

### Steps on Pi
- dd image && partprobe && mount p1+p2
- mkdir root/.ssh/ && vim authorized_keys
- touch boot/SSH && vim boot/wpa_supplicant.conf
- boot up
- passwd -d pi
- apt install git python3-pip pigpio
- git clone https://github.com/sistason/airship_control
- cd airship_control; pip3 -r airship/requirements.txt install
- raspi-config -> Serial enable
