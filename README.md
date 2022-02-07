# vpsBatchRun
###VPS批量执行二进制程序
#####现有的功能
######1.批量执行二进制可执行文件 ！！！ 注意只支持二进制可执行文件
######2.收集日志到本机
######3.收集日志到oss
######4.打印所有机器执行日志

###使用方法:
######1.依赖安装
`pip install -r requirements.txt`
######2.执行
`python vpsBatchRun.py`

##使用须知:
######1. 根目录需放置 id_rsa 私钥文件用于登录ssh（vps要提前放置公钥才能登录）
######2. server.txt 文件为服务器IP 每行一个
######3. 根目录需要一个main目录下再创建不同可执行文件的目录（如./main/test/testRun） testRun所调用的文件也可以放在test目录中
######4. 日志输出的格式必须如 {test.log} 其中test为可执行文件名
######5. 如需收集日志到oss 需要配置config.ini中的oss设置
