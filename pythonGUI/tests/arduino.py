import pyfirmata
from pyfirmata import util, Arduino
import time

print('initializing board')
board = Arduino('COM4')
print('board initialized')

it = util.Iterator(board)
it.start()
l = [5,6,7,8, 13]
for f in l:
    board.digital[f].mode = pyfirmata.INPUT
    board.digital[f].enable_reporting()
o = [12]
for f in o:
    board.digital[f].mode = pyfirmata.OUTPUT


while True:
    sensor1 = [board.digital[f].read() for f in l]
    # sensor = sensor + [board.analog[f].read() for f in a]
    sensor = board.digital[13].read()
    if sensor:
        print(sensor1, 'door open')
        board.digital[12].write(0)
    else:
        print(sensor1, 'door closed')
        board.digital[12].write(1)
    # print(sensor)
    time.sleep(0.1)