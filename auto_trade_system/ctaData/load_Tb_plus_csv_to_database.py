# -*- encoding:utf-8 -*-

'''
导入tb极速版数据到MongoDB数据库中
'''

import re
import Tkinter, tkFileDialog
import os

from vnpy.trader.app.ctaStrategy.ctaBase import MINUTE_DB_NAME
from vnpy.trader.app.ctaStrategy.ctaHistoryData import loadTbPlusCsv

#获取文件目录
root = Tkinter.Tk()
root.withdraw()

default_dir = u'/home/freeman/Desktop/ctaData/data'
file_path = tkFileDialog.askopenfilename(title=u'选择CSV文件',initialdir=os.path.expanduser(default_dir))

if file_path:
    file_name = file_path
    pat = r'.*/(.*)_1.*.csv'
    symbol = (re.match(pat, file_name)).group(1)

    if __name__ == '__main__':
        loadTbPlusCsv(file_name, MINUTE_DB_NAME, symbol)
