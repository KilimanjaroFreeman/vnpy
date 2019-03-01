# encoding: UTF-8

"""
展示如何执行参数优化。
"""

from __future__ import division
from __future__ import print_function

from vnpy.trader.app.ctaStrategy.ctaBacktesting import BacktestingEngine, MINUTE_DB_NAME, OptimizationSetting
from vnpy.trader.app.ctaStrategy.ctaBase import loadContractDetail

import seaborn as sns
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import csv
import time


if __name__ == '__main__':
    from vnpy.trader.app.ctaStrategy.strategy.strategyMarketStable_IF_1min import MarketStableStrategy_IF_1min as opt_strategy
    
    #设置回测参数
    start_date = '20100501'          #回测起始日期
    end_date = '20150101'            #回测终止日期
    symbol = 'IF000'                 #回测合约
    slippage = 1                     #滑点为几个跳价
    rate = 0.3 / 10000               #手续费
    con_d = loadContractDetail(symbol)
    size = con_d['trade_size']       #合约大小
    price_tick = con_d['price_tick'] #最小价格变动
    
    #设置优化参数与优化目标
    setting = OptimizationSetting()                 # 新建一个优化任务设置对象
    setting.setOptimizeTarget('returnRiskRatio')    # 设置优化排序的目标是策略净盈利
    setting.addParameter('threshold', 0.01, 0.3, 0.01)        # 增加第二个优化参数atrMa，起始20，结束30，步进5
    setting.addParameter('loss_limit', 0.001, 0.01, 0.001)    # 增加第一个优化参数atrLength，起始12，结束20，步进2
    setting.addParameter('window', 30, 60, 5)    # 增加第一个优化参数atrLength，起始12，结束20，步进2
    setting.addParameter('volume_ratio', 1, 1.5, 0.1)    # 增加第一个优化参数atrLength，起始12，结束20，步进2
    setting.addParameter('sharp_ratio_threshold', 0.1, 0.3, 0.02)    # 增加第一个优化参数atrLength，起始12，结束20，步进2
    # setting.addParameter('std_num', 0.6, 2, 0.2)        # 增加第二个优化参数atrMa，起始20，结束30，步进5
    # setting.addParameter('rsiLength', 5)            # 增加一个固定数值的参数
    
    #--------------------------------------------------------------------------------------------------
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 设置引擎的回测模式为K线
    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate(start_date)
    engine.setEndDate(end_date)
    
    # 设置产品相关参数
    engine.setSlippage(slippage * price_tick)     # 滑点
    engine.setRate(rate)                          # 手续费
    engine.setSize(size)                          # 合约大小
    engine.setPriceTick(price_tick)               # 最小价格变动
    
    # 设置使用的历史数据库
    engine.setDatabase(MINUTE_DB_NAME, symbol)
    
    # 跑优化
    # 性能测试环境：I7-3770，主频3.4G, 8核心，内存16G，Windows 7 专业版
    # 测试时还跑着一堆其他的程序，性能仅供参考
    start = time.time()
    
    # 运行单进程优化函数，自动输出结果，耗时：359秒
    # result_list = engine.runOptimization(opt_strategy, setting)            
    
    # 多进程优化，耗时：89秒
    result_list = engine.runParallelOptimization(opt_strategy, setting)
    
    #保存结果
    file_name = opt_strategy.__name__ + '.csv'
    cols = ['parameter','optTarget'] + result_list[0][2].keys()
    s_data = pd.DataFrame(columns=cols)
    
    for r in result_list:
        new_r = dict({'parameter':r[0]}, **{'optTarget':r[1]})
        new_r = dict(new_r, **r[2])
        s_data = s_data.append(pd.Series(new_r), ignore_index=True)
        
    s_data.to_csv(file_name)
    
    #画热力图
    r1 = eval(result_list[0][0])
    keys = list(r1.keys())
    indexs = []
    for k in keys:
        d = []
        for res in result_list:
            dic = eval(res[0])
            d.append(dic[k])
        indexs.append(d)
    
    for i in range(len(keys)-1):
        for j in range(i+1, len(keys)):
            a = list(set(indexs[i]))
            b = list(set(indexs[j]))
            a.sort()
            b.sort()
            data = pd.DataFrame(np.zeros((len(a), len(b))), index=a, columns=b)
            for r in result_list:
                dic = eval(r[0])
                data.loc[dic[keys[i]], dic[keys[j]]] = float(r[1])
            
            f, ax = plt.subplots(figsize = (10, 4))
            cmap = sns.cubehelix_palette(start = 1, rot = 3, gamma=0.8, as_cmap = True)
            sns.heatmap(data, cmap = cmap, linewidths = 0.05, ax = ax)
            ax.set_title('Optimization')
            ax.set_ylabel(keys[i])
            ax.set_xlabel(keys[j])
    plt.show()
    print(u'耗时：%s' %(time.time()-start))