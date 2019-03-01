# encoding: UTF-8

'''
本文件中包含了CTA模块中用到的一些基础设置、类和常量等。
'''

from datetime import time
from pymongo import MongoClient, ASCENDING

# CTA引擎中涉及的数据类定义
from vnpy.trader.vtConstant import EMPTY_UNICODE, EMPTY_STRING, EMPTY_FLOAT, EMPTY_INT

# 常量定义
# CTA引擎中涉及到的交易方向类型
CTAORDER_BUY = u'买开'
CTAORDER_SELL = u'卖平'
CTAORDER_SHORT = u'卖开'
CTAORDER_COVER = u'买平'

# 本地停止单状态
STOPORDER_WAITING = u'等待中'
STOPORDER_CANCELLED = u'已撤销'
STOPORDER_TRIGGERED = u'已触发'

# 本地停止单前缀
STOPORDERPREFIX = 'CtaStopOrder.'

# 数据库名称
SETTING_DB_NAME = 'VnTrader_Setting_Db'
POSITION_DB_NAME = 'VnTrader_Position_Db'

TICK_DB_NAME = 'VnTrader_Tick_Db'
DAILY_DB_NAME = 'VnTrader_Daily_Db'
MINUTE_DB_NAME = 'VnTrader_1Min_Db'

# 引擎类型，用于区分当前策略的运行环境
ENGINETYPE_BACKTESTING = 'backtesting'  # 回测
ENGINETYPE_TRADING = 'trading'          # 实盘

# CTA模块事件
EVENT_CTA_LOG = 'eCtaLog'               # CTA相关的日志事件
EVENT_CTA_STRATEGY = 'eCtaStrategy.'    # CTA策略状态变化事件


########################################################################
class StopOrder(object):
    """本地停止单"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.vtSymbol = EMPTY_STRING
        self.orderType = EMPTY_UNICODE
        self.direction = EMPTY_UNICODE
        self.offset = EMPTY_UNICODE
        self.price = EMPTY_FLOAT
        self.volume = EMPTY_INT
        
        self.strategy = None             # 下停止单的策略对象
        self.stopOrderID = EMPTY_STRING  # 停止单的本地编号 
        self.status = EMPTY_STRING       # 停止单状态

########################################################################
# 自己定义的一些函数
#-----------------------------------------------------
def loadContractDetail(vtSymbol):
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
        symbol = ''.join([x for x in vtSymbol if x.isalpha()])
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
    
    return d
