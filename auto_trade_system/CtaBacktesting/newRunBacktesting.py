# encoding: UTF-8

"""
展示如何执行策略回测。
"""

from __future__ import division
import re
import Tkinter, tkFileDialog
import os
import importlib
import traceback
import datetime

from vnpy.trader.app.ctaStrategy.ctaBacktesting import BacktestingEngine, MINUTE_DB_NAME
from vnpy.trader.app.ctaStrategy.ctaBase import loadContractDetail


def loadStrategyModule(moduleName):
    """使用importlib动态载入模块"""
    try:
        module = importlib.import_module(moduleName)
        
        # 遍历模块下的对象，只有名称中包含'Strategy'的才是策略类
        for k in dir(module):
            if 'Strategy' in k:
                v = module.__getattribute__(k)
                strategy_moudle = v
                return k, strategy_moudle
    except:
        print ('-' * 20)
        print ('Failed to import strategy file %s:' %moduleName)
        traceback.print_exc()    

if __name__ == '__main__':
    #动态载入策略类
    root = Tkinter.Tk()
    root.withdraw()
    default_dir = r'vnpy\trader\app\ctaStrategy\strategy'
    file_path = tkFileDialog.askopenfilename(title=u'选择策略文件',
                                            initialdir=os.path.expanduser(default_dir),
                                            filetypes=[('strategy files','*.py')])
    file_path = file_path.replace(r'.py', '')
    pat = '.*?(vnpy/trader/app.*)'
    file_path = re.match(pat, file_path).group(1)
    file_path = file_path.replace('/', '.')
    
    k, strategy_moudle = loadStrategyModule(file_path)
    
    print '***%s***'%k
    
    input_str = [unicode('输入回测开始日期 : ','utf-8').encode('gbk'),
                unicode('输入回测结束日期 : ', 'utf-8').encode('gbk'),
                unicode('输入回测合约代码 : ','utf-8').encode('gbk')]
    input_data = []
    
    for i in range(len(input_str)):
        status = True
        while status:
            inp = raw_input(input_str[i])
            
            if i ==0 or i == 1 :
                try:
                    test_format = datetime.datetime.strptime(inp, '%Y%m%d')
                    condition = True
                except:
                    condition = False
            
            elif i == 2:
                condition = True
                
            if condition:
                input_data.append(inp)
                status = False
    
    start_date = input_data[0]
    end_date = input_data[1]
    symbol = input_data[2]
    # start_date = raw_input(unicode('输入回测开始日期 : ','utf-8').encode('gbk'))
    # end_date = raw_input(unicode('输入回测结束日期 : ', 'utf-8').encode('gbk'))
    # slippage = float(raw_input(unicode('输入滑点跳数 : ','utf-8').encode('gbk')))
    # rate = float(raw_input(unicode('输入手续费率 : ', 'utf-8').encode('gbk')))
    # size = float(raw_input(unicode('输入合约大小 : ' ,'utf-8').encode('gbk')))
    # price_tick = float(raw_input(unicode('输入合约最小价格变动 : ', 'utf-8').encode('gbk')))
    # symbol = raw_input(unicode('输入回测合约代码 : ','utf-8').encode('gbk'))
    con_d = loadContractDetail(symbol)
    size = con_d['trade_size']
    price_tick = con_d['price_tick']
    slippage = 1 * price_tick             #默认滑点为一个跳价
    rate = 0.3 / 10000                    #默认手续费

    #------------------------------------------------------------------------------------------------------
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 设置引擎的回测模式为K线
    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate(start_date)
    engine.setEndDate(end_date)
    
    # 设置产品相关参数
    engine.setSlippage(slippage)      # 滑点
    engine.setRate(rate)              # 手续费
    engine.setSize(size)              # 股指合约大小 
    engine.setPriceTick(price_tick)   # 股指最小价格变动

    # 设置使用的历史数据库
    engine.setDatabase(MINUTE_DB_NAME, symbol)
    
    # 在引擎中创建策略对象
    d = {}
    engine.initStrategy(strategy_moudle, d)
    
    # 开始跑回测
    engine.runBacktesting()
    
    # 显示回测结果
    engine.showBacktestingResult()
    engine.showDailyResult()