# -*- encoding:utf-8 -*-

'''
导入tb极速版数据到MongoDB数据库中
'''

import re
import Tkinter, tkFileDialog
import os
import time

from vnpy.trader.app.ctaStrategy.ctaBase import MINUTE_DB_NAME
from vnpy.trader.app.ctaStrategy.ctaHistoryData import loadTbPlusCsv

file_dir = u'/home/freeman/桌面/ctaData/data'
#获取文件目录
L = []
for root, dirs, files in os.walk(file_dir):
    for file in files:
        if os.path.splitext(file)[1] == '.csv':
                L.append(os.path.join(root, file))

for f in L:
    file_name = f
    pat = r'.*/(.*)_1.*.csv'
    symbol = (re.match(pat, file_name)).group(1)
    if symbol[-3: ] == '888':
        print symbol
        loadTbPlusCsv(file_name, MINUTE_DB_NAME, symbol)
        time.sleep(5)
