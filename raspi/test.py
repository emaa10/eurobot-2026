import RPi.GPIO as GPIO

pullcord = 22

GPIO.setmode(GPIO.BCM)
GPIO.setup(pullcord, GPIO.IN, pull_up_down=GPIO.PUD_UP)

if GPIO.input(pullcord) == GPIO.HIGH:
    print("high")
else:
    print("low")