Simple control of an RC-anything via wifi and not much comfort.

### Hardware Airship
- Raspberry Pi Zero W
- Raspberry ZeroCam (Fisheye)
- 2x Motors+ESC+Props
- 9g Servo for pitch-control
- BerryIMU

### Hardware RC-Car
- Raspberry Pi 3
- Raspberry Pi Cam (Wide Angle)
- RC-Car with ESC to Pi
- Steering to Pi
- (BerryIMU?)

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
- apt install git python3-pip pigpio openvpn
- git clone https://github.com/sistason/remote_control
- cd remote_control; pip3 -r remote/requirements.txt install
- raspi-config -> Serial enable
