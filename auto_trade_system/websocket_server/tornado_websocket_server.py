# -*-encoding:utf-8 -*-
from __future__ import print_function
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado import gen
from tornado.options import define, options, parse_command_line
from tornado.httpserver import HTTPServer
# import asyncio
import threading
import time
import datetime
import sys, locale
import json

define('port', default = 9001, help = 'run on the given port', type = int)

clients=dict()#客户端Session字典


class IndexHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        print("New connection request!")
        self.render("index.html")
        
class LoginHandler(tornado.web.RequestHandler):
    def post(self):
        name = self.get_body_argument('name', '').strip()
        password = self.get_body_argument('password', '').strip()
        if not name:
            raise tornado.web.HTTPError(400)

        self.set_secure_cookie('name', name)
        self.set_secure_cookie('password', password)

class MyWebSocketHandler(tornado.websocket.WebSocketHandler):

    def open(self, *args, **kwargs):
        """有新链接时被调用"""
        self.stream.set_nodelay(True)
        #self是客户端实例
        name = self.get_secure_cookie('name')
        password = self.get_secure_cookie('password')

        if not name:
            name = self.get_argument('name', id(self))
            password = self.get_argument('password', None)
        
        self.name = name

        if name in clients.keys():
            #如果用户存在则中断连接
            msg = '%s already sign in and old user will sign out!!!'%name
            print(msg)
            self.write_message(msg)
            old_user = clients[name]['object']
            old_user.name = 'old_%s'%old_user.name
            old_user.close()
        else:
            pass

        #保存Session到clients字典中
        clients[self.name]={"name":name,"object":self}
        print("New client connected and was given name %s" % self.name)
        #连接成功发送一个配置文件
        setting_file = './setting.json'
        f = file(setting_file)
        setting = json.load(f)
        setting = json.dumps(setting, indent=4)
        msg = '{"code": 888, "msg": "connected", "result": %s}'%setting
        self.write_message(msg)
        
    def on_message(self, message):
        """收到消息时被调用"""
        front_end = 'front_end'
        back_end = 'back_end'
        fail_message = '{"code": 404, "msg": "the other side is not connected","result": 0}'

        #不打印后端发送的具体信息
        if self.name == back_end:
            print("back_end send a message")
        else:
            print("Client %s send a message:%s"%(self.name,message))

        #将前端发送的数据返回给后端
        if self.name == front_end:
            if back_end in clients.keys():
                clients[back_end]['object'].write_message(message)
            else:
                clients[front_end]['object'].write_message(fail_message)

        #将后端发送的数据返回给前端
        if self.name == back_end:
            if front_end in clients.keys():
                clients[front_end]['object'].write_message(message)
            else:
                clients[back_end]['object'].write_message(fail_message)
    
        new_mesg = '%s:\n%s'%(self.name, message)
        for key in clients.keys():

            if key == front_end or key == back_end:
                continue

            clients[key]["object"].write_message(new_mesg)
            
    def on_close(self): 
        """关闭链接时被调用"""
        if self.name in clients.keys():
            del clients[self.name]
        
        print("Client %s is closed"%(self.name))

    def check_origin(self, origin):
        """解决跨域问题"""
        return True

# class SendThread(threading.Thread):

    # """启动单独的线程运行此函数，每隔1秒向所有的客户端推送当前时间"""
    # def run(self):
        # tornado 5 中引入asyncio.set_event_loop,不然会报错
        # asyncio.set_event_loop(asyncio.new_event_loop())
        # while True:
            # for key in clients.keys():
                # msg = str(datetime.datetime.now())
                # clients[key]["object"].write_message(msg)
                # print("write to client %s:%s" % (key, msg))
            # time.sleep(1)
            
class ChatApplication(tornado.web.Application):
    def __init__(self):
        handlers = [
                (r'/', IndexHandler),
                (r'/login', LoginHandler),
                (r'/webSocket', MyWebSocketHandler),
                ]

        settings = dict(
                cookie_secret = 'abc',
                template_path = 'template',
                static_path = 'static',
                debug = True,
                )

        tornado.web.Application.__init__(self, handlers, **settings)

if __name__ == '__main__':
    #启动推送时间线程
    # SendThread().start()
    parse_command_line()
    app = ChatApplication()
    http_server = HTTPServer(app)
    http_server.listen(options.port)
    # 挂起运行
    tornado.ioloop.IOLoop.instance().start()
    
    
    
    
    
