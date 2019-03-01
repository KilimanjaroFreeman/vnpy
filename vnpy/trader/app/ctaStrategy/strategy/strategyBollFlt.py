# encoding: UTF-8

"""
Created on 2018/09/20
@author: Freeman
布林带过滤策略：
参数组合：（, , ）
每次交易n手
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
class BollFltStrategy(CtaTemplate):
    """布林带过滤策略"""

    #策略信息
    className = 'BollFltStrategy'
    author = u'freeman'

    # 交易参数
    slip_num = 5             #滑点为最小变动单位的跳数
    process_period = 1       #策略执行周期
    
    # 策略参数
    alpha = 'fu'             #交易合约字母
    midNum = 60              #布林带中轨
    diffNum = 10             #长期过滤均线与中轨周期差值
    stdNum = 1.0             #布林带上下轨, std倍数
    timePeriod = 15          #策略周期
    fixedSize = 3            #交易数量
    initDays = 90            #初始化天数

    # 策略变量
    mid_line = np.nan        #布林带中轨
    up_line = np.nan         #布林带上轨
    down_line = np.nan       #布林带下轨
    std = np.nan             #最近mid_num天的标准差
    ma_flt  = np.nan         #长期过滤均线
    open_long = False        #开多信号
    open_short = False       #开空信号
    
    #止盈止损相关变量
    trade_price = np.nan     #交易价格
    stop_price = np.nan      #固定止损价
    stop_line = np.nan       #最终止损线
    stop_order_status = True #是否可以发出本地停止单
    last_price = 0           #当前最新价
    
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
    paramList = ['name',
                'className',
                'author',
                'vtSymbol',
                'alpha',
                'timePeriod',
                'fixedSize',
                'initDays',
                'status',
                'rate',
                'replaceContract',
                'midNum',
                'stdNum',
                'diffNum']
                
    # 变量列表，保存了变量的名称
    varList = ['inited',
                'trading',
                'pos']

    # 同步列表，保存了需要保存到数据库的变量名称
    syncList = ['pos', 'pos_long', 'pos_short', 'capital', 'original_capital',
                'cash', 'deposit', 'trade_price', 'last_price','account_datetime',
                'stop_price', 'stop_line', 'mid_line', 'up_line', 'down_line',
                'ma_flt']

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(self.__class__, self).__init__(ctaEngine, setting)
        
        # 创建K线合成器对象
        self.long_num = self.midNum + self.diffNum
        self.bg_t = BarGenerator(self.onBar, self.timePeriod, self.onTminBar)
        self.am_t = ArrayManager(size=self.long_num + 1)

        self.bg = BarGenerator(self.onBar, self.process_period, self.onXminBar)
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
        # 基于X分钟判断趋势过滤，因此先更新
        self.bg.updateBar(bar)
        self.bg_t.updateBar(bar)
        
        #实时更新账户信息
        if self.trading and self.am_t.inited:
            self.caculateAccountNoTrade(bar)
            self.saveRealtimeStrategyInfor()

    #---------------------------------------------------------------------------
    def onTminBar(self, bar):
        """生成策略信号"""
        #获取K线序列
        self.am_t.updateBar(bar)
        close_array = self.am_t.close

        if not self.am_t.inited:
            return
        
        #计算布林带
        self.std = np.std(close_array[-self.midNum : ], ddof=1)      #样本标准差
        self.mid_line = np.mean(close_array[-self.midNum : ])        #布林带中轨
        self.up_line = self.mid_line + self.stdNum * self.std        #布林带上轨
        self.down_line = self.mid_line - self.stdNum * self.std      #布林带下轨
        self.ma_flt = np.mean(close_array[-self.long_num : ])        #长期过滤均线
        
        #均线过滤信号
        trend_up = self.mid_line >= self.ma_flt                      #趋势向上 ：布林带中轨在过滤均线上方
        trend_down = self.mid_line <= self.ma_flt                    #趋势向下 ：布林带中轨在过滤均线下方
        
        #交易信号
        self.open_long = trend_up and bar.close > self.up_line       #开多信号：收盘价大于布林带上轨
        self.open_short = trend_down and bar.close < self.down_line  #开空信号：收盘价小于布林带下轨
            
    #----------------------------------------------------------------------
    def onXminBar(self, bar):
        """处理交易"""
        # 全撤之前发出的委托
        self.cancelAll()

        # 保存K线数据
        am = self.am
        am.updateBar(bar)
        
        # 排除没有保存完的情况
        if not self.am_t.inited:
            # 实盘时数据初始化不够
            if self.trading:
                print u'%s, %s策略, 初始化天数不足' %(bar.datetime.strftime('%Y-%m-%d %H:%M:%S'), self.name)
                print u'当前已经储存%s分钟K线数量:%s' %(self.timePeriod, self.am_t.count)
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
        # 当前为空仓
        if self.pos == 0 and self.trading:
            if self.open_long:
                self.buy(bar.close + self.slip, self.fixedSize, False)
            elif self.open_short:
                self.short(bar.close - self.slip, self.fixedSize, False)
        
        # 当前持有多头头寸
        if self.pos > 0 and self.trading and self.stop_order_status:
            #更新止盈止损线
            self.stop_line = max(self.stop_price, self.mid_line)
            self.sell(self.stop_line, abs(self.pos), True)
            
        # 当前持有空头头寸
        if self.pos < 0 and self.trading and self.stop_order_status:
            #更新止盈止损线
            self.stop_line = min(self.stop_price, self.mid_line)
            self.cover(self.stop_line, abs(self.pos), True)
        
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
        if order.status == u'已撤销':
            self.stop_order_status = True

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """成交信息变更"""
        self.trade_price = trade.price

        if trade.offset == u'开仓':
            #记录成交信息
            open_mid = self.mid_line                        #开仓时的布林带中轨
            dif = self.stdNum * self.std                    #布林带的宽幅
            self.stop_order_status = True                   #可以发出本地停止单
            
            #开仓后马上挂本地停止单
            if trade.direction == u'多':
                open_stop = self.trade_price - dif * 1.3     #开仓价格下方1.3倍宽幅
                self.stop_price = max(open_mid, open_stop)  #初始固定止损价
                self.sell(self.stop_price, abs(self.pos), True) #挂本地停止单
            elif trade.direction == u'空':
                open_stop = self.trade_price + dif * 1.3
                self.stop_price = min(open_mid, open_stop)
                self.cover(self.stop_price, abs(self.pos), True)
        # 平仓时清空变量
        else:
            self.open_long = False
            self.open_short = False
            self.stop_price = np.nan
            self.stop_line = np.nan
            
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
        if so.status == u'已触发' or so.status == u'等待中':
            self.stop_order_status = False
        elif so.status == u'已撤销':
            self.stop_order_status = True
        
