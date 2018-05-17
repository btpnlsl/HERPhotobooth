# HERPhotobooth

This is Python code for a Raspberry-Pi based photobooth which will take pictures and upload them to Twitter.

My photobooth is primarily used at [Hollow Earth Radio](https://www.hollowearthradio.org) (HER) events.  You can see photos it 
has taken on Twitter at [@HERPhotoBooth](https://twitter.com/HERPhotoBooth).

HERPhotobooth was originally based on a project from [Instructables](http://www.instructables.com/id/Raspberry-Pi-photo-booth-controller/)
which uses the Pi to take pictures with a DSLR and to print the photos. The code for that project can be found on 
[GitHub](https://github.com/safay/RPi_photobooth).

HERPhotobooth is different in that it uses the Pi camera to take photos and uploads to Twitter. The code also has added a toggle
button to make a single shot vs all-at-once mode for taking pictures.  I've also split the code out into classes and added a 
configuration file to help improve the readability.
