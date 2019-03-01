# encoding: UTF-8

'''
本文件包含了CTA引擎中的策略开发用模板，开发策略时需要继承CtaTemplate类。
'''

from pymongo import MongoClient, ASCENDING
from collections import OrderedDict
import numpy as np
from datetime import datetime, time, timedelta
import time as time_stmp
import pymongo
import copy
import urllib2
import sys
import json

from vnpy.trader.vtConstant import *
from vnpy.trader.vtUtility import BarGenerator, ArrayManager
from .ctaBase import *

########################################################################
class CtaTemplate(object):
    """CTA策略模板"""
    
    # 策略类的名称和作者
    className = 'CtaTemplate'
    author = EMPTY_UNICODE
    
    # MongoDB数据库的名称，K线数据库默认为1分钟
    tickDbName = TICK_DB_NAME
    barDbName = MINUTE_DB_NAME
    
    # 策略的基本参数
    name = EMPTY_UNICODE           # 策略实例名称
    vtSymbol = EMPTY_STRING        # 交易的合约vt系统代码    
    productClass = EMPTY_STRING    # 产品类型（只有IB接口需要）
    currency = EMPTY_STRING        # 货币（只有IB接口需要）
    
    # 策略的基本变量，由引擎管理
    inited = False                 # 是否进行了初始化
    trading = False                # 是否启动交易，由引擎管理
    pos = 0                        # 持仓情况
    
    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol']
    
    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos']
    
    # 同步列表，保存了需要保存到数据库的变量名称
    syncList = ['pos']

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        self.ctaEngine = ctaEngine

        # 设置策略的参数
        if setting:
            d = self.__dict__
            for key in self.paramList:
                if key in setting:
                    d[key] = setting[key]
    
    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        raise NotImplementedError

    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        raise NotImplementedError

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def onStopOrder(self, so):
        """收到停止单推送（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def buy(self, price, volume, stop=False):
        """买开"""
        return self.sendOrder(CTAORDER_BUY, price, volume, stop)
    
    #----------------------------------------------------------------------
    def sell(self, price, volume, stop=False):
        """卖平"""
        return self.sendOrder(CTAORDER_SELL, price, volume, stop)       

    #----------------------------------------------------------------------
    def short(self, price, volume, stop=False):
        """卖开"""
        return self.sendOrder(CTAORDER_SHORT, price, volume, stop)          
 
    #----------------------------------------------------------------------
    def cover(self, price, volume, stop=False):
        """买平"""
        return self.sendOrder(CTAORDER_COVER, price, volume, stop)
        
    #----------------------------------------------------------------------
    def sendOrder(self, orderType, price, volume, stop=False):
        """发送委托"""
        if self.trading:
            # 如果stop为True，则意味着发本地停止单
            if stop:
                vtOrderIDList = self.ctaEngine.sendStopOrder(self.vtSymbol, orderType, price, volume, self)
            else:
                vtOrderIDList = self.ctaEngine.sendOrder(self.vtSymbol, orderType, price, volume, self) 
            return vtOrderIDList
        else:
            # 交易停止时发单返回空字符串
            return []
        
    #----------------------------------------------------------------------
    def cancelOrder(self, vtOrderID):
        """撤单"""
        # 如果发单号为空字符串，则不进行后续操作
        if not vtOrderID:
            return
        
        if STOPORDERPREFIX in vtOrderID:
            self.ctaEngine.cancelStopOrder(vtOrderID)
        else:
            self.ctaEngine.cancelOrder(vtOrderID)
            
    #----------------------------------------------------------------------
    def cancelAll(self):
        """全部撤单"""
        self.ctaEngine.cancelAll(self.name)
    
    #----------------------------------------------------------------------
    def insertTick(self, tick):
        """向数据库中插入tick数据"""
        self.ctaEngine.insertData(self.tickDbName, self.vtSymbol, tick)
    
    #----------------------------------------------------------------------
    def insertBar(self, bar):
        """向数据库中插入bar数据"""
        self.ctaEngine.insertData(self.barDbName, self.vtSymbol, bar)
        
    #----------------------------------------------------------------------
    def loadTick(self, days):
        """读取tick数据"""
        return self.ctaEngine.loadTick(self.tickDbName, self.vtSymbol, days)
    
    #----------------------------------------------------------------------
    def loadBar(self, days):
        """读取bar数据"""
        return self.ctaEngine.loadBar(self.barDbName, self.vtSymbol, days)
    
    #----------------------------------------------------------------------
    def writeCtaLog(self, content):
        """记录CTA日志"""
        content = self.name + ':' + content
        self.ctaEngine.writeCtaLog(content)
        
    #----------------------------------------------------------------------
    def putEvent(self):
        """发出策略状态变化事件"""
        self.ctaEngine.putStrategyEvent(self.name)
        
    #----------------------------------------------------------------------
    def getEngineType(self):
        """查询当前运行的环境"""
        return self.ctaEngine.engineType
    
    #----------------------------------------------------------------------
    def saveSyncData(self):
        """保存同步数据到数据库"""
        if self.trading:
            self.ctaEngine.saveSyncData(self)
    
    #----------------------------------------------------------------------
    def getPriceTick(self):
        """查询最小价格变动"""
        return self.ctaEngine.getPriceTick(self)
        
    #---------------------------------------------------------------------
    #-----------------------自己添加的函数---------------------------------
    #----------------------------------------------------------------------
    def insertTrade(self,DBName, vtStrategy, trade):
        """向数据库中插入交易记录"""
        trade_data = copy.deepcopy(trade)
        trade_data.trade_date = datetime.now().strftime('%Y%m%d')
        trade_data.datetime = datetime.now()

        if 'dt' not in dir(trade):
            dt = trade_data.trade_date + ' ' + trade.tradeTime
            trade_data.dt = datetime.strptime(dt,'%Y%m%d %H:%M:%S')
            
        self.ctaEngine.insertData(DBName, vtStrategy, trade_data)
        
    #---------------------------------------------------------------------
    def saveRealtimeStrategyInfor(self):
        """向数据库中插入策略的实时信息"""
        DBName = 'Realtime_Strategy_Information'
        TBName = self.name
        d = {}
        d['name'] = self.name
        d['vtSymbol'] = self.vtSymbol

        for key in self.syncList:
            d[key] = self.__getattribute__(key)

        self.ctaEngine.insertData(DBName, TBName, d)

    #---------------------------------------------------------------------
    def caculateAccountNoTrade(self, bar):
        """没有成交时，每一个bar账户明细改变"""
        total_pos_no_trade = abs(self.pos_long) + abs(self.pos_short)
        
        if total_pos_no_trade > 0:
            long_ratio = np.true_divide(abs(self.pos_long), total_pos_no_trade)
            short_ratio = np.true_divide(abs(self.pos_short), total_pos_no_trade)
        else:
            long_ratio = 0
            short_ratio = 0
        
        #多头仓位和空头仓位价格变化对账户余额的影响
        d_long = bar.close * self.trade_size * abs(self.pos_long) - long_ratio * self.deposit / self.deposit_ratio
        d_short = short_ratio * self.deposit / self.deposit_ratio - bar.close * self.trade_size * abs(self.pos_short)
        d_d = d_long + d_short
        self.capital = self.capital + d_d
        self.deposit = bar.close * self.trade_size * self.deposit_ratio * total_pos_no_trade
        self.cash = self.capital - self.deposit
        self.account_datetime = datetime.now()
        
        # 同步变量到数据库
        self.saveSyncData()
        
    #------------------------------------------------------------------------
    def caculateAccountTrade(self, trade):
        """成交时，账户明细改变"""
        
        #成交前账户信息
        total_pos_no_trade = abs(self.pos_long) + abs(self.pos_short)
        
        if total_pos_no_trade > 0:
            long_ratio = np.true_divide(abs(self.pos_long), total_pos_no_trade)
            short_ratio = np.true_divide(abs(self.pos_short), total_pos_no_trade)
        else:
            long_ratio = 0
            short_ratio = 0
        
        #多头仓位和空头仓位价格变化对账户余额的影响
        d_long = trade.price * self.trade_size * abs(self.pos_long) - long_ratio * self.deposit / self.deposit_ratio
        d_short = short_ratio * self.deposit / self.deposit_ratio - trade.price * self.trade_size * abs(self.pos_short)
        d_d = d_long + d_short
        self.capital = self.capital + d_d
        self.deposit = trade.price * self.trade_size * self.deposit_ratio * total_pos_no_trade
        self.cash = self.capital - self.deposit

        #更改多空仓位信息
        if trade.offset == u'开仓': 
            if trade.direction == u'多':
                self.pos_long += abs(trade.volume)
            elif trade.direction == u'空':
                self.pos_short += abs(trade.volume)
        else:
            if trade.direction == u'多':
                self.pos_short -= abs(trade.volume)
            elif trade.direction == u'空':
                self.pos_long -= abs(trade.volume)
                
        total_pos = abs(self.pos_long) + abs(self.pos_short)
        
        #成交后账户信息
        if trade.offset == u'开仓':
            d_1 = trade.price * self.trade_size * self.deposit_ratio * abs(trade.volume)
            self.cash = self.cash - d_1 - (d_1 / self.deposit_ratio * self.rate)        #扣除手续费
            self.deposit = trade.price * self.trade_size * self.deposit_ratio * total_pos
            self.capital = self.cash + self.deposit
        else:
            d_1 = trade.price * self.trade_size * self.deposit_ratio * abs(trade.volume)
            self.cash = self.cash + d_1 - (d_1 / self.deposit_ratio * self.rate)         #扣除手续费
            self.deposit = trade.price * self.trade_size * self.deposit_ratio * total_pos
            self.capital = self.cash + self.deposit
            
        self.account_datetime = datetime.now()

        # 同步变量到数据库
        self.saveSyncData()
    
    #---------------------------------------------------------------------------------
    def loadContractDetail(self, sym):
        try:
            # 设置MongoDB操作的超时时间为0.5秒
            dbClient = MongoClient('localhost', 27017, connectTimeoutMS=500)
            
            # 调用server_info查询服务器状态，防止服务器异常并未连接成功
            dbClient.server_info()
        except ConnectionFailure:
            print u'读取合约连接数据库失败'
            
        if dbClient:
            db = dbClient['VnTrader_Contract']
            collection = db['Detail']
            #回测模式下self.vtSymbol为空
            if self.vtSymbol:
                symbol = ''.join([x for x in self.vtSymbol if x.isalpha()])
            else:
                symbol = sym
            flt = {'symbol': symbol}
            cursor = collection.find(flt)
            if cursor:
                Data = list(cursor)
            else:
                Data = []
        else:
            print u'读取合约参数失败'
            Data = []
        
        if not Data:
            return
        
        d = Data[0]
        self.trade_size = d['trade_size']
        self.deposit_ratio = d['deposit_ratio']
        self.tickPrice = d['price_tick']

    #--------------------------------------------------------------------------------
    def send_strategy_account_to_bg(self):
        '''把策略的账户信息发送到后端监控'''
        try:
            dt = self.account_datetime.replace(second=0, microsecond=0)
            dt = int(time_stmp.mktime(dt.timetuple())) * 1000             #毫秒级别时间戳
            url_1 = u'http://192.168.10.132:8888/dzkj-st/strategyDataStatistics/addPersonStrategyData?'
            url_2 = (u'time=%d&strategy_name=%s&long_pos=%s&short_pos=%s&init_money=%.2f&acculumate_net=%.2f&stock_index_futures=%s'\
                    %(dt, self.className, self.pos_long, self.pos_short, self.original_capital, self.capital, self.last_price))
            url = url_1 + url_2
            req = urllib2.Request(url)
            response = urllib2.urlopen(req)
            html = response.read()
            return html
        except:
            print u'datetime %s: 发送策略账户到后端失败'%datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
    #---------------------------------------------------------------------------------
    def closePositionAndStop(self, bar):
        """紧急操作，平掉策略仓位并且停止策略"""
        # 当前持有多头头寸
        if self.pos_long != 0 and self.trading:
            #平多
            self.sell(bar.close - self.slip, abs(self.pos_long), False)
         
        # 当前持有空头头寸
        if self.pos_short != 0 and self.trading:
            #平空
            self.cover(bar.close + self.slip, abs(self.pos_short), False)
        
        #如果仓位为0，停止策略
        if self.pos_long == 0 and self.pos_short == 0 and self.trading:
            self.trading = False
        
    def replaceDominantContract(self, bar):
        """更换主力合约，平掉当前头寸，更改配置文件"""
        if self.pos_long != 0 and self.trading:
            #平多
            self.sell(bar.close - self.slip, abs(self.pos_long), False)

        if self.pos_short != 0 and self.trading:
            #平空
            self.cover(bar.close + self.slip, abs(self.pos_short), False)

        #如果仓位为0
        if self.pos_long == 0 and self.pos_short == 0 and self.trading:
            #更新数据库
            try:
                old_symbol = self.replaceContract['old_contract']
                new_symbol = self.replaceContract['new_contract']
                self._database_handle(old_symbol, new_symbol)
            except:
                print('%s数据库更新失败'%self.name)
                return
    
            #更新配置文件
            self._json_handle(self.name, new_symbol)

    #--------------------------------------------------------------------------------------
    def _json_handle(self, strategy_name, new_symbol):
        """更改json配置文件，更新主力合约号"""
        file_dir = r'./CTA_setting.json'
        f = file(file_dir)
        strategy_list = json.load(f)
 
        for n, d in enumerate(strategy_list):
            if d['name'] == strategy_name:
                d['vtSymbol'] = new_symbol
                d['status'] = 'run'
                #删除更改主力合约标志
                try:
                    del d['replaceContract']
                except:
                    pass

        strategy_list = map(self._order_dict, strategy_list)

        with open(file_dir, 'w') as f:
            jsonL = json.dumps(strategy_list, indent=5)
            f.write(jsonL)
            print(u"%s配置文件更新成功"%self.name)

    #------------------------------------------------------------------------
    def _order_dict(self, d):
        """把字典转化为顺序字典方便显示"""
        new_d = OrderedDict()
        new_d['className'] = d['className']
        new_d['name'] = d['name']
        new_d['vtSymbol'] = d['vtSymbol']
        new_d['alpha'] = d['alpha']
        new_d['fixedSize'] = d['fixedSize']
        new_d['initDays'] = d['initDays']
        new_d['status'] = d['status']
        
        del d['className']
        del d['name']
        del d['vtSymbol'] 
        del d['alpha']
        del d['fixedSize']
        del d['initDays']
        del d['status']
        
        for k in d:
            new_d[k] = d[k]
            
        return new_d

    #----------------------------------------------------------------------------------------
    def _database_handle(self,  old_symbol, new_symbol):
        """如果需要更换主力合约， 把旧合约的账户信息复制到新合约的数据库中"""
        try:
            dbClient = MongoClient('localhost', 27017, connectTimeOutMS=500)
            # 调用server_info查询服务器状态， 防止服务器异常并未连接成功
            dbClient.server_info()
        except ConnectionFailure:
            print u'读取合约连接数据库失败'
            
        if dbClient:
            db=dbClient['VnTrader_Position_Db']
            collection = db[self.className]
            flt = {'name': self.name, 'vtSymbol': old_symbol}
            cursor = collection.find(flt)
            
            try:
                d = list(cursor)[0]
            except:
                pass

            new_d = {}
            new_d['pos'] = 0
            new_d['pos_long'] = 0
            new_d['pos_short'] = 0
            new_d['deposit'] = 0
            new_d['cash'] = d['capital']
            new_d['capital'] = d['capital']
            new_d['original_capital'] = d['original_capital']
            new_d['vtSymbol'] = new_symbol
            new_d['name'] = d['name']
            new_d['account_datetime'] = d['account_datetime']
            
            flt = {'name': d['name'], 'vtSymbol': new_symbol}
            collection.replace_one(flt, new_d, upsert=True)
            print(u"%s数据库更换主力合约成功"%d['name'])
        dbClient.close()
        
########################################################################
class TargetPosTemplate(CtaTemplate):
    """
    允许直接通过修改目标持仓来实现交易的策略模板
    
    开发策略时，无需再调用buy/sell/cover/short这些具体的委托指令，
    只需在策略逻辑运行完成后调用setTargetPos设置目标持仓，底层算法
    会自动完成相关交易，适合不擅长管理交易挂撤单细节的用户。    
    
    使用该模板开发策略时，请在以下回调方法中先调用母类的方法：
    onTick
    onBar
    onOrder
    
    假设策略名为TestStrategy，请在onTick回调中加上：
    super(TestStrategy, self).onTick(tick)
    
    其他方法类同。
    """
    
    className = 'TargetPosTemplate'
    author = u'量衍投资'
    
    # 目标持仓模板的基本变量
    tickAdd = 1             # 委托时相对基准价格的超价
    lastTick = None         # 最新tick数据
    lastBar = None          # 最新bar数据
    targetPos = EMPTY_INT   # 目标持仓
    orderList = []          # 委托号列表

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'targetPos']

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(TargetPosTemplate, self).__init__(ctaEngine, setting)
        
    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情推送"""
        self.lastTick = tick
        
        # 实盘模式下，启动交易后，需要根据tick的实时推送执行自动开平仓操作
        if self.trading:
            self.trade()
        
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到K线推送"""
        self.lastBar = bar
    
    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托推送"""
        if order.status == STATUS_ALLTRADED or order.status == STATUS_CANCELLED:
            if order.vtOrderID in self.orderList:
                self.orderList.remove(order.vtOrderID)
    
    #----------------------------------------------------------------------
    def setTargetPos(self, targetPos):
        """设置目标仓位"""
        self.targetPos = targetPos
        
        self.trade()
        
    #----------------------------------------------------------------------
    def trade(self):
        """执行交易"""
        # 先撤销之前的委托
        self.cancelAll()
        
        # 如果目标仓位和实际仓位一致，则不进行任何操作
        posChange = self.targetPos - self.pos
        if not posChange:
            return
        
        # 确定委托基准价格，有tick数据时优先使用，否则使用bar
        longPrice = 0
        shortPrice = 0
        
        if self.lastTick:
            if posChange > 0:
                longPrice = self.lastTick.askPrice1 + self.tickAdd
                if self.lastTick.upperLimit:
                    longPrice = min(longPrice, self.lastTick.upperLimit)         # 涨停价检查
            else:
                shortPrice = self.lastTick.bidPrice1 - self.tickAdd
                if self.lastTick.lowerLimit:
                    shortPrice = max(shortPrice, self.lastTick.lowerLimit)       # 跌停价检查
        else:
            if posChange > 0:
                longPrice = self.lastBar.close + self.tickAdd
            else:
                shortPrice = self.lastBar.close - self.tickAdd
        
        # 回测模式下，采用合并平仓和反向开仓委托的方式
        if self.getEngineType() == ENGINETYPE_BACKTESTING:
            if posChange > 0:
                l = self.buy(longPrice, abs(posChange))
            else:
                l = self.short(shortPrice, abs(posChange))
            self.orderList.extend(l)
        
        # 实盘模式下，首先确保之前的委托都已经结束（全成、撤销）
        # 然后先发平仓委托，等待成交后，再发送新的开仓委托
        else:
            # 检查之前委托都已结束
            if self.orderList:
                return
            
            # 买入
            if posChange > 0:
                # 若当前有空头持仓
                if self.pos < 0:
                    # 若买入量小于空头持仓，则直接平空买入量
                    if posChange < abs(self.pos):
                        l = self.cover(longPrice, posChange)
                    # 否则先平所有的空头仓位
                    else:
                        l = self.cover(longPrice, abs(self.pos))
                # 若没有空头持仓，则执行开仓操作
                else:
                    l = self.buy(longPrice, abs(posChange))
            # 卖出和以上相反
            else:
                if self.pos > 0:
                    if abs(posChange) < self.pos:
                        l = self.sell(shortPrice, abs(posChange))
                    else:
                        l = self.sell(shortPrice, abs(self.pos))
                else:
                    l = self.short(shortPrice, abs(posChange))
            self.orderList.extend(l)
    

########################################################################
class CtaSignal(object):
    """
    CTA策略信号，负责纯粹的信号生成（目标仓位），不参与具体交易管理
    """

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.signalPos = 0      # 信号仓位
    
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """K线推送"""
        pass
    
    #----------------------------------------------------------------------
    def onTick(self, tick):
        """Tick推送"""
        pass
        
    #----------------------------------------------------------------------
    def setSignalPos(self, pos):
        """设置信号仓位"""
        self.signalPos = pos
        
    #----------------------------------------------------------------------
    def getSignalPos(self):
        """获取信号仓位"""
        return self.signalPos
