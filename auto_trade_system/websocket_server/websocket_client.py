# -*- encoding: utf-8 -*-

from websocket import create_connection, WebSocketConnectionClosedException
import pandas as pd
import sys
import json
import socket
import os
import time
import multiprocessing

lib_path = '/home/freeman/Desktop/auto_trade_system/lib/'
sys.path.append(lib_path)
from ats_base import StrategyDBProcessor
from add_and_delete_strategy import StrategySetting


class WebsockClient():
    """客户端"""
    def __init__(self, url):
        self.base_dir = '/home/freeman/Desktop/auto_trade_system/'
        self.url = url + '?name=back_end&password=123456'
        self.ws = create_connection(self.url)
        self.db_processor = StrategyDBProcessor()
        self.ss = StrategySetting()
    
    #-------------------------------------------------------------
    def run_client(self):
        """运行客户端"""
        #两个进程运行前端发送过来的信号和定时发送策略信息
        
        p_1 = None
        p_2 = None
        while True:
            running_time = True
            #处理前端发送来的信号的进程
            if running_time and p_1 is None:
                p_1 = multiprocessing.Process(target=self.run_accept_command)
                p_1.start()
                print(u'开启信号处理进程')
                
            #定时发送策略信息的进程
            if running_time and p_2 is None:
                p_2 = multiprocessing.Process(target=self.run_send_strategys_information)
                p_2.start()
                print(u'开启定时发送策略信息进程')
            
            if not running_time and (p_1 is not None or p_2 is not None):
                p_1.terminate()
                p_1.join()
                P_1 = None
                print(u'关闭信号处理进程')
                
                p_2.terminate()
                p_2.join()
                P_2 = None
                print(u'关闭定时发送策略信息进程') 
            
            time.sleep(60)
        
    #-----------------------------------------------------
    def run_accept_command(self):
        """等待前端发送命令并处理"""

        while True:
            #等待信息传输
            try:
                command = self.ws.recv()
                command = command.strip()
                print(u'收到信息：{}'.format(command))
                
                if not command:
                    continue
                    
                #判断是否为命令信息
                if command[0] == '{' and command[-1] == '}':
                    #字符串转化为字典
                    command = eval(command)
                    if 'command' in command.keys():
                        #受到指令，作相应操作
                        self.run_command(command)
                else:
                    pass
            except WebSocketConnectionClosedException:
                 self._connect_server()
                
    #--------------------------------------------
    def run_command(self, command):
        """处理前端传过来的命令"""
        #添加策略
        if command['command'] == 'add_strategy':
            args = self._get_param(command, 'account', 'setting')
           
            if args:
                account = args[0]
                setting = args[1]
                self.ss.add_strategy(account, setting)
                self._send_message(None, code_type=1)
            else:
                self._send_message(None, code_type=-1)    
                
        #删除策略    
        elif command['command'] == 'delete_strategy':
            args = self._get_param(command, 'account', 'name')
            
            if args:
                account = args[0]
                name = args[1]
                self.ss.delete_strategy(account, name)
                self._send_message(None, code_type=1)
            else:
                self._send_message(None, code_type=-1)  
                
        #将状态为stop的策略改为为run
        elif command['command'] == 'run_strategy':
            args = self._get_param(command, 'account', 'name')
            
            if args:
                account = args[0]
                name = args[1]
                self.ss.run_strategy(account, name)
                self._send_message(None, code_type=1)
            else:
                self._send_message(None, code_type=-1)  
                
        #将状态为run的策略改为为stop
        elif command['command'] == 'stop_strategy':
            args = self._get_param(command, 'account', 'name')
            
            if args:
                account = args[0]
                name = args[1]
                self.ss.stop_strategy(account, name)
                self._send_message(None, code_type=1)
            else:
                self._send_message(None, code_type=-1)
                
        #更改主力合约
        elif command['command'] == 'replace_account_contract':
            args = self._get_param(command, 'account', 'old_contract',
                                   'new_contract')
            
            if args:
                account = args[0]
                old_contract = args[1]
                new_contract = args[2]
                self.ss.replace_account_contract(account, old_contract,
                                                 new_contract)
                self._send_message(None, code_type=1)
            else:
                self._send_message(None, code_type=-1)
                
        #获取某一账户正在运行的策略名
        elif command['command'] == 'get_account_strategy':
            args = self._get_param(command, 'account')
            
            if args:
                account = args[0]
                strategy = self.ss.get_account_strategy(account)
                self._send_message(strategy, code_type=2)
            else:
                self._send_message(None, code_type=-1)
        
        #获统计一段时间策略的交易表现
        elif command['command'] == 'get_trade_result':
            args = self._get_param(command, 'name', 'start_date',
                                   'end_date')
            
            if args:
                name = args[0]
                start_date = args[1]
                end_date = args[2]
                trade_result = self.db_processor.get_trade_result(name,
                                                                  start_date,
                                                                  end_date)
                self._send_message(trade_result, code_type=3)
            else:
                self._send_message(None, code_type=-1)
                
        #获取策略在一段时间内的账户详情
        elif command['command'] == 'get_strategy_information':
            args = self._get_param(command, 'name', 'start_date',
                                   'end_date')
            
            if args:
                name = args[0]
                start_date = args[1]
                end_date = args[2]
                strategy_infor = self.db_processor.get_strategy_information(name,
                                                                           start_date,
                                                                           end_date)
                self._send_message(strategy_infor, code_type=4)
            else:
                self._send_message(None, code_type=-1) 
        
        #无效命令
        else:
            self._send_message(None, code_type=-1)
         
    #----------------------------------------------------------------------------
    def run_send_strategys_information(self):
        """每隔一分钟自动向前端发送所有配置文件的策略在当日的信息"""
        today = pd.Timestamp.now().strftime('%Y%m%d')
        
        while True:
            strategy_names = self._get_all_strategy_name()
            all_data = {}
            
            for account in strategy_names:
                data = []
                for name in strategy_names[account]:
                    d = self.db_processor.get_strategy_information(name, today)
                    d = self._dataframe_to_dict(d)
                    data.append(d)
                    
                all_data[account] = data  
            try:
                self._send_message(all_data, code_type=0)
                print("{}: Strategys information send!".format(
                            pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')))
            except socket.error:
                 self._connect_server()
                
            time.sleep(60)
                
    #-----------------------------------------------------------------------------
    def _connect_server(self):
        """重新连接服务器"""
        try:
            self.ws = create_connection(self.url)
            print(u'重新连接服务器成功！')
        except:
            print(u'重新连接服务器失败，10秒后重试！')
            time.sleep(10)
            
    #-----------------------------------------------------------------------------
    def _get_all_strategy_name(self):
        """读取所有账户配置文件内的策略名"""
        s_dir = self.base_dir + 'trade_accounts'
        account_names = os.listdir(s_dir)
        strategy_names = {}
        
        for account in account_names:
            sn = self.ss.get_account_strategy(account)
            names = []
            for s in sn[account]:
                names.append(s['name'])
                
            if names:
                strategy_names[account] = names
                
        return strategy_names
    
    #----------------------------------------------------------------------------
    def _get_param(self, x, *args):
        """获取命令中的参数"""
        try:
            n = [x['params'][arg] for arg in args]
        except:
            print('传入参数错误')
            return []
        
        return n
    
    #-----------------------------------------------
    def _dataframe_to_dict(self, data):
        """dataframe转化为dict"""
        data = data.reset_index()
        data = data.astype('str')
        new_data = {}

        for k in data.columns:
            new_data[k] = list(data[k].values)
            
        return new_data
                                 
    #---------------------------------------------------
    def _send_message(self, data, code_type):
        """将数据转化为json形式的字符再发送"""
        #有返回命令
        if code_type > 1:
            if isinstance(data, pd.DataFrame):
                data = self._dataframe_to_dict(data)
            else:
                data = data.astype('str')
                data = dict(data)
            
            new_data = {'code': code_type,'msg': u'正常返回', 'result': data}
        #无返回命令
        elif code_type == 1:
            new_data = {'code': 1,'msg': u'运行成功', 'result': 0}
        #无效命令
        elif code_type == -1:
            new_data = {'code': -1,'msg': u'无效命令', 'result': 0}
        elif code_type == 0:
            new_data = {'code': 0,'msg': u'策略分时数据', 'result': data}   
        new_data = json.dumps(new_data, indent=5)
        self.ws.send(new_data)
        

######################################################################
if __name__ == '__main__':
    url = 'ws://192.168.10.214:9001/webSocket'
    wc = WebsockClient(url)
    wc.run_client()
    #wc.run_accept_command()
    # wc.run_send_strategys_information()
