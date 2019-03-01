# encoding: UTF-8

from __future__ import print_function
import json
from datetime import datetime, timedelta, time

from pymongo import MongoClient

from vnpy.trader.app.ctaStrategy.ctaBase import MINUTE_DB_NAME, TICK_DB_NAME
from vnpy.trader.vtUtility import get_trade_time


#----------------------------------------------------------------------
def cleanData(dbName, collectionName, start):
    """清洗数据"""
    print(u'\n清洗数据库：%s, 集合：%s, 起始日：%s' %(dbName, collectionName, start))
    
    mc = MongoClient('localhost', 27017)    # 创建MongoClient
    cl = mc[dbName][collectionName]         # 获取数据集合
    d = {'datetime':{'$gte':start}}         # 只过滤从start开始的数据
    cx = cl.find(d)                         # 获取数据指针
    
    data_time = [d['datetime'].time() for d in cx]   #数据时间戳
    
    #获取合约交易时间
    trade_time = get_trade_time(collectionName)
    
    # 遍历数据
    for data in cx:
        # 获取时间戳对象
        dt = data['datetime'].time()
        
        # 默认需要清洗
        cleanRequired = True
        
        # 如果在交易事件内，则为有效数据，无需清洗
        
        #没有夜盘， 也没有早盘休息
        if trade_time['morning_rest'] is None and trade_time['night_start'] is None:
            if ((trade_time['morning_start'] <= dt <trade_time['morning_end']) or
                (trade_time['afternoon_start'] <= dt <trade_time['afternoon_end'])):
                cleanRequired = False
        #有早盘休息， 没有夜盘
        elif trade_time['morning_rest'] is not None and trade_time['night_start'] is None:
            if ((trade_time['morning_start'] <= dt <trade_time['morning_rest']) or
                (trade_time['morning_restart'] <= dt < trade_time['morning_end']) or
                (trade_time['afternoon_start'] <= dt <trade_time['afternoon_end'])):
                cleanRequired = False
        #有早盘休息，有夜盘
        else:
            #夜盘隔天结束
            if trade_time['night_end'] < time(3, 0, 0):
                if ((trade_time['morning_start'] <= dt <trade_time['morning_rest']) or
                    (trade_time['morning_restart'] <= dt < trade_time['morning_end']) or
                    (trade_time['afternoon_start'] <= dt <trade_time['afternoon_end']) or
                    (dt >= trade_time['night_start']) or (dt <= trade_time['night_end'])):
                    cleanRequired = False
            #夜盘当天结束
            else:
                if ((trade_time['morning_start'] <= dt <trade_time['morning_rest']) or
                    (trade_time['morning_restart'] <= dt < trade_time['morning_end']) or
                    (trade_time['afternoon_start'] <= dt <trade_time['afternoon_end']) or
                    (trade_time['night_start'] <= dt < trade_time['night_end'])):
                    cleanRequired = False
        
        #如果数据时间戳重复，则需要清洗
        if date_time.count(dt) > 1:
            cleanRequired = True
            date_time.remove(dt)
            print(u'存在重复数据')
            
        # 如果需要清洗
        if cleanRequired:
            print(u'删除无效数据，时间戳：%s' %data['datetime'])
            cl.delete_one(data)
    
    print(u'清洗完成，数据库：%s, 集合：%s' %(dbName, collectionName))
    


#----------------------------------------------------------------------
def runDataCleaning():
    """运行数据清洗"""
    print(u'开始数据清洗工作')
    
    # 加载配置
    setting = {}
    with open("DR_setting.json") as f:
        setting = json.load(f)
        
    # 遍历执行清洗
    today = datetime.now()
    start = today - timedelta(10)   # 清洗过去10天数据
    start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    for l in setting['tick']:
        symbol = l[0]
        cleanData(TICK_DB_NAME, symbol, start)
        
    for l in setting['bar']:
        symbol = l[0]
        cleanData(MINUTE_DB_NAME, symbol, start)
    
    print(u'数据清洗工作完成')
    

if __name__ == '__main__':
    runDataCleaning()
