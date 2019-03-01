# -*- encoding: utf-8 -*-

import pandas as pd
import sys
import os
import json
from collections import OrderedDict
import datetime

class StrategySetting(object):
    """添加或者删除目前正在运行的策略"""
    def __init__(self, ahead_day=2):
        self.base_dir = '/home/freeman/Desktop'
        self.doc_dir = '/auto_trade_system/trade_accounts/'
        self.json_name = '/CTA_setting.json'
        self.ahead_day = ahead_day       #默认在每月的第3个星期五前两天换股指合约
    
    def add_strategy(self, account, setting):
        """给账户添加一个策略"""
        strategy_list = self._load_json(account)
        name = setting['name']
                
        try:
            alpha = ''.join([ x for x in setting['vtSymbol'] if x.isalpha()])
            setting['alpha'] = alpha
        except:
            print(u'传入参数错误!')
            return
        
        #如果要添加的策略已经存在，则覆盖旧策略
        strategy_list = self._delete_strategy(name, strategy_list)        
        strategy_list.append(setting)
        self._save_json(strategy_list, account)
        
    def delete_strategy(self, account, name):
        """删除账户正在运行的策略"""
        strategy_list = self._load_json(account)
        strategy_list = self._delete_strategy(name, strategy_list)
        self._save_json(strategy_list, account)
        
    def run_strategy(self, account, name):
        """如果策略状态为stop，则改为run，使策略正常运行"""
        strategy_list = self._load_json(account)
        
        #判断策略是否在配置文件中，如是，将status设为run
        for n, d in enumerate(strategy_list):
            if name == d['name']:
                strategy_list[n]['status'] = 'run'
        
        self._save_json(strategy_list, account)
        
    def stop_strategy(self, account, name):
        """如果策略状态为run，则改为stop，策略会平掉所有头寸，并停止运行"""
        strategy_list = self._load_json(account)
        
        #判断策略是否在配置文件中，如是，将status设为stop
        for n, d in enumerate(strategy_list):
            if name == d['name']:
                strategy_list[n]['status'] = 'stop'
        
        self._save_json(strategy_list, account)
        
    def get_account_strategy(self, account):
        """获取某一账户正在运行的策略名"""
        strategy_list = self._load_json(account)
        account_strategy = []
        
        for n, d in enumerate(strategy_list):
            account_strategy.append({
                                'name': d['name'],
                                'vtSymbol': d['vtSymbol'],
                                'status': d['status']
                                    })
            
        return pd.Series({account: account_strategy})
            
    def replace_account_contract(self, account, old_contract,
                                 new_contract, name=None):
        """更改主力合约"""
        strategy_list = self._load_json(account)
        
        #添加更改主力合约标记
        for n, d in enumerate(strategy_list):
            if name:
                if name == d['name']:
                    d['replaceContract'] = {'old_contract': old_contract,
                                           'new_contract': new_contract}
                else:
                    pass
            else:
                if d['vtSymbol'] == old_contract:
                    d['replaceContract'] = {'old_contract': old_contract,
                                           'new_contract': new_contract}
                else:
                    pass
                
        self._save_json(strategy_list, account)      
        
    def auto_replace_stock_index_contract(self, stock_futures=['IF']):
        """自动更改股指期货的主力合约，需要import到runCtaTrading中调用"""
        now = datetime.datetime.now()
        flag = False
        file_dir = r'./CTA_setting.json'
        strategy_list = self._load_json(file_dir=file_dir)
        
        for stock_future in stock_futures:
            new_contract = self.main_contract(now, stock_future)

            for n, d in enumerate(strategy_list):
                vs = d['vtSymbol']
                if vs[0:2] == stock_future and vs != new_contract:
                    d['replaceContract'] = {'old_contract': vs,
                                           'new_contract': new_contract}
                    print u'%s 主力合约由 %s 更换为 %s'%(strategy_names[i], 
                            vs, new_contract)
                    flag = True
        
        if flag:
            self._save_json(strategy_list, file_dir=file_dir) 
            
    def main_contract(self, date, stock_future = 'IF'):
        """给一个时间戳即可返回一个股指的主力合约号"""   
        #年份
        year = date.strftime('%Y')[-2: ]
        #月份
        month = date.strftime('%m')
        #日
        day = int(date.strftime('%d'))
        #星期
        week_num = int(date.strftime('%w'))
        
        #每月第3个星期5提前ahead_day更换主力合约
        
        ds = date.strftime('%Y%m') + '01'
        Friday = []
        for i in range(30):
            nd = datetime.datetime.strptime(ds, '%Y%m%d') + datetime.timedelta(days=i)
            if nd.strftime('%w') == '5':
                Friday.append(nd)
                
        ahead_date = Friday[2] - datetime.timedelta(days=self.ahead_day)
        
        if day >= int(ahead_date.strftime('%d')):
            new_date = ahead_date + datetime.timedelta(days=20)
            year = new_date.strftime('%Y')[-2: ]
            month = new_date.strftime('%m')
        
        contract = stock_future + year + month 
       
        return contract

    def _load_json(self, account=None, file_dir=None):
        """载入json配置文件"""
        if file_dir is None:
            file_dir = self.base_dir + self.doc_dir + account + self.json_name
            
        f = file(file_dir)
        strategy_list = json.load(f)
        
        return strategy_list
    
    def _delete_strategy(self, name, strategy_list):
        """删除list里包含name的dict"""
        for n, d in enumerate(strategy_list):
            if name == d['name']:
                del strategy_list[n]
                
        return strategy_list
      
    def _save_json(self, strategy_list, account=None, file_dir=None):
        """保存json文件"""
        if file_dir is None:
            file_dir = self.base_dir + self.doc_dir + account + self.json_name
            
        strategy_list = map(self._order_dict, strategy_list)
        
        with open(file_dir, 'w') as f:
            jsonL = json.dumps(strategy_list, indent=5)
            f.write(jsonL)
    
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
        
