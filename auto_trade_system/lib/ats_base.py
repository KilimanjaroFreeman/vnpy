# encoding: UTF-8

"""
本文件中包含了自动交易系统中的一些基础设置、类和常量等。
"""

from __future__ import division

import hashlib
import os
from datetime import datetime, timedelta, time
import pandas as pd
import numpy as np
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from collections import OrderedDict
import copy
import datetime
from prettytable import PrettyTable
import json
from time import sleep
import urllib2

from vnpy.trader.app.ctaStrategy.ctaBase import loadContractDetail

#定义一些常量
DIRECTION_LONG = u'多'

#----------------------------------------
def get_file_md5(file_path):
    """计算文件MD5值"""
    f = open(file_path, 'rb')
    md5_obj = hashlib.md5()
    while True:
        d = f.read(8096)

        if not d:
            break

        md5_obj.update(d)
    hashcode = md5_obj.hexdigest()
    f.close()

    return hashcode

##############################################################################
class VtTradeData(object):
    """成交数据类"""
    def __init__(self, series):
        self.gatewayName = series.loc['gatewayName']
        self.rawData = series.loc['rawData']

        #代码编号相关
        self.symbol = series.loc['symbol']
        self.exchange = series.loc['exchange']
        self.vtSymbol = series.loc['vtSymbol']

        self.tradeID = series.loc['tradeID']
        self.vtTradeID = series.loc['vtTradeID']

        self.orderID = series.loc['orderID']
        self.vtOrderID = series.loc['vtOrderID']

        #成交相关
        self.direction = series.loc['direction']
        self.offset = series.loc['offset']
        self.price = series.loc['price']
        self.volume = series.loc['volume']
        self.tradeTime = series.loc['tradeTime']
        self.datetime = series.loc['datetime']
        self.dt = series.loc['dt']
        self.trade_date = series.loc['trade_date']

####################################################################################
class TradingResult(object):
    """每笔交易的结果"""
    def __init__(self, entryPrice, entryDt, exitPrice, 
                 exitDt, volume, rate, slippage, size):
        """Constructor"""
        self.entryPrice = entryPrice    # 开仓价格
        self.exitPrice = exitPrice      # 平仓价格
        
        self.entryDt = entryDt          # 开仓时间datetime    
        self.exitDt = exitDt            # 平仓时间
        
        self.volume = volume    # 交易数量（+/-代表方向）
        
        self.turnover = (self.entryPrice+self.exitPrice)*size*abs(volume)   # 成交金额
        self.commission = self.turnover*rate                                # 手续费成本
        self.slippage = slippage*2*size*abs(volume)                         # 滑点成本
        self.pnl = ((self.exitPrice - self.entryPrice) * volume * size 
                    - self.commission - self.slippage)                      # 净盈亏
        
########################################################################################
class StrategyDBProcessor(object):
    """从数据库中获取策略的不同信息"""
    def __init__(self):
        self.host = 'localhost'
        self.port = 27017
    
    #------------------------------------------------------------------------------------
    def get_data(self, db_name, tb_name, order):
        """依据order从数据库提取数据"""
        #连接数据库
        try:
            db_client = MongoClient(self.host, self.port,
                                    connectTimeoutMS=500)

            #调用server_info查询服务器状态，防止服务器异常并未连接成功
            db_client.server_info()

        except:
            print(u'Mongodb连接失败')
            return

        db = db_client[db_name]
        collection = db[tb_name]
        cursor = collection.find(order)
        data = list(cursor)
        result = pd.DataFrame(data)
        
        if not result.empty:
            del result['_id']
    
        #断开数据库连接
        db_client.close()

        return result
        
    #--------------------------------------------------------------------------------------
    def date_format_trans(self, start_date, end_date):
        """将str格式转化为datetime格式"""
        start_date = pd.Timestamp(start_date)

        if end_date is None:
            end_date = start_date
        else:
            end_date = pd.Timestamp(end_date)

        #为了获取的数据包括end_date这一天
        if end_date.time() == time(0, 0):
            end_date = end_date + timedelta(hours = 23) + timedelta(minutes=59)
        
        return start_date, end_date
    
    #----------------------------------------------------------------------------------------
    def get_strategy_information(self, strategy_name, start_date, end_date=None):
        """从mongodb中获取策略在一段时间内的账户详情"""
        #调整日期格式
        start_date, end_date = self.date_format_trans(start_date, end_date)
        d = {'account_datetime':{'$gte': start_date, '$lte': end_date}}
        db_name = 'Realtime_Strategy_Information'
        result = self.get_data(db_name, strategy_name, d)

        #如果是空列表返回一个空表
        if result.empty:
            return result

        result.set_index('account_datetime', inplace=True)
        result.sort_index(ascending=True, inplace=True)
        result['deposit_ratio'] = result['deposit'] / result['capital'] * 100
        result['pnl'] = result['capital'] - result['original_capital']
        result['pnl_ratio'] = result['pnl'] / result['original_capital'] * 100

        #记录开平仓时间点，0：仓位无变化；1：开多；2：开空；3：平多；4：平空
        pos_change_signal = [0]
        index = result.index
        for i in range(1, len(index)):
            if result.loc[index[i], 'pos'] == result.loc[index[i-1], 'pos']:
                pos_change_signal.append(0)
            elif (result.loc[index[i], 'pos'] > result.loc[index[i-1], 'pos'] and
               result.loc[index[i], 'pos_long'] > result.loc[index[i-1], 'pos_long']):
                pos_change_signal.append(1)
            elif (result.loc[index[i], 'pos'] < result.loc[index[i-1], 'pos'] and
               result.loc[index[i], 'pos_short'] > result.loc[index[i-1], 'pos_short']):
                pos_change_signal.append(2)
            elif (result.loc[index[i], 'pos'] < result.loc[index[i-1], 'pos'] and
               result.loc[index[i], 'pos_long'] < result.loc[index[i-1], 'pos_long']):
                pos_change_signal.append(3)
            elif (result.loc[index[i], 'pos'] > result.loc[index[i-1], 'pos'] and
               result.loc[index[i], 'pos_short'] < result.loc[index[i-1], 'pos_short']):
                pos_change_signal.append(4)

        result['pos_change_signal'] = pos_change_signal
        pos_change_signal_dict = {0: u'not', 1: u'long',
                           2: u'short', 3: u'sell', 4: u'cover'}
        trade_signal = [pos_change_signal_dict[i] for i in pos_change_signal]
        result['trade_signal'] = trade_signal


        return result
         
    #----------------------------------------------------------------------------------  
    def get_trade_result(self, strategy_name,  start_date, end_date):
        """统计一段时间策略的交易表现"""
        start_date, end_date = self.date_format_trans(start_date, end_date)
        db_name = 'TradeRecord'
        d = {'datetime':{'$gte': start_date, '$lte':end_date}}
        result = self.get_data(db_name, strategy_name, d)
        
        #如果是空列表返回一个空表
        if result.empty:
            return result
        
        result.sort_values(by='datetime', ascending=True, inplace=True)
        trade_dict = OrderedDict()
        
        for i in range(len(result)):
            trade_dict[i] = VtTradeData(result.iloc[i,:])
 
        #获取最后交易日价格
        strategy_data = self.get_strategy_information(strategy_name, start_date,
                                                     end_date)
        #如果是空列表返回一个空表
        if strategy_data.empty:
            return strategy_data
        
        last_price = strategy_data.iloc[-1,:].loc['last_price']
        last_date = strategy_data.index[-1]
        trade_result = self.calculate_trade(trade_dict, last_price, last_date)
        
        #计算夏普率
        date = [i.date() for i in strategy_data.index]
        strategy_data['trade_date'] = date
        new_date = pd.Series(date).drop_duplicates()
        daily_pnl = OrderedDict()
        
        #每日盈亏额
        for i in range(len(new_date)):
            d_2 = new_date.iloc[i]
            
            if i == 0: 
                sd_1 = strategy_data[strategy_data['trade_date']==d_2].iloc[0,:].loc['pnl']
                sd_2 = strategy_data[strategy_data['trade_date']==d_2].iloc[-1,:].loc['pnl']
            else:
                d_1 = new_date.iloc[i-1]
                sd_1 = strategy_data[strategy_data['trade_date']==d_1].iloc[-1,:].loc['pnl'] 
                sd_2 = strategy_data[strategy_data['trade_date']==d_2].iloc[-1,:].loc['pnl'] 
            
            di = d_2.strftime('%Y-%m-%d')
            daily_pnl[di] = sd_2 - sd_1 
            
        trade_result['daily_pnl'] = daily_pnl
        pnl_std = np.std(daily_pnl.values()) 
        pnl_mean = np.mean(daily_pnl.values())
        sharp_ratio = pnl_mean / pnl_std * np.sqrt(240)
        trade_result['sharp_ratio'] = sharp_ratio
        trade_result['name'] = strategy_name
        
        return trade_result
    
    #----------------------------------------------------------------------------------------
    def calculate_trade(self, trade_dict, last_price, last_date):
        """
        计算回测结果
        """   
        # 检查成交记录
        if not trade_dict:
            print(u'成交记录为空，无法计算回测结果')
            return {}
        
        #载入合约参数
        symbol = trade_dict[0].symbol
        con_d = loadContractDetail(symbol)
        size = con_d['trade_size']
        price_tick = con_d['price_tick']
        slip = 0
        slippage = slip * price_tick       #默认滑点为0个跳价
        rate = 0.3/10000                   #默认手续费万分之0.3
        
        # 首先基于回测后的成交记录，计算每笔交易的盈亏
        resultList = []             # 交易结果列表
        
        longTrade = []              # 未平仓的多头交易
        shortTrade = []             # 未平仓的空头交易
        
        tradeTimeList = []          # 每笔成交时间戳
        posList = [0]               # 每笔成交后的持仓情况        

        for trade in trade_dict.values():
            # 复制成交对象，因为下面的开平仓交易配对涉及到对成交数量的修改
            # 若不进行复制直接操作，则计算完后所有成交的数量会变成0
            trade = copy.copy(trade)
            
            # 多头交易
            if trade.direction == DIRECTION_LONG:
                # 如果尚无空头交易
                if not shortTrade:
                    longTrade.append(trade)
                # 当前多头交易为平空
                else:
                    while True:
                        entryTrade = shortTrade[0]
                        exitTrade = trade
                        
                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)
                        result = TradingResult(entryTrade.price, entryTrade.dt, 
                                               exitTrade.price, exitTrade.dt,
                                               -closedVolume, rate, slippage, size)
                        resultList.append(result)
                        
                        posList.extend([-1,0])
                        tradeTimeList.extend([result.entryDt, result.exitDt])
                        
                        # 计算未清算部分
                        entryTrade.volume -= closedVolume
                        exitTrade.volume -= closedVolume
                        
                        # 如果开仓交易已经全部清算，则从列表中移除
                        if not entryTrade.volume:
                            shortTrade.pop(0)
                        
                        # 如果平仓交易已经全部清算，则退出循环
                        if not exitTrade.volume:
                            break
                        
                        # 如果平仓交易未全部清算，
                        if exitTrade.volume:
                            # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                            # 等于新的反向开仓交易，添加到队列中
                            if not shortTrade:
                                longTrade.append(exitTrade)
                                break
                            # 如果开仓交易还有剩余，则进入下一轮循环
                            else:
                                pass
                        
            # 空头交易        
            else:
                # 如果尚无多头交易
                if not longTrade:
                    shortTrade.append(trade)
                # 当前空头交易为平多
                else:                    
                    while True:
                        entryTrade = longTrade[0]
                        exitTrade = trade
                        
                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)
                        result = TradingResult(entryTrade.price, entryTrade.dt, 
                                               exitTrade.price, exitTrade.dt,
                                               closedVolume, rate, slippage, size)
                        resultList.append(result)
                        
                        posList.extend([1,0])
                        tradeTimeList.extend([result.entryDt, result.exitDt])

                        # 计算未清算部分
                        entryTrade.volume -= closedVolume
                        exitTrade.volume -= closedVolume
                        
                        # 如果开仓交易已经全部清算，则从列表中移除
                        if not entryTrade.volume:
                            longTrade.pop(0)
                        
                        # 如果平仓交易已经全部清算，则退出循环
                        if not exitTrade.volume:
                            break
                        
                        # 如果平仓交易未全部清算，
                        if exitTrade.volume:
                            # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                            # 等于新的反向开仓交易，添加到队列中
                            if not longTrade:
                                shortTrade.append(exitTrade)
                                break
                            # 如果开仓交易还有剩余，则进入下一轮循环
                            else:
                                pass                    
        
        # 到最后交易日尚未平仓的交易，则以最后价格平仓
        endPrice = last_price
            
        for trade in longTrade:
            result = TradingResult(trade.price, trade.dt, endPrice, last_date, 
                                   trade.volume, rate, slippage, size)
            resultList.append(result)
            
        for trade in shortTrade:
            result = TradingResult(trade.price, trade.dt, endPrice, last_date, 
                                   -trade.volume, rate, slippage, size)
            resultList.append(result)            
        
        # 检查是否有交易
        if not resultList:
            print(u'无交易结果')
            return {}
        
        # 然后基于每笔交易的结果，我们可以计算具体的盈亏曲线和最大回撤等        
        capital = 0             # 资金
        maxCapital = 0          # 资金最高净值
        drawdown = 0            # 回撤
        
        totalResult = 0         # 总成交数量
        totalTurnover = 0       # 总成交金额（合约面值）
        totalCommission = 0     # 总手续费
        totalSlippage = 0       # 总滑点
        
        timeList = []           # 时间序列
        pnlList = []            # 每笔盈亏序列
        capitalList = []        # 盈亏汇总的时间序列
        drawdownList = []       # 回撤的时间序列
        
        winningResult = 0       # 盈利次数
        losingResult = 0        # 亏损次数		
        totalWinning = 0        # 总盈利金额		
        totalLosing = 0         # 总亏损金额        
        
        for result in resultList:
            capital += result.pnl
            maxCapital = max(capital, maxCapital)
            drawdown = capital - maxCapital
            
            pnlList.append(result.pnl)
            timeList.append(result.exitDt)      # 交易的时间戳使用平仓时间
            capitalList.append(capital)
            drawdownList.append(drawdown)
            
            totalResult += 1
            totalTurnover += result.turnover
            totalCommission += result.commission
            totalSlippage += result.slippage
            
            if result.pnl >= 0:
                winningResult += 1
                totalWinning += result.pnl
            else:
                losingResult += 1
                totalLosing += result.pnl
                
        # 计算盈亏相关数据
        winningRate = winningResult/totalResult*100         # 胜率
        
        averageWinning = 0                                  # 这里把数据都初始化为0
        averageLosing = 0
        profitLossRatio = 0
        
        if winningResult:
            averageWinning = totalWinning/winningResult     # 平均每笔盈利
        if losingResult:
            averageLosing = totalLosing/losingResult        # 平均每笔亏损
        if averageLosing:
            profitLossRatio = -averageWinning/averageLosing # 盈亏比

        # 返回回测结果
        d = {}
        d['capital'] = capital
        d['maxCapital'] = maxCapital
        d['drawdown'] = drawdown
        d['totalResult'] = totalResult
        d['totalTurnover'] = totalTurnover
        d['totalCommission'] = totalCommission
        d['totalSlippage'] = totalSlippage
        d['timeList'] = timeList
        d['pnlList'] = pnlList
        d['capitalList'] = capitalList
        d['drawdownList'] = drawdownList
        d['winningRate'] = winningRate
        d['averageWinning'] = averageWinning
        d['averageLosing'] = averageLosing
        d['profitLossRatio'] = profitLossRatio
        d['posList'] = posList
        d['tradeTimeList'] = tradeTimeList
        d['resultList'] = resultList
        
        trade_result = pd.Series([])
        trade_result[u'first_deal'] = d['timeList'][0]
        trade_result[u'last_deal'] = d['timeList'][-1]
        
        trade_result[u'number_of_deals'] = d['totalResult']      
        trade_result[u'total_pnl'] = d['capital']
        trade_result[u'maximun_withdrawal'] =min(d['drawdownList'])                
        
        trade_result[u'average_profit_per_deal'] = d['capital']/d['totalResult']
        trade_result[u'average_slippage_per_deal'] = d['totalSlippage']/d['totalResult']
        trade_result[u'average_commission_per_deal'] = d['totalCommission']/d['totalResult']
        
        trade_result[u'win_rate'] = d['winningRate']
        trade_result[u'average_winning'] =  d['averageWinning']
        trade_result[u'average_losing'] = d['averageLosing']
        trade_result[u'profit_loss_ratio'] = d['profitLossRatio']
                     
        return trade_result

################################################################################################################
class AccountMonitor(object):
    '''监控策略运行状况，输出到控制台''' 
    def __init__(self):
        pass
      
    #-------------------------------------------------------------------------  
    def get_account_from_db(self, strategy_class, strategy_names, vt_symbol):
        '''从Mongodb中读取账户详情'''
        account = []
        try:
            dbClient = MongoClient('localhost', 27017, connectTimeOutMS=500)
            #调用server_info查询服务器状态， 防止服务器异常并未连接成功
            dbClient.server_info()
        except ConnectionFailure:
            print u'读取合约连接数据库失败'
        if dbClient:
            db=dbClient['VnTrader_Position_Db']
            for i in range(len(strategy_names)):
                collection = db[strategy_class[i]]
                flt = {'name': strategy_names[i], 'vtSymbol': vt_symbol[i]}
                cursor = collection.find(flt)
                try:
                    d = list(cursor)[0]
                    account.append(d)
                except:
                    pass
                    
        dbClient.close()
        return account
    
    #------------------------------------------------------------------------------------------
    def send_strategy_account_to_bg(self, dt, ID, asset, deposit):
        '''把策略的账户信息发送到后端监控'''
        try:
            url_1 = u'http://192.168.10.132:8888/dzkj-st/strategyDataStatistics/addStrategyData?'
            url_2 = u'dealdate=%s&backestId=%s&totalAsserts=%.2f&marketValue=%.2f'%(dt, ID, asset, deposit)
            url = url_1 + url_2
            req = urllib2.Request(url)
            response = urllib2.urlopen(req)
            html = response.read()
            return html
        except:
            print u'datetime %s: 发送策略账户到后端失败'%datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    #------------------------------------------------------------------------------------------------- 
    def print_account_information(self):
        '''打印账户信息'''  
        #读取正在运行的策略名单
        f = file(r'./CTA_setting.json')
        strategy_list = json.load(f)
        strategy_names = []
        strategy_class = []
        vt_symbol = []
        strategy_not_send = []                 #正在运行却选择不发送到后端的策略
        
        for s in strategy_list:
            strategy_names.append(s['name'])
            strategy_class.append(s['className'])
            vt_symbol.append(s['vtSymbol'])
        
        #每一分钟查询账户信息一次
        while True:
            account = self.get_account_from_db(strategy_class, strategy_names, vt_symbol)
            
            if account == []:
                pass
            else:
                pt = PrettyTable(['Strategy Name', 'Capital', 'Cash', 'Margin', 'Margin Ratio', 'NetPnL',
                                'PnL Ratio', 'Symbol', 'Pos', 'Long Pos', 'Short Pos', 'Time', 'Status'])
                total_capital = 0
                total_cash = 0
                total_deposit = 0
                total_original_capital = 0
                time_now = datetime.datetime.now()
                total_pos = 0
                total_long_pos = 0
                total_short_pos = 0

                for a in account:
                    #如果策略记录在数据库中的时间和当前时间差2分钟即认为策略停止运行
                    time_diff = time_now - a['account_datetime']

                    if time_diff > datetime.timedelta(minutes=2):
                        status = '*** Stop ***'
                    else:
                        status = '*** Runing ***'

                    margin_ratio = a['deposit'] / a['capital'] * 100
                    pnl = a['capital'] - a['original_capital']
                    pnl_ratio = pnl / a['original_capital'] * 100
                    pt.add_row([a['name'], '%.2f'%a['capital'], '%.2f'%a['cash'], '%.2f'%a['deposit'], 
                                '%.2f %%'%margin_ratio, '%.2f'%pnl, '%.2f %%'%pnl_ratio, a['vtSymbol'], a['pos'], a['pos_long'],
                                a['pos_short'],a['account_datetime'].strftime('%Y-%m-%d %H:%M:%S'), status])
                    total_capital += a['capital']
                    total_cash += a['cash']
                    total_deposit += a['deposit']
                    total_original_capital += a['original_capital']
                    total_pos += a['pos']
                    total_long_pos += a['pos_long']
                    total_short_pos += a['pos_short']

                    #发送策略账户信息
#                     if a['name'] in strategy_not_send or status == '*** Stop ***':
#                         continue
#                     asset = a['capital']
#                     deposit = a['deposit']
#                     dt = a['account_datetime'].strftime('%Y-%m-%d')
#                     ID = a['name']
#                     self.send_strategy_account_to_bg(dt, ID, asset, deposit)

                total_pnl = total_capital - total_original_capital
                total_margin_ratio = total_deposit / total_capital * 100
                total_pnl_ratio = total_pnl / total_original_capital * 100
                pt.add_row(['*** Account ***','* %.2f *'%total_capital, '* %.2f *'%total_cash, 
                            '* %.2f *'%total_deposit, '* %.2f %% *'%total_margin_ratio, '* %.2f *'%total_pnl,
                            '* %.2f %% *'%total_pnl_ratio, '-', '* %s *'%total_pos, '* %s *'%total_long_pos, 
                            '* %s *'%total_short_pos, '-', '-'])
                pt.align = 'c'
                print '*'*160
                print(pt)
                
            sleep(60)

    #--------------------------------------------------------------------------------------------------------------
    
    
