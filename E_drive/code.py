import time
import board
import analogio
import digitalio
import pwmio
import pulseio
import neopixel
import wifi
import socketpool
from adafruit_motor import motor
from adafruit_httpserver import Server, Request, Response, GET
import adafruit_hcsr04

# --- GLOBAL CONFIGURATION ---
factor = 0.03

# --- MOTOR HARDWARE SETUP ---
PWM_M1A, PWM_M1B = board.GP11, board.GP10
PWM_M2A, PWM_M2B = board.GP8, board.GP9

pwm_1a = pwmio.PWMOut(PWM_M1A, frequency=5000)
pwm_1b = pwmio.PWMOut(PWM_M1B, frequency=5000)
motorL = motor.DCMotor(pwm_1a, pwm_1b)
pwm_2a = pwmio.PWMOut(PWM_M2A, frequency=5000)
pwm_2b = pwmio.PWMOut(PWM_M2B, frequency=5000)
motorR = motor.DCMotor(pwm_2a, pwm_2b)

# Ultrasonic Sensor Setup
sonar = adafruit_hcsr04.HCSR04(trigger_pin=board.GP7, echo_pin=board.GP28)

# --- SENSORS & BUTTONS ---
SA = analogio.AnalogIn(board.GP26)

# New Light Sensor on GP2 (LOW = bright, HIGH = dark)
light_sensor = digitalio.DigitalInOut(board.GP2)
light_sensor.direction = digitalio.Direction.INPUT

execute_button = digitalio.DigitalInOut(board.GP20)
execute_button.direction = digitalio.Direction.INPUT
execute_button.pull = digitalio.Pull.UP

mode_button = digitalio.DigitalInOut(board.GP21)
mode_button.direction = digitalio.Direction.INPUT
mode_button.pull = digitalio.Pull.UP

# --- TURN INDICATOR LEDS ---
led_left = digitalio.DigitalInOut(board.GP16)
led_left.direction = digitalio.Direction.OUTPUT
led_right = digitalio.DigitalInOut(board.GP17)
led_right.direction = digitalio.Direction.OUTPUT

TURN_THRESHOLD = 0.15 

def update_indicators(sL, sR):
    diff = sR - sL  # positive => right wheel faster => turning left
    if diff > TURN_THRESHOLD:
        led_left.value, led_right.value = True, False
    elif diff < -TURN_THRESHOLD:
        led_left.value, led_right.value = False, True
    else:
        led_left.value, led_right.value = False, False

# --- RC RECEIVER PWM INPUT (Throttle / Roll / Pitch / Yaw) ---
# Standard 50Hz RC PWM: ~1000-2000us pulse, idles LOW between pulses.
THROTTLE_PIN, ROLL_PIN, PITCH_PIN, YAW_PIN = board.GP12, board.GP13, board.GP14, board.GP15

throttle_in = pulseio.PulseIn(THROTTLE_PIN, maxlen=4, idle_state=False)
roll_in = pulseio.PulseIn(ROLL_PIN, maxlen=4, idle_state=False)
pitch_in = pulseio.PulseIn(PITCH_PIN, maxlen=4, idle_state=False)
yaw_in = pulseio.PulseIn(YAW_PIN, maxlen=4, idle_state=False)

for _pulse_buf in (throttle_in, roll_in, pitch_in, yaw_in):
    _pulse_buf.pause()
    _pulse_buf.clear()
    _pulse_buf.resume()

RC_PULSE_MIN, RC_PULSE_MAX = 1000, 2000  # sanity window in microseconds

def read_pwm_us(pulse_buf, last_value):
    """Scan a PulseIn buffer for the most recent valid RC pulse width (us).
    Falls back to last_value if nothing valid is captured (signal lost/lag)."""
    if len(pulse_buf) == 0:
        return last_value
    pulse_buf.pause()
    value = last_value
    for i in range(len(pulse_buf)):
        candidate = pulse_buf[i]
        if RC_PULSE_MIN < candidate < RC_PULSE_MAX:
            value = candidate
    pulse_buf.clear()
    pulse_buf.resume()
    return value

def pwm_to_normalized(pulse_us, deadband=25):
    """Map a ~1000-2000us RC pulse (centered 1500us) to -1.0..1.0."""
    pulse_us = max(1000, min(2000, pulse_us))
    if abs(pulse_us - 1500) < deadband:
        return 0.0
    return max(-1.0, min(1.0, (pulse_us - 1500) / 500.0))

throttle_us, roll_us, pitch_us, yaw_us = 1500, 1500, 1500, 1500

# --- PASSIVE BUZZER SETUP ---
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
    try:
        return sonar.distance
    except RuntimeError:
        return -1.0  # Return fallback value if reading fails

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
CYAN, ORANGE = (0, 255, 255), (255, 140, 0)

def Robot_Movement(sL, sR):
    sL = max(-1.0, min(1.0, sL))
    sR = max(-1.0, min(1.0, sR))
    motorL.throttle = sL
    motorR.throttle = sR
    update_indicators(sL, sR)

# --- WEB UI PAGE ---
html_page = """<!DOCTYPE html><html><head>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<style>
    body { font-family: sans-serif; text-align: center; background: #222; color: white; }
    .grid { display: grid; grid-template-columns: repeat(3, 100px); gap: 10px; justify-content: center; margin-top: 30px; }
    button { width: 100px; height: 100px; font-size: 30px; background: #444; color: #fff; border: 2px solid #00adb5; border-radius: 15px; }
    button:active { background: #00adb5; }
    .stop { border-color: #ff2e63; color: #ff2e63; }
    .stop:active { background: #ff2e63; color: white; }
    .card-container { display: flex; justify-content: center; gap: 15px; margin-top: 20px; }
    .distance-card { background: #333; padding: 15px 25px; border-radius: 10px; font-size: 20px; border: 1px solid #555; min-width: 120px; }
    .distance-val { color: #00adb5; font-weight: bold; }
</style>
<script>
    function updateSensors() {
        // Poll distance data
        fetch('/distance')
            .then(response => response.text())
            .then(data => { document.getElementById('dist').innerText = data; })
            .catch(err => console.log(err));

        // Poll GP2 light data
        fetch('/light')
            .then(response => response.text())
            .then(data => { document.getElementById('light-status').innerText = data; })
            .catch(err => console.log(err));
    }
    setInterval(updateSensors, 500); // Polls sensors every 500ms
</script>
</head><body>
    <h1>Pico Robot</h1>
    <div class="card-container">
        <div class="distance-card">Distance: <span id="dist" class="distance-val">--</span> cm</div>
        <div class="distance-card">Environment: <span id="light-status" class="distance-val">--</span></div>
    </div>
    <div class="grid">
        <td></td><button onclick="fetch('/f')">forward</button><td></td>
        <button onclick="fetch('/l')">left</button>
        <button class="stop" onclick="fetch('/s')">stop</button>
        <button onclick="fetch('/r')">right</button>
        <td></td><button onclick="fetch('/b')">back</button><td></td>
    </div>
</body></html>"""

current_mode = 0  
robot_started = False
server = None

def setup_ap_mode():
    #print("Starting Wi-Fi Access Point...")
    try:
        wifi.radio.start_ap(ssid="PicoW-Robot-Net", password="")
        #print("AP Started! Network: 'PicoW-Robot-Net'")
        pool = socketpool.SocketPool(wifi.radio)
        
        server_instance = Server(pool, "/ ")
        
        @server_instance.route("/")
        def base(request: Request):
            return Response(request, html_page, content_type="text/html")

        @server_instance.route("/distance")
        def get_distance(request: Request):
            dist = Read_Ultrasonic()
            if dist < 0:
                return Response(request, "Error")
            return Response(request, f"{dist:.1f}")

        # --- NEW ROUTE FOR LIVE LIGHT DATA ---
        @server_instance.route("/light")
        def get_light(request: Request):
            # If light_sensor.value is False (LOW) -> bright. If True (HIGH) -> dark.
            status = "Bright" if not light_sensor.value else "Dark"
            return Response(request, status)

        @server_instance.route("/f")
        def forward(request: Request):
            Robot_Movement(0.75 - factor/2, 0.75 + factor/2)
            return Response(request, "OK")

        @server_instance.route("/b")
        def backward(request: Request):
            Robot_Movement(-0.75 + factor/2, -0.75 - factor/2)
            return Response(request, "OK")

        @server_instance.route("/l")
        def left(request: Request):
            Robot_Movement(-0.5 - factor/2, 0.5 + factor/2)
            return Response(request, "OK")

        @server_instance.route("/r")
        def right(request: Request):
            Robot_Movement(0.5 + factor/2, -0.5 - factor/2)
            return Response(request, "OK")

        @server_instance.route("/s")
        def stop(request: Request):
            Robot_Movement(0, 0)
            return Response(request, "OK")

        server_instance.start(port=80)
        return server_instance
    except Exception as e:
        #print("Failed to start AP Mode:", e)
        return None

# --- BOOT UP ---
#print("Playing requested MS PLAY string...")
my_melody = "MFT240L8 O4aO5dc O4aO5dc O4aO5dc L16dcdcdcdc"
play_ms_string(my_melody)

#print("System Ready. Mode 0 (Line Follower). Press GP21 to cycle modes.")
pixels.fill(RED)

while True:
    # 1. Mode Toggling (GP21) -- now cycles through 5 modes (0-4)
    if not mode_button.value:
        current_mode = (current_mode + 1) % 5
        robot_started = False
        Robot_Movement(0, 0)

        if current_mode == 0:
            #print("Switched to: Line Follower Mode")
            pixels.fill(RED)
            play_ms_string("T240 L16 o4 g e")
            if server:
                server.stop()
                server = None

        elif current_mode == 1:
            #print("Switched to: Wi-Fi AP Mode")
            pixels.fill(BLUE)
            play_ms_string("T240 L16 o4 e g")
            server = setup_ap_mode()

        elif current_mode == 2:
            #print("Switched to: Mode 2 (Obstacle Avoidance)")
            pixels.fill(WHITE)
            play_ms_string("T240 L16 o5 c e g")
            if server:
                server.stop()
                server = None

        elif current_mode == 3:
            #print("Switched to: Mode 3 (RC Manual Drive)")
            pixels.fill(CYAN)
            play_ms_string("T240 L16 o4 c e g o5 c")
            if server:
                server.stop()
                server = None

        elif current_mode == 4:
            #print("Switched to: Mode 4 (RC Full Control)")
            pixels.fill(ORANGE)
            play_ms_string("T240 L16 o5 c o4 g e c")
            if server:
                server.stop()
                server = None

        time.sleep(0.4)

    # 2. Execution Toggle (GP20)
    if not execute_button.value:
        if current_mode in (2, 3, 4):
            # Arm/disarm toggle -- these modes drive continuously, so treat
            # this like a safety switch you can exit out of at any time.
            mode_color = {2: WHITE, 3: CYAN, 4: ORANGE}[current_mode]
            robot_started = not robot_started
            if robot_started:
                pixels.fill(mode_color)
                pixels.brightness = 0.3
                play_ms_string("T180 L8 o5 c")
                #print(f"Mode {current_mode} started")
            else:
                pixels.fill(mode_color)
                pixels.brightness = 0.15
                Robot_Movement(0, 0)
                play_ms_string("T180 L8 o4 c")
                #print(f"Mode {current_mode} stopped")
            time.sleep(0.3)
        elif not robot_started:
            pixels.fill(GREEN if current_mode == 0 else MAGENTA)
            play_ms_string("T180 L8 o5 c")
            robot_started = True
            time.sleep(0.3)

    # 2b. RC channel decode -- refresh every loop regardless of mode so
    # values are current the instant modes 3/4 need them.
    throttle_us = read_pwm_us(throttle_in, throttle_us)
    roll_us = read_pwm_us(roll_in, roll_us)
    pitch_us = read_pwm_us(pitch_in, pitch_us)
    yaw_us = read_pwm_us(yaw_in, yaw_us)

    # 3. Mode 0: Line Follower
    if current_mode == 0 and robot_started:
        an = (SA.value * 3.3) / 65536
        #print(an)
        if 1.59 < an < 1.75:   Robot_Movement(0.70 - factor/2, 0.70 + factor/2)
        elif 1.76 < an < 1.9:  Robot_Movement(0.72 - factor/2, 0.35 + factor/2)
        elif 1.35 < an < 1.55: Robot_Movement(0.35 - factor/2, 0.72 + factor/2)
        elif 2.1 < an < 2.4:   Robot_Movement(0.72 - factor/2, 0.20 + factor/2) 
        elif 0.8 < an < 1.09:  Robot_Movement(0.20 - factor/2, 0.72 + factor/2) 
        elif 1.91 < an < 2.0:  Robot_Movement(0.80 - factor/2, 0.10 + factor/2)
        elif 1.1 < an < 1.35:  Robot_Movement(0.10 - factor/2, 0.80 + factor/2)
        elif an < 0.3 or an > 3:
            Robot_Movement(0, 0)

    # 4. Mode 1: Wi-Fi AP Server
    elif current_mode == 1 and robot_started and server:
        server.poll()

    # 5. Mode 2: Obstacle Avoidance
    elif current_mode == 2 and robot_started:
        Distance = Read_Ultrasonic()
        # Read and #print the light status to terminal during operation too
        Light_Condition = "Bright" if not light_sensor.value else "Dark"
        #print(f"Distance: {Distance} cm | Light: {Light_Condition}")
        
        if Distance < 0:
            #print("Ultrasonic sensor error. Retrying...")
            Robot_Movement(0, 0)  
            time.sleep(0.1)
        elif Distance < 20:  
            #print("Obstacle! Turning Left...")
            Robot_Movement(-0.6 - factor/2, 0.6 + factor/2)  
            time.sleep(0.4)
        else:  
            Robot_Movement(0.8 - factor/2, 0.8 + factor/2)

    # 6. Mode 3: RC Manual Drive -- throttle drives the left motor directly,
    # pitch drives the right motor directly (independent, no mixing).
    elif current_mode == 3 and robot_started:
        left_speed = pwm_to_normalized(throttle_us)
        right_speed = pwm_to_normalized(pitch_us)
        ##print(f"T:{throttle_us} P:{pitch_us} -> L:{left_speed:.2f} R:{right_speed:.2f}")
        Robot_Movement(left_speed - factor/2, right_speed + factor/2)

    elif current_mode == 4 and robot_started:
        Distance = Read_Ultrasonic()
        left_speed = pwm_to_normalized(throttle_us)
        right_speed = pwm_to_normalized(pitch_us)
        ##print(f"T:{throttle_us} P:{pitch_us} -> L:{left_speed:.2f} R:{right_speed:.2f}")
        if(Distance<20 and right_speed>0.1 and left_speed>0.1):
            Robot_Movement(0,0)
        else:
            Robot_Movement(left_speed - factor/2, right_speed + factor/2)

    time.sleep(0.01)