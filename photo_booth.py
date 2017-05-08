#!/usr/bin/python

import RPIO as GPIO
import time
import threading
import os
import subprocess
import sys
import logging
import picamera
import tweepy
import traceback
import datetime

import photo_booth_config as cfg

############################################################################
# Twitter support
############################################################################

class Twitter(object):
  """Class to connect to and send DMs/update status on twitter"""

  def __init__(self):
    self.twitter_api = None
    self.logger = logging.getLogger(__name__)

  def connect(self):
    """Initialize Twitter API Object.

    Args:
      None
    """

    # User may not have configured twitter - don't initialize it until it's 
    # first used
    if self.twitter_api == None:
      self.logger.info("Initializing Twitter")
 
      if cfg.TWITTER_CONSUMER_KEY == '' or cfg.TWITTER_CONSUMER_SECRET == '':
        self.logger.error("Twitter customer key/secret not specified - unable to Tweet!")
      elif cfg.TWITTER_ACCESS_KEY == '' or cfg.TWITTER_ACCESS_SECRET == '':
        self.logger.error("Twitter access key/secret not specified - unable to Tweet!")
      else:
        auth = tweepy.OAuthHandler(cfg.TWITTER_CONSUMER_KEY, cfg.TWITTER_CONSUMER_SECRET)
        auth.set_access_token(cfg.TWITTER_ACCESS_KEY, cfg.TWITTER_ACCESS_SECRET)
        self.twitter_api = tweepy.API(auth)

  def update_status(self, msg, photo_path):
    # tweet a picture to my account

    self.connect()

    if self.twitter_api != None:
      # Twitter doesn't like the same message sent multiple times, so add a time stamp

      msg = time.strftime("%Y-%m-%d %H:%M:%S: ") + msg
      
      self.logger.info("Updating Twitter status to: %s", msg)
      try:
        self.twitter_api.update_with_media(photo_path, status=msg)
      except tweepy.error.TweepError as ex:
        self.logger.error("Unable to update Twitter status: %s", ex)

class Button(object):
  """ Class to manage a momentary button on the Pi GPIO """

  def onPressed(self, port, value):
    if self.__button_port == port and value == 1:
      self.logger.debug("Button %d pressed %d", port, value)
      self.__button_cb(port)

  def __init__(self, port, callback):
    self.__button_port = port
    self.__button_cb = callback
    self.logger = logging.getLogger(__name__)
    self.logger.debug("Initializing Button %d", port)
    GPIO.setup(port, GPIO.IN)
    GPIO.add_interrupt_callback(port, self.onPressed)
    self.logger.debug("Button %d initialized", port)

class LED(object):
  """ Class to manage a LED on the Pi GPIO """

  def Set(self, state):
    self.state = state
    GPIO.output(self.port, state)

  def On(self):
    self.Set(True)

  def Off(self):
    self.Set(False)

  def Toggle(self):
    self.Set(not self.state)

  def Blink(self, delay):
    self.Off()
    time.sleep(delay)
    self.On()
    time.sleep(delay)

  def __init__(self, port, state=True):
    self.port = port
    self.logger = logging.getLogger(__name__)
    self.logger.debug("Initializing LED %d", port)
    GPIO.setup(port, GPIO.OUT)
    self.Set(state)
    self.logger.debug("LED %d initialized", port)

class PhotoButton(Button, LED):

  def __init__(self, button_port, led_port, callback):
    Button.__init__(self, button_port, callback)
    LED.__init__(self, led_port)   

class ToggleButton(Button, LED):
 
  def TogglePressed(self, port):
    if self.__ignore != True:
      self.Toggle()
      self.__cb(port)

  def Ignore(self):
    self.__ignore = True

  def Reset(self):
    self.__ignore = False
    self.On()

  def __init__(self, button_port, led_port, callback):
    self.__ignore = False    
    self.__cb = callback
    Button.__init__(self, button_port, self.TogglePressed)
    LED.__init__(self, led_port, True)   

class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, target):
        super(StoppableThread, self).__init__(None, target)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()   

############################################################################
# Main functionality
############################################################################

class PhotoBooth(object):
  """ Class with main functionality for the HER photo booth """

  def __init__(self):
    self.logger = logging.getLogger(__name__)


  def setup_camera(self):
    self.camera = picamera.PiCamera()
    self.camera.resolution = (500, 375) # use a smaller resolution for speed
    self.camera.vflip = False
    self.camera.hflip = True
    self.camera.saturation = 50
    self.camera.brightness = 60    

  def take_a_picture(self):
    self.Pose.On()
    time.sleep(1.5)
    # slow blink delay for pose
    for i in range(5):
      self.Pose.Blink(0.4)
    # fast blink delay for pose
    for i in range(5):
      self.Pose.Blink(0.1)
    self.Pose.Off()

    self.logger.info("Taking picture %d" % (self.pictureId))

    self.camera.capture('/home/pi/photobooth_images/photobooth%d.jpg' % (self.pictureId))

  def take_all_pictures(self):
    self.pictureId = 1
    while self.pictureId < 5:
       self.take_a_picture()
       self.pictureId += 1

  def upload_picture(self):
    self.logger.info("Uploading photo")
    self.pictureId = 1    
    self.Upload.On()

    subprocess.call("montage /home/pi/photobooth_images/*.jpg -tile 2x2 -geometry +10+10 /home/pi/temp_montage2.jpg", shell=True)

    self.twitter.update_status("Hollow Earth Photo booth", "/home/pi/temp_montage2.jpg")

    subprocess.call("rm /home/pi/photobooth_images/*.jpg", shell=True)
    subprocess.call("rm /home/pi/temp_montage*", shell=True)
  
    self.Upload.Off()
    self.Photo.On()

  def blinkPhotoLed(self):
    while self.BlinkyThread.stopped() == False:
      self.Photo.Blink(.5)
    self.Photo.Off()

  def onPhotoPressed(self, port):
    self.logger.info("Photo button pressed")

    if self.BlinkyThread is not None and self.BlinkyThread.isAlive() == True:
      self.BlinkyThread.stop()
      
    self.Photo.Off()

    if self.Toggle.state == True:
      self.take_all_pictures()
    else:
      self.Toggle.Ignore()
      self.take_a_picture()
      self.pictureId += 1
      if self.pictureId < 5:
        self.BlinkyThread = StoppableThread(target=self.blinkPhotoLed)
        self.BlinkyThread.start()
   
    if self.pictureId == 5:
      self.upload_picture()
      self.BlinkyThread.stop()
      self.Toggle.Reset()

  def onTogglePressed(self, port):
    self.logger.info("Toggle button pressed")

  def main(self):
    """ Main functionality
    """

    try:
      # Set up logging
      log_fmt = '%(asctime)-15s %(levelname)-8s %(message)s'
      log_level = logging.INFO

      if sys.stdout.isatty():
        # Connected to a real terminal - log to stdout
        logging.basicConfig(format=log_fmt, level=log_level)
      else:
        # Background mode - log to a file
        logging.basicConfig(format=log_fmt, level=log_level, filename=cfg.LOG_FILENAME)

      # Banner
      self.logger.info("=========================================================")
      self.logger.info("HER Photo Booth starting")

      # Use Raspberry Pi board in Broadcom mode
      self.logger.info("Configuring global settings")
      GPIO.setmode(GPIO.BCM)

      self.pictureId = 1
      self.setup_camera()
      self.twitter = Twitter()

      self.BlinkyThread = StoppableThread(target=self.blinkPhotoLed)

      self.Photo = PhotoButton(cfg.PHOTO, cfg.PHOTO_LED, self.onPhotoPressed)
      self.Toggle = ToggleButton(cfg.TOGGLE, cfg.TOGGLE_LED, self.onTogglePressed)
      self.Pose = LED(cfg.POSE_LED, False)
      self.Upload = LED(cfg.UPLOAD_LED, False)
    
      GPIO.wait_for_interrupts()

    except KeyboardInterrupt:
      logging.critical("Terminating due to keyboard interrupt")
    except:
      logging.critical("Terminating due to unexpected error: %s", sys.exc_info()[0])
      logging.critical("%s", traceback.format_exc())

    GPIO.cleanup()

if __name__ == "__main__":
  PhotoBooth().main()

