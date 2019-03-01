# -*- encoding:utf-8 -*-

import pymongo
import numpy as py

DBName = 'VnTrader_Contract'
client = pymongo.MongoClient('localhost',27017)
collection = client[DBName]['Detail']
data = [
    {'symbol':'rb', 'trade_size':10.0, 'deposit_ratio':0.09, 'price_tick':1.0},
    {'symbol':'i', 'trade_size':100.0, 'deposit_ratio':0.1, 'price_tick':0.5},
    {'symbol':'jm', 'trade_size':60.0, 'deposit_ratio':0.12, 'price_tick':0.5},
    {'symbol':'j', 'trade_size':100.0, 'deposit_ratio':0.12, 'price_tick':0.5},
    {'symbol':'hc', 'trade_size':10.0, 'deposit_ratio':0.08, 'price_tick':1.0},
    {'symbol':'ru', 'trade_size':10.0, 'deposit_ratio':0.09, 'price_tick':5.0},
    {'symbol':'TA', 'trade_size':5.0, 'deposit_ratio':0.06, 'price_tick':2.0},
    {'symbol':'MA', 'trade_size':10.0, 'deposit_ratio':0.07, 'price_tick':1.0},
    {'symbol':'pp', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':1.0},
    {'symbol':'cu', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':10.0},
    {'symbol':'ni', 'trade_size':1.0, 'deposit_ratio':0.08, 'price_tick':10.0},
    {'symbol':'zn', 'trade_size':5.0, 'deposit_ratio':0.08, 'price_tick':5.0},
    {'symbol':'p', 'trade_size':10.0, 'deposit_ratio':0.06, 'price_tick':2.0},
    {'symbol':'CF', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':5.0},
    {'symbol':'SR', 'trade_size':10.0, 'deposit_ratio':0.05, 'price_tick':1.0},
    {'symbol':'c', 'trade_size':10.0, 'deposit_ratio':0.05, 'price_tick':1.0},
    {'symbol':'jd', 'trade_size':10.0, 'deposit_ratio':0.08, 'price_tick':1.0},
    {'symbol':'IF', 'trade_size':300.0, 'deposit_ratio':0.15, 'price_tick':0.2},
    {'symbol':'IH', 'trade_size':300.0, 'deposit_ratio':0.15, 'price_tick':0.2},
    {'symbol':'IC', 'trade_size':200.0, 'deposit_ratio':0.3, 'price_tick':0.2},
    {'symbol':'au', 'trade_size':1000.0, 'deposit_ratio':0.05, 'price_tick':0.05},
    {'symbol':'ag', 'trade_size':15.0, 'deposit_ratio':0.06, 'price_tick':1.0},
    {'symbol':'pb', 'trade_size':5.0, 'deposit_ratio':0.08, 'price_tick':5.0},
    {'symbol':'al', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':5.0},
    {'symbol':'sn', 'trade_size':1.0, 'deposit_ratio':0.07, 'price_tick':10.0},
    {'symbol':'SF', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':2.0},
    {'symbol':'SM', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':2.0},
    {'symbol':'ZC', 'trade_size':100.0, 'deposit_ratio':0.08, 'price_tick':0.2},
    {'symbol':'fu', 'trade_size':10.0, 'deposit_ratio':0.1, 'price_tick':1.0},
    {'symbol':'v', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':5.0},
    {'symbol':'bu', 'trade_size':10.0, 'deposit_ratio':0.08, 'price_tick':2.0},
    {'symbol':'a', 'trade_size':10.0, 'deposit_ratio':0.07, 'price_tick':1.0},
    {'symbol':'cs', 'trade_size':10.0, 'deposit_ratio':0.05, 'price_tick':1.0},
    {'symbol':'m', 'trade_size':10.0, 'deposit_ratio':0.07, 'price_tick':1.0},
    {'symbol':'y', 'trade_size':10.0, 'deposit_ratio':0.06, 'price_tick':2.0},
    {'symbol':'RS', 'trade_size':10, 'deposit_ratio':0.2, 'price_tick':1.0},
    {'symbol':'RM', 'trade_size':10.0, 'deposit_ratio':0.06, 'price_tick':1.0},
    {'symbol':'OI', 'trade_size':10.0, 'deposit_ratio':0.07, 'price_tick':1.0},
    {'symbol':'CY', 'trade_size':5.0, 'deposit_ratio':0.05, 'price_tick':5.0},
    {'symbol':'AP', 'trade_size':10.0, 'deposit_ratio':0.07, 'price_tick':1.0},
    {'symbol':'FG', 'trade_size':20.0, 'deposit_ratio':0.07, 'price_tick':1.0},
    {'symbol':'sp', 'trade_size':10.0, 'deposit_ratio':0.07, 'price_tick':2.0},
    {'symbol':'sc', 'trade_size':1000.0, 'deposit_ratio':0.1, 'price_tick':0.1},
    {'symbol':'l', 'trade_size':5.0, 'deposit_ratio':0.07, 'price_tick':5.0},
    {'symbol':'eg', 'trade_size':10.0, 'deposit_ratio':0.06, 'price_tick':1.0},
    {'symbol':'b', 'trade_size':10.0, 'deposit_ratio':0.05, 'price_tick':1.0}
   ]

for d in data:
    flt = {'symbol':d['symbol']}
    collection.update_one(flt, {'$set':d}, upsert=True)
