# encoding: UTF-8


import numpy as np
import talib
from datetime import time, timedelta

from vnpy.trader.vtObject import VtBarData

########################################################################
#-----------------------------------------------------------------------
def get_trade_time(vtSymbol):
    """获取合约的交易时间函数"""
    """
    输入代码如: rb1810, 输出该品种的交易时间,格式为:time
    morning_start: 白盘开始时间, afternoon_end: 白盘结束时间
    night_start: 夜盘开始时间, night_end: 夜盘结束时间
    """
    # 获取品种的字母部分
    symbol = "".join(x for x in vtSymbol if x.isalpha())
    # 初始化交易时间字典(为最常见的商品期货时间)
    d = {}
    d["morning_start"] = time(9, 0, 0)
    d["morning_end"] = time(11, 30, 0)
    d["morning_rest"] = time(10, 15, 0)
    d["morning_restart"] = time(10, 30, 0)
    d["afternoon_start"] = time(13, 30, 0)
    d["afternoon_end"] = time(15, 0, 0)
    d["night_start"] = time(21, 0, 0)
    d["night_end"] = time(23, 30, 0)
    #----------------------------------------------
    # 股指期货的情况(9:29-15:00)
    if symbol in ["IF","IH","IC"]:
        d["morning_start"] = time(9,30,0)
        d["afternoon_start"] = time(13, 0, 0)
        d["night_start"] = None
        d["night_end"] = None
        d["morning_rest"] = None
        d["morning_restart"] = None
    #----------------------------------------------
    # 国债期货的情况(9:14-15:15)
    elif symbol in ["T","TF"]:
        d["morning_start"] = time(9,15,0)
        d["afternoon_start"] = time(13, 0, 0)
        d["afternoon_end"] = time(15,15,0)
        d["night_start"] = None
        d["night_end"] = None
        d["morning_rest"] = None
        d["morning_restart"] = None
    #----------------------------------------------
    # 商品期货1,没有夜盘的品种
    elif symbol in ["wr","c","pp","l","v","cs","jd","bb","fb",
                    "AP","SF","SM","WH","LR","RI","RS","PM","JR"]:
        d["night_start"] = None
        d["night_end"] = None
    #----------------------------------------------
    # 商品期货2,夜盘23点结束的品种
    elif symbol in ["rb","hc","ru","bu","fu"]:
        d["night_end"] = time(23,0,0)
    #----------------------------------------------
    # 商品期货3,夜盘1点结束的品种
    elif symbol in ["zn","ni","cu","al","pb","sn"]:
        d["night_end"] = time(01,0,0)
    #----------------------------------------------
    # 商品期货4,夜盘2:30结束的品种
    elif symbol in ["ag","au","sc"]:
        d["night_end"] = time(02,30,0)
    #----------------------------------------------
    # 剩下的默认为, 夜盘23:30结束
    else:
        pass
    return d

class BarGenerator(object):
    """
    K线合成器，支持：
    1. 基于Tick合成1分钟K线
    2. 基于1分钟K线合成X分钟K线（X可以是2、3、5、10、15、30	）
    """

    #----------------------------------------------------------------------
    def __init__(self, onBar, xmin=0, onXminBar=None):
        """Constructor"""
        self.bar = None             # 1分钟K线对象
        self.onBar = onBar          # 1分钟K线回调函数
        
        self.xminBar = None         # X分钟K线对象
        self.xmin = xmin            # X的值
        self.onXminBar = onXminBar  # X分钟K线的回调函数
        
        self.lastTick = None        # 上一TICK缓存对象
        self.lastBar = None         # 上一Bar缓存对象
        
        self.tradeTime = {}         #交易时间
        self.d1 = None
        self.d2 = None
        self.n1 = None
        self.n2 = None
    #----------------------------------------------------------------------
    def updateTick(self, tick):
        """TICK更新"""
        # 获取合约交易时间段
        if not self.tradeTime:
            self.tradeTime = get_trade_time(tick.symbol)
            self.d1 = self.tradeTime['morning_start']
            self.d2 = self.tradeTime['afternoon_end']
            self.n1 = self.tradeTime['night_start']
            self.n2 = self.tradeTime['night_end']
                
        #剔除非交易时间的tick数据
        t_time = tick.datetime.time()
        
        #是否有夜盘
        if self.n1 is None:
            is_trade_time = (t_time >= self.d1 and t_time <= self.d2)
        else:
            is_trade_time = (t_time >= self.d1 and t_time <= self.d2) or (t_time >= self.n1 and t_time <= self.n2)
            
        if is_trade_time:
            newMinute = False   # 默认不是新的一分钟
            
            # 尚未创建对象
            if not self.bar:
                self.bar = VtBarData()
                newMinute = True
            # 新的一分钟
            elif self.bar.datetime.minute != tick.datetime.minute:
                # 生成上一分钟K线的时间戳
                self.bar.datetime = self.bar.datetime.replace(second=0, microsecond=0)  # 将秒和微秒设为0
                self.bar.date = self.bar.datetime.strftime('%Y%m%d')
                self.bar.time = self.bar.datetime.strftime('%H:%M:%S.%f')
                
                # 推送已经结束的上一分钟K线
                self.onBar(self.bar)
                
                # 创建新的K线对象
                self.bar = VtBarData()
                newMinute = True
                
            # 初始化新一分钟的K线数据
            if newMinute:
                self.bar.vtSymbol = tick.vtSymbol
                self.bar.symbol = tick.symbol
                self.bar.exchange = tick.exchange

                self.bar.open = tick.lastPrice
                self.bar.high = tick.lastPrice
                self.bar.low = tick.lastPrice
            # 累加更新老一分钟的K线数据
            else:                                   
                self.bar.high = max(self.bar.high, tick.lastPrice)
                self.bar.low = min(self.bar.low, tick.lastPrice)

            # 通用更新部分
            self.bar.close = tick.lastPrice        
            self.bar.datetime = tick.datetime  
            self.bar.openInterest = tick.openInterest
       
            if self.lastTick:
                volumeChange = tick.volume - self.lastTick.volume   # 当前K线内的成交量
                self.bar.volume += max(volumeChange, 0)             # 避免夜盘开盘lastTick.volume为昨日收盘数据，导致成交量变化为负的情况
                
            # 缓存Tick
            self.lastTick = tick
        else:
            pass
    #----------------------------------------------------------------------
    def updateBar(self, bar):
        """1分钟K线更新"""
        
        #获取合约交易时间段
        if not self.tradeTime:
            self.tradeTime = get_trade_time(bar.symbol)
            self.d1 = self.tradeTime['morning_start']
            self.d2 = self.tradeTime['afternoon_end']
            self.n1 = self.tradeTime['night_start']
            self.n2 = self.tradeTime['night_end']
            
        #如果K线为日线模式
        if self.xminBar is not None and self.xmin == 'Daily':
            #默认日线结束时间在14:00到17:00之间
            if self.lastBar.datetime.hour >= 14 and self.lastBar.datetime.hour <= 17:
                cond_1 = self.lastBar.datetime.date() != bar.datetime.date()   #相邻两个一分钟Bar不在同一天
                cond_2 = (bar.datetime.hour - self.lastBar.datetime.hour) > 4                #相邻两个一分钟Bar时间间隔超过4小时
                is_end = cond_1 or cond_2
                if is_end:
                    self.xminBar.datetime = self.lastBar.datetime
                    self.pushXminBar()
        
        # 尚未创建对象
        if not self.xminBar:
            self.xminBar = VtBarData()
            
            self.xminBar.vtSymbol = bar.vtSymbol
            self.xminBar.symbol = bar.symbol
            self.xminBar.exchange = bar.exchange
        
            self.xminBar.open = bar.open
            self.xminBar.high = bar.high
            self.xminBar.low = bar.low            
            
            self.xminBar.datetime = bar.datetime    # 以第一根分钟K线的开始时间戳作为X分钟线的时间戳
        # 累加老K线
        else:
            self.xminBar.high = max(self.xminBar.high, bar.high)
            self.xminBar.low = min(self.xminBar.low, bar.low)
    
        # 通用部分
        self.xminBar.close = bar.close        
        self.xminBar.openInterest = bar.openInterest
        self.xminBar.volume += int(bar.volume)                
            
        # X分钟已经走完
        #日线情况
        if self.xmin != 'Daily':
            a1 = not (bar.datetime.minute + 1) % self.xmin   # 可以用X整除
            if (self.xmin == 60) and (self.n2 is not None):
                t_next = (bar.datetime + timedelta(minutes=1)).time()
                a2 = t_next == self.n2
            else:
                a2 = False
            is_end = a1 or a2
            
            if is_end:
                self.pushXminBar()
        
        self.lastBar = bar

    #----------------------------------------------------------------------
    def pushXminBar(self):
        '''推送X分钟Bar'''
        self.xminBar.datetime = self.xminBar.datetime.replace(second=0, microsecond=0)  # 将秒和微秒设为0
        self.xminBar.date = self.xminBar.datetime.strftime('%Y%m%d')
        self.xminBar.time = self.xminBar.datetime.strftime('%H:%M:%S.%f')
        
        # 推送
        self.onXminBar(self.xminBar)
        
        # 清空老K线缓存对象
        self.xminBar = None
        
    #-----------------------------------------------------------------------------------
    def generate(self):
        """手动强制立即完成K线合成"""
        self.onBar(self.bar)
        self.bar = None



########################################################################
class ArrayManager(object):
    """
    K线序列管理工具，负责：
    1. K线时间序列的维护
    2. 常用技术指标的计算
    """

    #----------------------------------------------------------------------
    def __init__(self, size=100):
        """Constructor"""
        self.count = 0                      # 缓存计数
        self.size = size                    # 缓存大小
        self.inited = False                 # True if count>=size
        
        self.openArray = np.zeros(size)     # OHLC
        self.highArray = np.zeros(size)
        self.lowArray = np.zeros(size)
        self.closeArray = np.zeros(size)
        self.volumeArray = np.zeros(size)
        
    #----------------------------------------------------------------------
    def updateBar(self, bar):
        """更新K线"""
        self.count += 1
        if not self.inited and self.count >= self.size:
            self.inited = True
        
        self.openArray[0:self.size-1] = self.openArray[1:self.size]
        self.highArray[0:self.size-1] = self.highArray[1:self.size]
        self.lowArray[0:self.size-1] = self.lowArray[1:self.size]
        self.closeArray[0:self.size-1] = self.closeArray[1:self.size]
        self.volumeArray[0:self.size-1] = self.volumeArray[1:self.size]
    
        self.openArray[-1] = bar.open
        self.highArray[-1] = bar.high
        self.lowArray[-1] = bar.low        
        self.closeArray[-1] = bar.close
        self.volumeArray[-1] = bar.volume
        
    #----------------------------------------------------------------------
    @property
    def open(self):
        """获取开盘价序列"""
        return self.openArray
        
    #----------------------------------------------------------------------
    @property
    def high(self):
        """获取最高价序列"""
        return self.highArray
    
    #----------------------------------------------------------------------
    @property
    def low(self):
        """获取最低价序列"""
        return self.lowArray
    
    #----------------------------------------------------------------------
    @property
    def close(self):
        """获取收盘价序列"""
        return self.closeArray
    
    #----------------------------------------------------------------------
    @property    
    def volume(self):
        """获取成交量序列"""
        return self.volumeArray
    
    #----------------------------------------------------------------------
    def sma(self, n, array=False):
        """简单均线"""
        result = talib.SMA(self.close, n)
        if array:
            return result
        return result[-1]
        
    #----------------------------------------------------------------------
    def std(self, n, array=False):
        """标准差"""
        result = talib.STDDEV(self.close, n)
        if array:
            return result
        return result[-1]
    
    #----------------------------------------------------------------------
    def cci(self, n, array=False):
        """CCI指标"""
        result = talib.CCI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]
        
    #----------------------------------------------------------------------
    def atr(self, n, array=False):
        """ATR指标"""
        result = talib.ATR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]
        
    #----------------------------------------------------------------------
    def rsi(self, n, array=False):
        """RSI指标"""
        result = talib.RSI(self.close, n)
        if array:
            return result
        return result[-1]
    
    #----------------------------------------------------------------------
    def macd(self, fastPeriod, slowPeriod, signalPeriod, array=False):
        """MACD指标"""
        macd, signal, hist = talib.MACD(self.close, fastPeriod,
                                        slowPeriod, signalPeriod)
        if array:
            return macd, signal, hist
        return macd[-1], signal[-1], hist[-1]
    
    #----------------------------------------------------------------------
    def adx(self, n, array=False):
        """ADX指标"""
        result = talib.ADX(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]
    
    #----------------------------------------------------------------------
    def boll(self, n, dev, array=False):
        """布林通道"""
        mid = self.sma(n, array)
        std = self.std(n, array)
        
        up = mid + std * dev
        down = mid - std * dev
        
        return up, down    
    
    #----------------------------------------------------------------------
    def keltner(self, n, dev, array=False):
        """肯特纳通道"""
        mid = self.sma(n, array)
        atr = self.atr(n, array)
        
        up = mid + atr * dev
        down = mid - atr * dev
        
        return up, down
    
    #----------------------------------------------------------------------
    def donchian(self, n, array=False):
        """唐奇安通道"""
        up = talib.MAX(self.high, n)
        down = talib.MIN(self.low, n)
        
        if array:
            return up, down
        return up[-1], down[-1]
    

