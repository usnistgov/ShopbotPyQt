import pyfirmata
from pyfirmata import util, Arduino
import time

print('initializing board')
board = Arduino('COM4')
print('board initialized')

it = util.Iterator(board)
it.start()
for f in [5,6,7,8]:
    board.digital[f].mode = pyfirmata.INPUT
    board.digital[f].enable_reporting()

while True:
    sensor = [board.digital[f].read() for f in [5,6,7,8]]
    print(sensor)
    time.sleep(0.1)