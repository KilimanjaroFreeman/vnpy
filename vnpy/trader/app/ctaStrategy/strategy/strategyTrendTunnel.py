# encoding: UTF-8
from __future__ import division

"""
Created on 2018/09/20
@author: Freeman
多周期趋势通道策略：rb_30分钟
参数组合：（XXX, XXX, XXX）
每次交易1手
"""
import numpy as np
import talib as tb
from pymongo import MongoClient, ASCENDING
import datetime

from vnpy.trader.vtObject import VtBarData
from vnpy.trader.vtConstant import EMPTY_STRING
from vnpy.trader.app.ctaStrategy.ctaTemplate import (CtaTemplate, 
                                                     BarGenerator, 
                                                     ArrayManager)

########################################################################
class TrendTunnelStrategy(CtaTemplate):
    """多周期趋势通道策略_TA_30分钟"""
    
    className = 'TrendTunnelStrategy'
    author = u'freeman'

    # 交易参数
    process_period = 1             #策略执行周期
    time_15 = 15                   #策略15分钟周期
    time_30 = 30                   #策略30分钟周期
    time_60 = 60                   #策略60分钟周期
    time_daily = 'Daily'           #策略日线周期
    slip_num = 5                   #滑点为最小变动单位的跳数
    
    # 策略参数
    alpha = 'TA'                   #交易合约字母
    midNum = 20                    #通道中轨周期
    atrNum = 14                    #ATR周期
    openPeriod = 30                #开仓周期级别
    closePeriod = 30               #平仓周期级别
    tradeMode = 0                  #交易模式 0:多空双向；1:只做多；-1:只做空
    initDays = 30                  #初始化天数
    fixedSize = 2                  #交易数量
    
    # 策略变量
    open_tunnel_up = 0             #开仓通道上沿
    open_tunnel_down = 0           #开仓通道下沿
    close_tunnel_up = 0            #平仓通道上沿
    close_tunnel_down = 0          #平仓通道下沿
    up_line_15m = np.array([])     #15分钟通道上沿
    down_line_15m = np.array([])   #15分钟通道下沿
    up_line_30m = np.array([])     #30分钟通道下沿
    down_line_30m = np.array([])   #30分钟通道下沿
    up_line_60m = np.array([])     #60分钟通道下沿
    down_line_60m = np.array([])   #60分钟通道下沿
    up_line_daily = np.array([])   #日线通道上沿
    down_line_daily = np.array([]) #日线通道下沿
    
    open_long_15m = False          #15分钟做多信号
    close_long_15m = False         #15分钟平多信号
    open_short_15m = False         #15分钟做空信号
    close_short_15m = False        #15分钟平空信号
    
    open_long_30m = False          #30分钟做多信号
    close_long_30m = False         #30分钟平多信号
    open_short_30m = False         #30分钟做空信号
    close_short_30m = False        #30分钟平空信号
    
    open_long_60m = False          #60分钟做多信号
    close_long_60m = False         #60分钟平多信号
    open_short_60m = False         #60分钟做空信号
    close_short_60m = False        #60分钟平空信号
    
    open_long_daily = False        #Daily分钟做多信号
    close_long_daily = False       #Daily分钟平多信号
    open_short_daily = False       #Daily分钟做空信号
    close_short_daily = False      #Daily分钟平空信号
    
    #止盈止损相关变量
    trade_price = np.nan           #交易价格
    last_price = 0                 #当前最新价
    
    #仓位信息
    rate = 0.3/10000               #手续费
    capital = 10000                #总资产
    deposit = 0                    #保证金
    pos_long = 0                   #多头仓位
    pos_short = 0                  #空头仓位
    cash = capital                 #现金
    original_capital = capital     #原始资本
    account_datetime = 0           #账户信息更新时间
    
    #紧急平仓信号，若status=run正常运行，status=stop策略平仓并停止运行
    status = 'run'

    #更换主力合约信号，若replaceContract不是None，则更改主力和约
    replaceContract = None

    # 参数列表，保存了参数的名称
    paramList = ['name',
                'className',
                'author',
                'vtSymbol',
                'alpha',
                'fixedSize',
                'initDays',
                'status',
                'rate',
		'replaceContract',
                'midNum',
                'atrNum',
                'openPeriod',
                'closePeriod',
                'tradeMode']

    # 变量列表，保存了变量的名称
    varList = ['inited',
                'trading',
                'pos']

    # 同步列表，保存了需要保存到数据库的变量名称
    syncList = ['pos', 'pos_long', 'pos_short', 'capital', 'original_capital',
                'cash', 'deposit', 'trade_price', 'last_price', 'account_datetime',
                'open_tunnel_up', 'open_tunnel_down', 'close_tunnel_up',
                'close_tunnel_down']

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(self.__class__, self).__init__(ctaEngine, setting)
        
        # 创建不同周期K线合成器对象
        self.bg = BarGenerator(self.onBar, self.process_period, self.onXminBar)
        self.am = ArrayManager(size=30)
        
        d_num = max(self.atrNum, self.midNum)
        self.bg_daily = BarGenerator(self.onBar, self.time_daily, self.onDailyBar)
        self.am_daily = ArrayManager(size=d_num + 1)
        
        self.bg_15m = BarGenerator(self.onBar, self.time_15, self.on15minBar)
        self.am_15m = ArrayManager(size=d_num + 1)
        
        self.bg_30m = BarGenerator(self.onBar, self.time_30, self.on30minBar)
        self.am_30m = ArrayManager(size=d_num + 1)
        
        self.bg_60m = BarGenerator(self.onBar, self.time_60, self.on60minBar)
        self.am_60m = ArrayManager(size=d_num + 1)
        
    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)
        
        #读取合约参数
        self.writeCtaLog(u'%s读取合约参数' %self.name)
        self.loadContractDetail(self.alpha)
        self.slip = self.tickPrice * self.slip_num
        
        # 载入历史数据，并采用回放计算的方式初始化策略数值
        initData = self.loadBar(self.initDays)
        for bar in initData:
            self.onBar(bar)

        self.putEvent()

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' %self.name)
        self.putEvent()

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' %self.name)
        self.putEvent()

    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        # 只需要要在一个BarGenerator中合成1分钟K线
        self.bg.updateTick(tick)
        self.last_price = tick.lastPrice
        
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        # 基于X分钟判断趋势过滤，因此先更新
        self.bg.updateBar(bar)         #小周期
        self.bg_15m.updateBar(bar)     #15分钟周期
        self.bg_30m.updateBar(bar)     #30分钟周期
        self.bg_60m.updateBar(bar)     #60分钟周期
        self.bg_daily.updateBar(bar)   #日线分钟周期
        
        #实时更新账户信息
        if self.trading and self.am_daily.inited:
            self.caculateAccountNoTrade(bar)
            self.saveRealtimeStrategyInfor()
            
    #----------------------------------------------------------------------
    def on15minBar(self, bar):
        """处理15分钟数据"""
        #更新bar
        self.am_15m.updateBar(bar)
        
        #趋势通道
        m_atr = tb.ATR(self.am_15m.high, self.am_15m.low, self.am_15m.close, timeperiod=self.atrNum)
        m_ma = tb.MA(self.am_15m.close, timeperiod=self.midNum)
        self.up_line_15m = m_ma + (m_atr / 2) 
        self.down_line_15m = m_ma - (m_atr / 2) 
        #15分钟开平仓信号
        self.open_long_15m = bar.close > self.up_line_15m[-1]
        self.close_long_15m = bar.close < self.down_line_15m[-1]
        self.open_short_15m = bar.close < self.down_line_15m[-1]
        self.close_short_15m = bar.close > self.up_line_15m[-1]

    #----------------------------------------------------------------------
    def on30minBar(self, bar):
        """处理30分钟数据"""
        #更新bar
        self.am_30m.updateBar(bar)
        
        #趋势通道
        m_atr = tb.ATR(self.am_30m.high, self.am_30m.low, self.am_30m.close, timeperiod=self.atrNum)
        m_ma = tb.MA(self.am_30m.close, timeperiod=self.midNum)
        self.up_line_30m = m_ma + (m_atr / 2) 
        self.down_line_30m = m_ma - (m_atr / 2) 
        #30分钟开平仓信号
        self.open_long_30m = bar.close > self.up_line_30m[-1]
        self.close_long_30m = bar.close < self.down_line_30m[-1]
        self.open_short_30m = bar.close < self.down_line_30m[-1]
        self.close_short_30m = bar.close > self.up_line_30m[-1]

    #----------------------------------------------------------------------
    def on60minBar(self, bar):
        """处理60分钟数据"""
        #更新bar
        self.am_60m.updateBar(bar)
        
        #趋势通道
        m_atr = tb.ATR(self.am_60m.high, self.am_60m.low, self.am_60m.close, timeperiod=self.atrNum)
        m_ma = tb.MA(self.am_60m.close, timeperiod=self.midNum)
        self.up_line_60m = m_ma + (m_atr / 2) 
        self.down_line_60m = m_ma - (m_atr / 2) 
        #60分钟开平仓信号
        self.open_long_60m = bar.close > self.up_line_60m[-1]
        self.close_long_60m = bar.close < self.down_line_60m[-1]
        self.open_short_60m = bar.close < self.down_line_60m[-1]
        self.close_short_60m = bar.close > self.up_line_60m[-1]

    #----------------------------------------------------------------------
    def onDailyBar(self, bar):
        """处理日线数据"""
        #更新bar
        self.am_daily.updateBar(bar)
        #趋势通道
        m_atr = tb.ATR(self.am_daily.high, self.am_daily.low, self.am_daily.close, timeperiod=self.atrNum)
        m_ma = tb.MA(self.am_daily.close, timeperiod=self.midNum)
        self.up_line_daily = m_ma + (m_atr / 2) 
        self.down_line_daily = m_ma - (m_atr / 2)
        #Daily开平仓信号
        self.open_long_daily = bar.close > self.up_line_daily[-1]
        self.close_long_daily = bar.close < self.down_line_daily[-1]
        self.open_short_daily = bar.close < self.down_line_daily[-1]
        self.close_short_daily = bar.close > self.up_line_daily[-1]

    #----------------------------------------------------------------------
    def onXminBar(self, bar):
    
        # 全撤之前发出的委托
        self.cancelAll()

        # 保存K线数据
        am = self.am
        am.updateBar(bar)
        
        # 排除没有保存完的情况
        if not self.am_daily.inited:
            # 实盘时数据初始化不够
            if self.trading:
                print u'%s, %s策略, 初始化天数不足' %(bar.datetime.strftime('%Y-%m-%d %H:%M:%S'), self.name)
                print u'当前已经储存%s分钟K线数量:%s' %(self.time_daily, self.am_daily.count)
            return

        #------------------------------------------------------------------
        #紧急平仓并且停止策略运行
        if self.status == 'stop':
            self.closePositionAndStop(bar)
            return

        #更换主力合约
        if self.replaceContract:
            self.replaceDominantContract(bar)
            return

        #------------------------------------------------------------------   
        #依据平仓周期级别获取相应信号
        if self.closePeriod == 15:
            close_long = self.close_long_15m
            close_short = self.close_short_15m
            self.close_tunnel_up = self.up_line_15m[-1]
            self.close_tunnel_down = self.down_line_15m[-1]
        elif self.closePeriod == 30:
            close_long = self.close_long_30m
            close_short = self.close_short_30m
            self.close_tunnel_up = self.up_line_30m[-1]
            self.close_tunnel_down = self.down_line_30m[-1]
        elif self.closePeriod == 60:
            close_long = self.close_long_60m
            close_short = self.close_short_60m
            self.close_tunnel_up = self.up_line_60m[-1]
            self.close_tunnel_down = self.down_line_60m[-1]
        elif self.closePeriod == 'Daily':
            close_long = self.close_long_daily
            close_short = self.close_short_daily
            self.close_tunnel_up = self.up_line_daily[-1]
            self.close_tunnel_down = self.down_line_daily[-1]
        
        #依据开仓周期级别获取相应信号
        if self.openPeriod == 15:
            open_long = self.open_long_15m and not close_long
            open_short = self.open_short_15m and not close_short
            self.open_tunnel_up = self.up_line_15m[-1]
            self.open_tunnel_down = self.down_line_15m[-1]
        elif self.openPeriod == 30:
            open_long = self.open_long_30m and not close_long
            open_short = self.open_short_30m and not close_short
            self.open_tunnel_up = self.up_line_30m[-1]
            self.open_tunnel_down = self.down_line_30m[-1]
        elif self.openPeriod == 60:
            open_long = self.open_long_60m and not close_long
            open_short = self.open_short_60m and not close_short
            self.open_tunnel_up = self.up_line_60m[-1]
            self.open_tunnel_down = self.down_line_60m[-1]
        elif self.openPeriod == 'Daily':
            open_long = self.open_long_daily and not close_long
            open_short = self.open_short_daily and not close_short
            self.open_tunnel_up = self.up_line_daily[-1]
            self.open_tunnel_down = self.down_line_daily[-1]
        
        #依据交易模式确定是否多空双向或采用单边交易
        if self.tradeMode == 0:
            pass
        elif self.tradeMode == 1:
            open_short = False
        elif self.tradeMode == -1:
            open_long = False

        #-------------------------------------------------------------------------------------------        
        # 当前为空仓
        if self.pos == 0 and self.trading:
            if open_long:
                self.buy(bar.close + self.slip, self.fixedSize, False)
            elif open_short:
                self.short(bar.close - self.slip, self.fixedSize, False)
        
        # 当前持有多头头寸
        if self.pos > 0 and self.trading:
            if close_long:
                self.sell(bar.close - self.slip, abs(self.pos), False)
            
        # 当前持有空头头寸
        if self.pos < 0 and self.trading:
            if close_short:
                self.cover(bar.close + self.slip, abs(self.pos), False)
        
        # 打印检查
        # if self.trading:
            # print '----------------------------~*-*~-------------------------------'
            # print u'本地时间:%s  K线时间:%s'%(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            # bar.datetime.strftime('%Y-%m-%d %H:%M:%S'))
            # print u'*%s*策略 持有 %s 仓位为：%s'%(self.className, self.vtSymbol, self.pos)
            # print u'账户详情：现金 %.2f ,保证金 %.2f, 总资产 %.2f'%(self.cash,self.deposit,self.capital)

        # 同步变量到数据库
        # self.saveSyncData()
        # 发出状态更新事件
        self.putEvent()        

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        pass

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """成交信息变更"""
        #记录交易数据
        self.trade_price = trade.price
            
        #--------------------------------------------------------------------
        # 保存成交记录到数据库中
        self.insertTrade('TradeRecord',self.name,trade)
        #统计策略账户信息
        self.caculateAccountTrade(trade)
        # 发出状态更新事件
        self.putEvent()

    #----------------------------------------------------------------------
    def onStopOrder(self, so):
        """停止单推送"""
        pass
