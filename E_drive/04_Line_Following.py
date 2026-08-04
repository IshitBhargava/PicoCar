import time
import board
import analogio
import digitalio
import pwmio
import neopixel
import wifi
import socketpool
from adafruit_motor import motor
from adafruit_httpserver import Server, Request, Response, GET
import adafruit_hcsr04


factor = 0.15 #Adjustment factor for the motor drive system

# --- MOTOR HARDWARE SETUP ---
PWM_M1A, PWM_M1B = board.GP8, board.GP9
PWM_M2A, PWM_M2B = board.GP10, board.GP11

pwm_1a = pwmio.PWMOut(PWM_M1A, frequency=5000)
pwm_1b = pwmio.PWMOut(PWM_M1B, frequency=5000)
motorL = motor.DCMotor(pwm_1a, pwm_1b)
pwm_2a = pwmio.PWMOut(PWM_M2A, frequency=5000)
pwm_2b = pwmio.PWMOut(PWM_M2B, frequency=5000)
motorR = motor.DCMotor(pwm_2a, pwm_2b)

# Ultrasonic Sensor Setup
sonar = adafruit_hcsr04.HCSR04(trigger_pin=board.GP16, echo_pin=board.GP17)

# --- SENSORS & BUTTONS ---
SA = analogio.AnalogIn(board.GP26)

execute_button = digitalio.DigitalInOut(board.GP20)
execute_button.direction = digitalio.Direction.INPUT
execute_button.pull = digitalio.Pull.UP

mode_button = digitalio.DigitalInOut(board.GP21)
mode_button.direction = digitalio.Direction.INPUT
mode_button.pull = digitalio.Pull.UP

# --- PASSIVE BUZZER SETUP (GP22) ---
buzzer = pwmio.PWMOut(board.GP22, frequency=440, duty_cycle=0, variable_frequency=True)

OCTAVE_4 = {
    'c': 261.63, 'c#': 277.18, 'd': 293.66, 'd#': 311.13, 'e': 329.63,
    'f': 349.23, 'f#': 369.99, 'g': 392.00, 'g#': 415.30, 'a': 440.00,
    'a#': 466.16, 'b': 493.88, 'p': 0
}

def play_frequency(frequency, duration):
    if frequency > 0:
        buzzer.frequency = int(frequency)
        buzzer.duty_cycle = 32768
    else:
        buzzer.duty_cycle = 0
    time.sleep(duration)
    buzzer.duty_cycle = 0
    time.sleep(duration * 0.1)

def Read_Ultrasonic():
    time.sleep(0.1)
    return sonar.distance

def play_ms_string(play_str):
    tempo, default_length, current_octave = 120, 4, 4
    i = 0
    play_str = play_str.lower()
    while i < len(play_str):
        char = play_str[i]
        if char == 'm':
            i += 2
            continue
        elif char == 't':
            val = ""
            i += 1
            while i < len(play_str) and play_str[i].isdigit():
                val += play_str[i]
                i += 1
            if val: tempo = int(val)
            continue
        elif char == 'o':
            i += 1
            if i < len(play_str) and play_str[i].isdigit():
                current_octave = int(play_str[i])
                i += 1
            continue
        elif char == 'l':
            val = ""
            i += 1
            while i < len(play_str) and play_str[i].isdigit():
                val += play_str[i]
                i += 1
            if val: default_length = int(val)
            continue
        elif char in 'abcdefgp':
            note = char
            i += 1
            if i < len(play_str) and play_str[i] in ('#', '+'):
                note += '#'
                i += 1
            note_len_val = ""
            while i < len(play_str) and play_str[i].isdigit():
                note_len_val += play_str[i]
                i += 1
            length = int(note_len_val) if note_len_val else default_length
            duration = (240 / tempo) / length
            if note in OCTAVE_4:
                base_freq = OCTAVE_4[note]
                octave_shift = current_octave - 4
                frequency = base_freq * (2 ** octave_shift)
                play_frequency(frequency, duration)
            continue
        else:
            i += 1

# --- NEOPIXEL SETUP ---
pixels = neopixel.NeoPixel(board.GP18, 2, brightness=0.3, auto_write=True)
RED, GREEN, BLUE, MAGENTA, WHITE = (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 0, 255), (255, 255, 255)

def Robot_Movement(sL, sR):
    motorL.throttle = sL
    motorR.throttle = sR

# --- ULTRA-SIMPLIFIED UI ---
html_page = """<!DOCTYPE html><html><head>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<style>
    body { font-family: sans-serif; text-align: center; background: #222; color: white; }
    .grid { display: grid; grid-template-columns: repeat(3, 100px); gap: 10px; justify-content: center; margin-top: 50px; }
    button { width: 100px; height: 100px; font-size: 30px; background: #444; color: #fff; border: 2px solid #00adb5; border-radius: 15px; }
    button:active { background: #00adb5; }
    .stop { border-color: #ff2e63; color: #ff2e63; }
    .stop:active { background: #ff2e63; color: white; }
</style></head><body>
    <h1>Pico Robot</h1>
    <div class="grid">
        <td></td><button onclick="fetch('/f')">forward</button><td></td>
        <button onclick="fetch('/l')">left</button>
        <button class="stop" onclick="fetch('/s')">stop</button>
        <button onclick="fetch('/r')">right</button>
        <td></td><button onclick="fetch('/b')">back</button><td></td>
    </div>
</body></html>"""

# Global configuration variables
current_mode = 0  
robot_started = False
server = None

def setup_ap_mode():
    print("Starting Wi-Fi Access Point...")
    try:
        wifi.radio.start_ap(ssid="PicoW-Robot-Net", password="")
        print("AP Started! Network: 'PicoW-Robot-Net'")
        pool = socketpool.SocketPool(wifi.radio)
        
        server_instance = Server(pool, "/ ")
        
        @server_instance.route("/")
        def base(request: Request):
            return Response(request, html_page, content_type="text/html")

        @server_instance.route("/f")
        def forward(request: Request):
            Robot_Movement(0.85, (0.85+factor))
            return Response(request, "OK")

        @server_instance.route("/b")
        def backward(request: Request):
            Robot_Movement(-0.85, (-0.85-factor))
            return Response(request, "OK")

        @server_instance.route("/l")
        def left(request: Request):
            Robot_Movement(-0.5, (0.5+factor))
            return Response(request, "OK")

        @server_instance.route("/r")
        def right(request: Request):
            Robot_Movement(0.5, (-0.5-factor))
            return Response(request, "OK")

        @server_instance.route("/s")
        def stop(request: Request):
            Robot_Movement(0, 0)
            return Response(request, "OK")

        server_instance.start(port=80)
        return server_instance
    except Exception as e:
        print("Failed to start AP Mode:", e)
        return None

# --- BOOT STRING AREA ---
print("Playing requested MS PLAY string...")
my_melody = "MFT240L8 O4aO5dc O4aO5dc O4aO5dc L16dcdcdcdc"
play_ms_string(my_melody)

print("System Ready. Mode 0 (Line Follower). Press GP21 to cycle modes.")
pixels.fill(RED)

while True:
    # 1. Handle Mode Toggling (GP21) — cycles 0 → 1 → 2 → 0
    if not mode_button.value:
        current_mode = (current_mode + 1) % 3
        robot_started = False
        Robot_Movement(0, 0)

        if current_mode == 0:
            print("Switched to: Line Follower Mode")
            pixels.fill(RED)
            play_ms_string("T240 L16 o4 g e")
            if server:
                server.stop()
                server = None

        elif current_mode == 1:
            print("Switched to: Wi-Fi AP Mode")
            pixels.fill(BLUE)
            play_ms_string("T240 L16 o4 e g")
            server = setup_ap_mode()

        elif current_mode == 2:
            print("Switched to: Mode 2 (Custom)")
            pixels.fill(WHITE)
            play_ms_string("T240 L16 o5 c e g")
            if server:
                server.stop()
                server = None

        time.sleep(0.4)

    # 2. Handle Starting the Mode (GP20)
    #    In Mode 2: first press starts, second press stops (toggle)
    if not execute_button.value:
        if current_mode == 2:
            robot_started = not robot_started
            if robot_started:
                pixels.fill(WHITE)
                pixels.brightness = 0.3          # bright white = running
                play_ms_string("T180 L8 o5 c")
                print("Mode 2 started")
            else:
                pixels.fill(WHITE)
                pixels.brightness = 0.15         # dim white = paused
                Robot_Movement(0, 0)
                play_ms_string("T180 L8 o4 c")
                print("Mode 2 stopped")
            time.sleep(0.3)
        elif not robot_started:
            pixels.fill(GREEN if current_mode == 0 else MAGENTA)
            play_ms_string("T180 L8 o5 c")
            robot_started = True
            time.sleep(0.3)

    # 3. Mode 0 Logic: Line Follower
    if current_mode == 0 and robot_started:
        an = (SA.value * 3.3) / 65536
        print(an)
        if 1.59 < an < 1.75:    Robot_Movement(0.85, (0.85+factor))
        elif 1.76 < an < 1.9:  Robot_Movement(0.75, (0.35+factor))
        elif 1.35 < an < 1.55:  Robot_Movement(0.35, (0.75+factor))
        elif 2.1 < an < 2.4: Robot_Movement(0.75, (0.25+factor))
        elif 0.8 < an < 1.09:  Robot_Movement(0.25, (0.75+factor))
        elif 1.91 < an < 2.0: Robot_Movement(1, 0.0)
        elif 1.1 < an < 1.35:  Robot_Movement(0.0, 1)
        elif an < 0.3 or an > 3:
            Robot_Movement(0, 0)

    # 4. Mode 1 Logic: Wi-Fi AP Server
    elif current_mode == 1 and robot_started and server:
        server.poll()

    # 5. Mode 2 Logic: Custom — put your code below
    elif current_mode == 2 and robot_started:
        try:
            Distance = Read_Ultrasonic()
            print(f"Distance: {Distance} cm")
            
            if Distance < 10:  # Obstacle detected
                print("Turn Left")
                Robot_Movement(-0.8, 0.9)  # Turn Left
                time.sleep(0.5)
            else:  # No obstacle
                Robot_Movement(0.9, 1)  # Move Forward
        except RuntimeError:
            print("Ultrasonic sensor error. Retrying...")
            Robot_Movement(0, 0)  # Stop in case of sensor error
            time.sleep(0.1)
        pass
    time.sleep(0.01)
