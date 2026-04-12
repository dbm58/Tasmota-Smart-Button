import alarm
import board
import digitalio
import neopixel
import time
import wifi

import adafruit_connection_manager
from adafruit_debouncer import Debouncer
import adafruit_requests

# --- CONFIGURATION ---
CHECK_INTERVAL = 60 

class Color:
    YELLOW = (255, 255, 0)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLACK = (0, 0, 0)
    OFF = (0, 0, 0)

class Atom:
    class Display:
        BRIGHTNESS = 0.02 
        PIXEL_COUNT = 25
        def __init__(self):
            self.pixels = neopixel.NeoPixel(
                board.NEOPIXEL,
                Atom.Display.PIXEL_COUNT,
                brightness=Atom.Display.BRIGHTNESS,
                auto_write=False)
        @property
        def color(self):
            return tuple(self.pixels[0]) 
        @color.setter
        def color(self, value):
            if value == self.color:
                return
            self.pixels.fill(value)
            self.pixels.show()
    def __init__(self):
        self.display = self.Display()
        
class Tasmota:
    def __init__(self, ip):
        self.ip = ip
        self.pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
        self.ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
        self.requests = adafruit_requests.Session(self.pool, self.ssl_context)

        print(f'Status URL:  {self.status_url}')
        print(f'Toggle URL:  {self.toggle_url}')

    def toggle(self):
        try:
            print(f"Sending Toggle to {self.toggle_url}...")
            with self.requests.get(self.toggle_url, timeout=5) as r:
                json = r.json()
                print("Toggle sent, status:", r.status_code)
                print('Toggle data returned: ', json)
                return json
        except Exception as e:
            print("Toggle failed:", e)
        return None

    def power_status(self):
        try:
            print("Fetching status...")
            with self.requests.get(self.status_url, timeout=10) as response:
                data = response.json()
                print('data: ', data)
                return data
        except Exception as e:
            print("Fetch failed:", e)
        return None

    @property
    def status_url(self):
        return f"http://192.168.1.{self.ip}/cm?cmnd=Power"

    @property
    def toggle_url(self):
        return f"http://192.168.1.{self.ip}/cm?cmnd=Power+TOGGLE"

atom = Atom()
#tasmota = Tasmota(178)  #  upper grow light
#tasmota = Tasmota(234)  #  basement space heater
tasmota = Tasmota(120)  #  main grow light

def update_display(data):
    if data == None:
        atom.display.color = Color.RED
        return
    power = data.get("POWER", "OFF")
    if power == 'ON':
        atom.display.color = Color.GREEN
        return
    atom.display.color = Color.OFF

def wait_for_next_check(duration):
    """Polls the button frequently while appearing to sleep."""
    start_time = time.monotonic()
    button_was_down = False
    
    # We use digitalio here because PinAlarm is too sensitive to noise on this board
    with digitalio.DigitalInOut(board.BTN) as pin:
        pin.direction = digitalio.Direction.INPUT
        pin.pull = None # Atom has external pull-up
        button = Debouncer(pin, interval=0.05) # 50ms debounce helps filter noise

        while True:
            button.update()
            now = time.monotonic()

            if not button.value: 
                atom.display.color = Color.YELLOW
                button_was_down = True
                    
            if button.rose:
                print("Button released! Sending toggle...")
                data = tasmota.toggle()
                update_display(data)
                button_was_down = False # Reset the flag
                start_time = now        # Reset the 60s timer
                
            # EXIT CONDITIONS:
            # 1. We've exceeded duration AND the button isn't currently held
            # 2. AND we aren't mid-interaction (waiting for a release)
            if (now - start_time >= duration) and button.value and not button_was_down:
                break
                
            t_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 0.2)
            alarm.light_sleep_until_alarms(t_alarm)

while True:
    data = tasmota.power_status()
    update_display(data)
    wait_for_next_check(CHECK_INTERVAL)

