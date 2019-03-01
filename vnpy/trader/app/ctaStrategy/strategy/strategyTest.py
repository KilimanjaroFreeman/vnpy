# encoding: UTF-8

"""
Created on 2018/09/20
@author: Freeman
每次交易1手
"""
import numpy as np
import talib
from pymongo import MongoClient, ASCENDING
import datetime

from vnpy.trader.vtObject import VtBarData
from vnpy.trader.vtConstant import EMPTY_STRING
from vnpy.trader.app.ctaStrategy.ctaTemplate import (CtaTemplate, 
                                                     BarGenerator, 
                                                     ArrayManager)

########################################################################
class TestStrategy(CtaTemplate):
    """测试策略"""
    
    #策略信息
    className = 'testStrateg'
    author = u'freeman'

    #交易参数
    slip_num = 5                #滑点为最小变动单位的跳数

    # 策略参数
    alpha = 'IF'                #交易合约字母
    initDays = 20               #初始化天数
    timePeriod = 1              #策略信号周期
    fixedSize = 2               #交易数量
    long = True

    #止盈止损相关变量
    trade_price = 0             #交易价格
    last_price = 0              #当前最新价
    open_long = False           #开多信号
    open_short = False          #开空信号
    close_long = False          #平多信号
    close_short = False         #平空信号
    
    #仓位信息
    rate = 0.3/10000            #手续费
    capital = 50000             #总资产
    deposit = 0                 #保证金
    pos_long = 0                #多头仓位
    pos_short = 0               #空头仓位
    cash = capital              #现金
    original_capital = capital  #原始资本
    account_datetime = 0        #账户信息更新时间

    #紧急平仓信号，若status=run正常运行，status=stop策略平仓并停止运行
    status = 'run'

    #更换主力合约信号，若replaceContract不是None，则更改主力和约
    replaceContract = None
    
    # 参数列表，保存了参数的名称
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
                'timePeriod']

    # 变量列表，保存了变量的名称
    varList = ['inited',
                'trading',
                'pos']

    # 同步列表，保存了需要保存到数据库的变量名称
    syncList = ['pos', 'pos_long', 'pos_short', 'capital', 'original_capital',
                'cash', 'deposit', 'trade_price', 'last_price','account_datetime',
                'long']

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(self.__class__, self).__init__(ctaEngine, setting)
        
        # 创建K线合成器对象
        self.bg = BarGenerator(self.onBar, self.timePeriod, self.onXminBar)
        self.am = ArrayManager(size=100)
        
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
        # 基于15分钟判断趋势过滤，因此先更新
        self.bg.updateBar(bar)
        
        #实时更新账户信息
        if self.trading and self.am.inited:
            self.caculateAccountNoTrade(bar)
            self.saveRealtimeStrategyInfor()

    #----------------------------------------------------------------------
    def onXminBar(self, bar):
        """处理交易"""
        # 全撤之前发出的委托
        self.cancelAll()

        # 保存K线数据
        am = self.am
        am.updateBar(bar)
        
        # 排除没有保存完的情况
        if not am.inited:
            # 实盘时数据初始化不够
            if self.trading:
                print u'%s, %s策略, 初始化天数不足' %(bar.datetime.strftime('%Y-%m-%d %H:%M:%S'), self.name)
                print u'当前已经储存30分钟K线数量:%s' % am.count
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
        close_array = am.close
        high_array = am.high
        low_array = am.low
        
        if self.pos <= -3 or self.pos >= 3:
            self.stop_open = True
        elif self.pos == 0:
            self.stop_open = False
            
        #逐渐加仓到3手
        if self.pos > -3 and self.pos < 3 and self.trading and not self.stop_open :
            if self.long:
                self.buy(bar.close + self.slip, self.fixedSize, False)
            else:
                self.short(bar.close - self.slip, self.fixedSize, False)

        
        # 当前持有多头头寸
        if self.pos > 0 and self.trading and self.stop_open:
            self.sell(bar.close - self.slip, self.fixedSize, False)
            if self.pos == 1:
                self.long = False
            
        # 当前持有空头头寸
        if self.pos < 0 and self.trading and self.stop_open:
            self.cover(bar.close + self.slip, self.fixedSize, False)
            if self.pos == -1:
                self.long = True
            
        
      # 打印检查
        # if self.trading:
            # print '----------------------------~*-*~-------------------------------'
            # print u'本地时间:%s  K线时间:%s'%(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            # bar.datetime.strftime('%Y-%m-%d %H:%M:%S'))
            # print u'*%s*策略 持有 %s 仓位为：%s'%(self.className, self.vtSymbol, self.pos)
            # print u'账户详情：现金 %.2f ,保证金 %.2f, 总资产 %.2f'%(self.cash,self.deposit,self.capital)

        # 同步变量到数据库
        self.saveSyncData()

        # 发出状态更新事件
        self.putEvent()        

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        pass

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """成交信息处理"""
        #记录交易价格
        self.trade_price = trade.price

        #------------------------------------------------------------------
        # 保存成交记录到数据库中
        self.insertTrade('TradeRecord',self.name,trade)
        # 统计策略账户信息
        self.caculateAccountTrade(trade)
        # 发出状态更新事件
        self.putEvent()

    #----------------------------------------------------------------------
    def onStopOrder(self, so):
        """停止单推送"""
        pass
