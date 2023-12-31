# PiLocker.py
import PN532_UART as NFC
from PiicoDev_QMC6310_new import PiicoDev_QMC6310
from PiicoDev_SSD1306 import *
from picamera import PiCamera
import RPi.GPIO as GPIO
from threading import Thread
import time
from time import sleep
from hardware_connection.hardware import getLastUserCode
from email_module.mail import getrecipientinfo, sendPickupNotice, send_email_with_mailgun
from queue import Queue
import os

magSensor = PiicoDev_QMC6310(range=3000)
threshold = 1000 # microTesla or 'uT'.
pn532 = NFC.PN532("/dev/ttyUSB0")
display = create_PiicoDev_SSD1306()
camera = PiCamera()
camera.resolution = (267, 200)

GPIO.setmode(GPIO.BCM)
ROW_PINS = [17, 18, 27, 22]
COL_PINS = [23, 24, 25]
relay_pin = 16
for pin in ROW_PINS:
    GPIO.setup(pin, GPIO.OUT)
# Setup columns as inputs with pull-up resistors
for pin in COL_PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def inithw():
    GPIO.setmode(GPIO.BCM)
    ROW_PINS = [17, 18, 27, 22]
    COL_PINS = [23, 24, 25]
    relay_pin = 16
    for pin in ROW_PINS:
        GPIO.setup(pin, GPIO.OUT)
    # Setup columns as inputs with pull-up resistors
    for pin in COL_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# Define keypad layout
KEYS = [
    ['0', '0', '0'],
    ['0', '0', '0'],
    ['0', '0', '0'],
    ['0', '0', '0']
]

def get_key():
    for i, pin in enumerate(ROW_PINS):
        GPIO.output(pin, GPIO.LOW)
        for j, col_pin in enumerate(COL_PINS):
            if GPIO.input(col_pin) == GPIO.LOW:
                time.sleep(0.2)  # Debounce
                return KEYS[i][j]

def keyinputs(num_digits):
    """get the num of digits from the keypad, if the user press the * key, reset the input"""
    GPIO.setmode(GPIO.BCM)
    output = ""
    #if lenth of the output is less than num_digits, keep getting the input
    while len(output) < num_digits:
        key = get_key()
        if key == "*":
            output = ""
        elif key is not None:
            #combine output and key together
            output = output + str(key)
    return output        


# This class is responsible for controlling the door.
# The isLockerClosed method checks whether the locker is closed. It makes a determination by detecting magnetic field strength.
# The openLocker method uses a relay to open the locker door.
# There are two additional methods, set_box_is_empty and set_box_is_not_empty, used to set the status of the locker.
class DoorControl:
    #variables
    def __init__(self):
        self.door_status = False#door is open or not True for open, False for close
        self.box_is_empty = True#box is open or not
    # magnet detection
    def isLockerClosed(self):
        """
        check the door is closed or not
        :param threshold:
        :param magSensor:
        if the magnet is detected, return True
        else, return False
        :return:
        """
        while True:
            strength = magSensor.readMagnitude()
            strength_str = str(strength) + ' uT'
            print(strength_str)
            print("Waiting for the door to close")
            if strength > threshold:
                print('Strong Magnet! The locker is closed.')
                self.door_status = False
                return True
            sleep(1)
    
    
    # relay
    def openLocker(self):
        try:
            GPIO.setup(relay_pin, GPIO.OUT)
            self.door_status = True
            return True

        except Exception:
            GPIO.cleanup()
            return False

        finally:
            sleep(10)
            GPIO.cleanup()
            inithw()

    # def runSensor(self):
    #     """run isLockerClosed function in a thread, 5 seconds per loop"""
    #     while True:
    #         self.isLockerClosed()
    #         print(f"Current magnetic strength: {self.door_status} uT")
    #         time.sleep(5)

    def set_box_is_empty(self):
        self.box_is_empty = True

    def set_box_is_not_empty(self):
        self.box_is_empty = False

    def set_door_closed(self):
        self.door_status = False


# This class is responsible for the overall operation of the PiLocker system.
# The start method describes the workflow of the locker, such as when a delivery person drops off a package and when a user picks up a package.
# The waitForUnlock method waits for a user to input a code or use an NFC tag to unlock.
# The getUID method is used to read the UID of the NFC tag.
# The sendToDisplay method displays information on the OLED screen.
# The takePhoto method captures photos using a camera.
# The pinpadCode and pinpadMobile methods get user input from a keypad, but in practice, they need to be integrated with the actual keypad hardware.
class PiLockerSystem:
    def __init__(self):
        self.hardware = DoorControl()
        # self.thread = threading.Thread(target=self.hardware.runSensor)
        # self.thread.start()

    def start(self):
        inithw()
        print("System up. Wating for packages.")
        while True:
            # no things in the box
            if self.hardware.box_is_empty == True:
                if self.hardware.door_status == False:
                    # deliveryman put the parcel into the box
                    self.sendToDisplay("please input phone number", 1)
                    mobileInput = self.pinpadMobile()
                    #check the mobile number is in the database or not
                    checkReceiver = eval(getrecipientinfo(mobileInput))
                    if checkReceiver['status'] == 'success':
                        self.hardware.openLocker()
                        self.sendToDisplay("please close the door when finised", 1)
                        self.hardware.box_is_empty = False
                        # use isLockerClosed function to check the door is closed or not
                        while True:
                            if self.hardware.isLockerClosed() == True:
                                self.hardware.set_box_is_not_empty()
                                break
                            # else:
                            #     self.hardware.set_box_is_empty()
                            #     break
                        # TODO db + email
                        sendPickupNotice(mobileInput)
                    elif checkReceiver['status'] == 'failure':
                        self.sendToDisplay(checkReceiver['message'], 1)
                    self.sendToDisplay("Door locked", 2)
                    sleep(2)
                elif self.hardware.door_status == True:
                    #TODO door was not closed properly
                    self.sendToDisplay("please close the door", 1)
                    sleep(2)
            # things in the box(user pick up the parcel)
            elif self.hardware.box_is_empty == False:
                if self.hardware.door_status == False:
                    #user pick up the parcel
                    self.sendToDisplay("Input the code", 3)
                    self.waitForUnlock()
                    


                elif self.hardware.door_status == True:
                    #user did not pick up the parcel
                    self.sendToDisplay("please pick up the things in box", 1)
                    sleep(5)

    def waitForUnlock(self):
        sec = Thread(target=self.sec)
        sec.start()
        res = getLastUserCode()
        q = Queue()
        t1 = Thread(target=self.accessByPin, args=(q,res['message']['code'],))
        t1.start()
        print("Wating for unlocking")
        while q.empty():
            nfcid=getUID()
            # print("detected nfc id:",nfcid)
            # print("-------------------------")
            if nfcid == res['message']['nfc_id']:
                print("Door unlocked by Card")
                self.hardware.openLocker()
                self.sendToDisplay("Thank you", 2)
                GPIO.cleanup()
                os._exit(0)
            elif nfcid != res['message']['nfc_id']:
                self.sendToDisplay("Wrong NFC", 1)
            elif nfcid=="00000000":
                continue
            sleep(2)
        if q.get() == "done":
            print("Door unlocked by pin")
            self.hardware.openLocker()
            self.sendToDisplay("Thank you", 2)
            GPIO.cleanup()
            os._exit(0)


    def accessByPin(self, q, code):
        while True:
            if code == self.pinpadCode():
                q.put("done")
                break
            elif code != self.pinpadCode():
                self.sendToDisplay("Wrong Code", 4)
            sleep(1)


    def sec(self):
        print("666666666666666666")
        count=0
        uc_PIN_TRIGGER = 5
        uc_PIN_ECHO = 6
        GPIO.setup(uc_PIN_TRIGGER, GPIO.OUT)
        GPIO.setup(uc_PIN_ECHO, GPIO.IN)
        while True:
            GPIO.output(uc_PIN_TRIGGER, GPIO.LOW)
            GPIO.output(uc_PIN_TRIGGER, GPIO.HIGH)
            sleep(0.00001)
            GPIO.output(uc_PIN_TRIGGER, GPIO.LOW)
            while GPIO.input(uc_PIN_ECHO)==0:
                pulse_start_time = time.time()
            while GPIO.input(uc_PIN_ECHO)==1:
                pulse_end_time = time.time()
            pulse_duration = pulse_end_time - pulse_start_time
            distance = round(pulse_duration * 17150, 2)
            print("distance:",distance)
            if distance <= 20:
                count=count+1
            if count>= 5:
                print("Sending Alert")
                self.take_photo("/home/iot-lab-2023/cits5506/1.jpg")
                send_email_with_mailgun("rfc@live.com","/home/iot-lab-2023/cits5506/1.jpg")
                break
                count=0
            sleep(1)

    def take_photo(file_path):
        camera.capture(file_path)
    #    camera.stop_preview()
    #    camera.start_preview()

    # oled display
    def sendToDisplay(self, text, line):
        """
        display the text on the oled screen(128x64 pixels),(4 lines, 16 characters per line)
        :param text: the text to be displayed
        :param line: 1-4
        will display the text on the line of the oled screen
        the number of line is from 1 to 8
        """
        # clear the screen
        # display.clear()
        display.fill(0)
        display.text(text, 0, 15*(line-1), 1)
        display.show()


    def pinpadCode(self,q=None):
        """
        TODO: get the input from the pinpad
        :return: 4-digit pin
        """

        code = keyinputs(4)
        # print("print from pinpadCode" , code)
        if q is not None:
            q.put(("code",code))
        return code

    def pinpadMobile(self):
        """
        TODO: get the input from the pinpad
        :return:
        """
        mobile = keyinputs(10)
        # print("print from pinpadMobile" , mobile)
        return mobile


def getUID():
    """
    read the uid of the nfc card
    :return:
    """
    try:
        uid = pn532.read_passive_target(timeout=1000)
        uid = "".join("%02X" % i for i in uid)[:-1]
        return uid
    except Exception as e:
        # print(e)
        return "00000000"
    # TODO: why here has a KeyboardInterrupt?
    except KeyboardInterrupt:
        pass