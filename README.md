# PicoCar

A nimble, feature-packed robotic car powered by the **Raspberry Pi Pico W (RP2040)**. Designed for line-following, WiFi-control, FlySky RC Control and easy expandability, PicoCar serves as a versatile platform for embedded systems and robotics experimentation.

---

## ✨ Features
- **Precise Motor Control:** Differential drive setup supporting smooth forward, reverse, turning, and speed regulation.
- **Autonomous Navigation:** Real-time obstacle detection and avoidance using ultrasonic sensors & line-following with a 5-sensor array.
- **Wireless Control / Telemetry:** It can send light & distance data and receive controls from a WiFi WebServer. It can also use a Flysky radio (like the I6X in my case) to control the car.
- **Lightweight & Efficient:** Made on a small 65mm-wheel platform it is incredibly light and easy to use.

---

## 🛠️ Hardware Components

| Component | Description |
| :--- | :--- |
| **Microcontroller** | Raspberry Pi Pico W |
| **Motor Driver** | <a href="https://my.cytron.io/p-robo-pico-simplifying-robotics-with-raspberry-pi-pico?srsltid=AfmBOor6v5G5z6pB7KaFBMDgH33y66E1BaDct4PWbV_ZHkpGlH2xZ7rh&r=1">Cytron Robo Pico controller</a>|
| **Actuators** | 2x DC Gear Motors with 65mm wheels |
| **Sensor** | HC-SR04 Ultrasonic Distance Sensor |
| **Photoresistor** | <a href="https://robu.in/product/digital-ldr-module/">LDR Module</a> |
| **Buck Converter** | LM2596 set to 5.5v Output |
| **Radio** | TX=FS-I6X & RX=FS-IA6 |
| **LEDs** | 3mm Yellow LEDs |
| **Line follower** | <a href="https://robu.in/product/maker-line-simplifying-line-sensor-for-beginner/">Maker Line</a> |

---

## 📌 Pinout & Wiring Configuration

| Port | Connected To | Function |
| :--- | :--- | :--- |
| **GROVE7* | HC-SR04; Yellow=Trigger & White=echo| Obstacle Detection|
| **GROVE5** | Line follower sensor; Yellow=Analog | Line following |
| **GROVE4** | Indicator LEDs; Yellow=Left LED Anode & White=Right LED Anode | Turn Indicators |
| **GROVE2** | Photoresistor (LDR); Yellow=AO & White=DO | Light intensity |
| **Servo12** | Radio CH3 | Left motor speed |
| **Servo13** | Radio CH1 | Not used |
| **Servo14** | Radio CH2 | Right motor speed |
| **Servo15** | Radio CH4 | Not used |

---

## 🚀 Getting Started

### Prerequisites
* **Firmware:** CircuitPython installed on your Raspberry Pi Pico.
* **IDE:** Thonny IDE, VS Code (with Pico-W-Dev/CircuitPython extensions), or your preferred editor.

### Installation & Flashing
1. Clone the repository:
   ```bash
   git clone [https://github.com/ishitbhargava/PicoCar.git](https://github.com/ishitbhargava/PicoCar.git)
   cd PicoCar
   ```

2. Upload the firmware to the Pico W. Copy the code.py for the main code and all the libraries from the libraries folder.
4. Restart the Pico and you should hear the boot tone from the Pico and the ARGB Leds should turn on after a few seconds. Note that it takes around 5-6 seconds for it to boot.

---
