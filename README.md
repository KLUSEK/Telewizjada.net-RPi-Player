# Telewizjada.net Raspberry Pi Player

## What is it
It's a script which agregates livestreamer, omxplayer (available on Raspbian) and ncurse for python to give you possibility to play stream provided by telewizjada.net
It doesn't require any X's - can be run directly from the shell.

![alt tag](http://i.imgur.com/IB657Yr.png)

## Dependenties
You need to have installed omxplayer and livestreamer

If you are Raspbian's user just do `apt-get install omxplayer livestreamer`

## Controle over HDMI-CEC
libcec-daemon allows you in combination with the right hardware to control your device with your TV remote control. Utilising your existing HDMI cabling.
