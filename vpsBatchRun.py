#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File  : deploy.py.py
# @Author: Jason Ruan
# @Email : ruan4215@gmail.com
# @Date  : 10/21/21
# @Desc  :
import paramiko
import os
from threading import Thread
from terminal_layout.extensions.choice import *
from terminal_layout import *
import time
import sys
import logging
from datetime import datetime
import oss2
import platform
import configparser

sshDict = {}
transportDict = {}
resDict = {}
ossConfDict = {}

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
elif __file__:
    application_path = os.path.dirname(__file__)

if application_path == '':
    application_path = os.getcwd()

def asyncFunc(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper

def getServerIpList():
    if os.path.exists('{appPath}/server.txt'.format(appPath=application_path)) is not True:
        print('server.txt 不存在！请检查！脚本退出')
        time.sleep(9999)
        exit()

    ipList = []
    with open('{appPath}/server.txt'.format(appPath=application_path)) as lines:
        array = lines.readlines()
        for i in array:
            i = i.strip('\n')
            ipList.append(i)

    if len(ipList) == 0:
        print('服务器不能未空,请检查server.txt 脚本退出(每行一个服务器IP)')
        time.sleep(9999)
        exit()

    print('服务器IP:'+str(ipList))
    return ipList

def getssh(ip):
    try:
        if os.path.exists('{appPath}/id_rsa'.format(appPath=application_path)) is not True:
            print('id_rsa 私钥不存在！请检查！脚本退出')
            time.sleep(9999)
            exit()
        private_key = paramiko.RSAKey.from_private_key_file('{appPath}/id_rsa'.format(appPath=application_path))
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=ip, port=22, username="root", pkey=private_key)
        return ssh
    except Exception as e:
        print(str(e))
        return False

def getExecPath():
    res = os.listdir('{appPath}/main'.format(appPath=application_path))
    if len(res) == 0:
        print('错误,main文件夹下必须有一个可执行文件!')
        return False
    return '{appPath}/main/{execName}'.format(appPath=application_path,execName=execName)

def getUploadPath():
    return '/root/{execName}'.format(execName=execName)

def getExecName():
    return execName

def getOssUploadFilePath():
    return 'main/{execName}'.format(execName=execName)

def mkServerDir(ip):
    try:
        ssh = sshDict[ip]
        stdin, stdout, stderr = ssh.exec_command('mkdir {path}'.format(path=getUploadPath()))
        result = stdout.read()
        print('服务器IP:' + ip)
        print(result.decode())
        print('创建目录执行完毕')
    except Exception as e:
        print(str(e))

def delServerDir(ip):
    ssh = sshDict[ip]
    stdin, stdout, stderr = ssh.exec_command('rm -rf {path}'.format(path=getUploadPath()))
    print('rm -rf {path}'.format(path=getUploadPath()))
    result = stdout.read()
    print('服务器IP:' + ip)
    print(result.decode())
    print('删除目录执行完毕')

def getTransport(ip):
    try:
        private_key = paramiko.RSAKey.from_private_key_file("{appPath}/id_rsa".format(appPath=application_path))
        transport = paramiko.Transport((ip, 22))
        transport.connect(username="root", pkey=private_key)
        return transport
    except Exception as e:
        print(str(e))
        return False

def uploadFile(ip,transport,from_path,to_path):
    try:
        sftp = paramiko.SFTPClient.from_transport(transport)
        print(from_path)
        print(to_path)
        sftp.put(from_path,to_path)
        print('服务器 {ip} 文件已上传至:{path}'.format(ip=ip,path=to_path))
        return True
    except Exception as e:
        print(str(e))
    return True

def downloadFile(ip,transport,from_path,to_path):
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.get(from_path, to_path)
    print('服务器 {ip} 的文件 {from_path} 已下载至:{path}'.format(ip=ip,from_path=from_path, path=to_path))
    return True

def stopProcess(ip):
    killCommand = "ps -ef | grep {exec} | grep -v grep | awk '{{print $2}}' | xargs kill -9".format(exec=getExecName())
    print(killCommand)
    ssh = sshDict[ip]
    stdin, stdout, stderr = ssh.exec_command('{command}'.format(command=killCommand))
    result = stdout.read()
    print('服务器IP:' + ip)
    print(result.decode())
    print('执行杀死进程成功')

@asyncFunc
def stopDelAsync(ip):
    if ip not in sshDict:
        ssh = getssh(ip)
        if ssh:
            sshDict[ip] = ssh
        else:
            print(ip+' ssh获取失败')
            return False
    stopProcess(ip)
    delServerDir(ip)


@asyncFunc
def runAsync(ssh,ip):
    execPath = getUploadPath()
    print('\r\n开始执行运行脚本命令:')
    runCommand = 'cd {cdPath} && chmod +x {path}/{execName}\nnohup {path}/{execName} > run.log 2>&1'.format(cdPath=getUploadPath(), path=execPath,execName=execName)
    print(runCommand)
    ssh.exec_command(runCommand, get_pty=True)
    tailCommand = 'tail -f {path}/run.log'.format(path=execPath)
    stdin, stdout, stderr = ssh.exec_command(tailCommand,get_pty=True)
    while not stdout.channel.exit_status_ready():
        result = stdout.readline()
        msg1 = ip + ':' + result
        print(msg1)
        logging.info(msg1)
        # 由于在退出时，stdout还是会有一次输出，因此需要单独处理，处理完之后，就可以跳出了
        if stdout.channel.exit_status_ready():
            msg2 = stdout.readlines()
            print(msg2)
            logging.info(msg2)
            break
    print('服务器IP:' + ip + '执行成功')

def uploadConf(ip):
    print('开始上传配置文件')
    execName = getExecName()
    confList = os.listdir('{appPath}/conf/{execName}'.format(execName=execName,appPath=application_path))
    newList = []
    for f in confList:
        if '.csv' in f:
            newList.append(f)

    if len(newList) == 0:
        print('错误,文件夹 conf/{path} 下必须至少有一个配置文件 脚本退出'.format(path=execName))
        time.sleep(9999)
        exit()

    curFileIndex = list(sshDict.keys()).index(ip)
    curFile = newList[curFileIndex]
    fullConfPath = '{appPath}/conf/{execName}/{confPath}'.format(appPath=application_path,execName=execName,confPath=curFile)
    toFilePath = '{execPath}/{confPath}'.format(execPath=getUploadPath(),confPath=curFile)
    uploadFile(ip, transportDict[ip], fullConfPath, toFilePath)

@asyncFunc
def downloadExecAndRun(ip):
    urlDict = getExecDownloadUrl()
    print('开始下载执行目录')
    zipName = '{execName}.zip'.format(
        execName=getExecName(),
    )
    downloadCommand = "wget {url} -O {path} && cd {runPath} && unzip {zipName}".format(
        url=urlDict['url'],
        path=getUploadPath()+'/'+urlDict['name'],
        runPath=getUploadPath(),
        zipName=zipName
    )

    execCommand(ip,sshDict[ip],downloadCommand)
    ssh = sshDict[ip]
    runAsync(ssh,ip)

def execCommand(ip,ssh,command):
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
    while not stdout.channel.exit_status_ready():
        result = stdout.readline()
        print('服务器IP:' + ip)
        print(result)

@asyncFunc
def fetchLogAndConfAsynctoLocal(ip):
    if ip not in sshDict:
        ssh = getssh(ip)
        if ssh:
            sshDict[ip] = ssh
        else:
            print(ip+' ssh获取失败')
            return False

    if ip not in transportDict:
        transport = getTransport(ip)
        if transport:
            transportDict[ip] = transport
        else:
            print(ip + ' 传输隧道获取失败')
            return False
    cssh = sshDict[ip]
    transport = transportDict[ip]
    logPath = getUploadPath()
    stdin, stdout, stderr = cssh.exec_command('cd {path} && find ./*.csv'.format(path=logPath))
    result = stdout.read()
    print('获取配置文件 服务器IP:' + ip + ' 返回信息:\r\n' + result.decode())
    confNameRes = result.decode().replace('\n', '')
    if confNameRes != '':
        confName = confNameRes.replace('./', '')
        confRealPath = "{serverPath}/{confName}".format(confName=confName, serverPath=getUploadPath())
        confPath = "{appPath}/log/{execName}/{ip}/{fileName}".format(appPath=application_path,
                                                                     execName=getExecName(), ip=ip,
                                                                     fileName=confName)
        path = "{appPath}/log/{execName}/{ip}".format(appPath=application_path, execName=getExecName(),
                                                      ip=ip)
        if not os.path.exists(path):
            os.makedirs(path)
        downloadFile(ip, transport, confRealPath, confPath)

    stdin, stdout, stderr = cssh.exec_command('cd {path} && find ./run.log'.format(path=logPath))
    result = stdout.read()
    print('获取运行输出日志 服务器IP:' + ip + ' 返回信息:\r\n' + result.decode())
    runlogRes = result.decode().replace('\n', '')
    if runlogRes != '':
        logName = runlogRes.replace('./', '')
        logRealPath = "{serverPath}/{logName}".format(logName=logName, serverPath=getUploadPath())
        toPath = "{appPath}/log/{execName}/{ip}/{fileName}".format(appPath=application_path,
                                                                     execName=getExecName(), ip=ip,
                                                                     fileName=logName)
        path = "{appPath}/log/{execName}/{ip}".format(appPath=application_path, execName=getExecName(),
                                                      ip=ip)
        if not os.path.exists(path):
            os.makedirs(path)
        downloadFile(ip, transport, logRealPath, toPath)

    print(logPath)
    stdin, stdout, stderr = cssh.exec_command('cd {path} && find ./{execName}.log'.format(execName=getExecName(),path=logPath))
    result = stdout.read()
    print('获取日志文件 服务器IP:' + ip + ' 返回信息:\r\n' + result.decode())
    logNameRes = result.decode().replace('\n', '')
    if logNameRes != '':
        logName = logNameRes.replace('./', '')
        logRealPath = "{serverPath}/{confName}".format(confName=logName, serverPath=getUploadPath())
        downloadLogPath = "{appPath}/log/{execName}/{ip}/{fileName}".format(appPath=application_path,
                                                                            execName=getExecName(), ip=ip,
                                                                            fileName=logName)
        path = "{appPath}/log/{execName}/{ip}".format(appPath=application_path, execName=getExecName(),
                                                      ip=ip)
        if not os.path.exists(path):
            os.makedirs(path)
        downloadFile(ip, transport, logRealPath, downloadLogPath)

@asyncFunc
def fetchLogAndConfAsynctoOss(ip):
    if ip not in sshDict:
        ssh = getssh(ip)
        if ssh:
            sshDict[ip] = ssh
        else:
            print(ip+' ssh获取失败')
            return False
    logPath = getUploadPath()
    cssh = sshDict[ip]
    print('cd {path} && find ./*.csv'.format(path=logPath))
    stdin, stdout, stderr = cssh.exec_command('cd {path} && find ./*.csv'.format(path=logPath))
    result = stdout.read()
    print('获取配置文件 服务器IP:' + ip + ' 返回信息:\r\n' + result.decode())
    confNameRes = result.decode().replace('\n', '')
    dt = datetime.now()
    if confNameRes != '':
        confName = confNameRes.replace('./', '')
        confRealPath = "{serverPath}/{confName}".format(confName=confName, serverPath=getUploadPath())
        ossPath = "log/{execName}/{date}/{ip}/{fileName}".format(
            date=dt.strftime('%Y-%m-%d'),
            execName=getExecName(), ip=ip,
            fileName=confName
        )
        uploadFileToOssByUrl(ossPath, ip, confRealPath)

    stdin, stdout, stderr = cssh.exec_command('cd {path} && find ./run.log'.format(path=logPath))
    result = stdout.read()
    print('获取运行输出日志 服务器IP:' + ip + ' 返回信息:\r\n' + result.decode())
    runlogRes = result.decode().replace('\n', '')
    if runlogRes != '':
        runlogName = runlogRes.replace('./', '')
        logRealPath = "{serverPath}/{logName}".format(logName=runlogName, serverPath=getUploadPath())
        ossPath = "log/{execName}/{date}/{ip}/{fileName}".format(
            date=dt.strftime('%Y-%m-%d'),
            execName=getExecName(), ip=ip,
            fileName=runlogName
        )
        uploadFileToOssByUrl(ossPath, ip, logRealPath)

    stdin, stdout, stderr = cssh.exec_command('cd {path} && find ./{execName}.log'.format(execName=getExecName(),path=logPath))
    result = stdout.read()
    print('获取日志文件 服务器IP:' + ip + ' 返回信息:\r\n' + result.decode())
    logNameRes = result.decode().replace('\n', '')
    if logNameRes != '':
        logName = logNameRes.replace('./', '')
        logRealPath = "{serverPath}/{confName}".format(confName=logName, serverPath=getUploadPath())
        ossPath = "log/{execName}/{date}/{ip}/{fileName}".format(
            date= dt.strftime('%Y-%m-%d'),
            execName=getExecName(), ip=ip,
            fileName=logName
        )
        uploadFileToOssByUrl(ossPath,ip,logRealPath)

def uploadFileToOssByUrl(ossPath,ip,serverFilePath):
    ossBucket = getOssBucket()
    signedUrl = ossBucket.sign_url('PUT', ossPath, 60 * 60)

    command = "curl -X PUT -H 'Content-Type:' --data-binary '@{serverFilePath}' '{url}'".format(
        url=signedUrl,
        serverFilePath=serverFilePath
    )
    print(command)
    execCommand(ip, sshDict[ip], command)
    return True

@asyncFunc
def execAsync(ip,command):
    if ip not in sshDict:
        ssh = getssh(ip)
        if ssh:
            sshDict[ip] = ssh
        else:
            print(ip+' ssh获取失败')
            return False
    ssh = sshDict[ip]
    execCommand(ip,ssh, command)
    print('执行成功')

def getOssBucket():
    auth = oss2.Auth(ossConfDict['accessKeyId'], ossConfDict['accessKeySecret'])
    ossBucket = oss2.Bucket(auth, ossConfDict['endpoint'], ossConfDict['bucketName'])
    return ossBucket

def putExecFileToOss():
    resDict['ossUploadStart'] = True
    print('上传执行文件至oss')
    ossBucket = getOssBucket()
    target = getOssUploadFilePath()
    source = getExecPath()
    print(source)

    execZip = '{path}/{execName}.zip'.format(
        execName=getExecName(),
        path=source
    )

    if os.path.isfile(execZip):
        os.remove(execZip)

    if 'windows' in platform.platform().lower():
        os.system('cd {path} && {curRoot}/zip -q -r {execName}.zip ./'.format(
            execName=getExecName(),
            path=source,
            curRoot=application_path
        ))
    else:
        os.system('cd {path} && zip -q -r {execName}.zip ./'.format(
            execName=getExecName(),
            path=source
        ))

    zipName = '{execName}.zip'.format(
        execName=getExecName(),
    )
    ossBucket.put_object_from_file(target + '/' + zipName, execZip)
    resDict['ossUploadOver'] = True
    return True

def getExecDownloadUrl():
    ossBucket = getOssBucket()
    target = getOssUploadFilePath()
    urlDict = {}

    zipName = '{execName}.zip'.format(
        execName=getExecName(),
    )

    fileName = target + '/' + zipName
    urlDict['url'] = '"'+ossBucket.sign_url('GET', fileName, 60 * 60)+'"'
    urlDict['name'] = zipName
    return urlDict

@asyncFunc
def runExecAsync(ip):
    if ip not in sshDict:
        ssh = getssh(ip)
        if ssh:
            sshDict[ip] = ssh
        else:
            print(ip+' ssh获取失败')
            return False

    stopProcess(ip)
    delServerDir(ip)
    mkServerDir(ip)
    if ip not in transportDict:
        transport = getTransport(ip)
        if transport:
            transportDict[ip] = transport
        else:
            print(ip + ' 传输隧道获取失败')
            return False
    uploadConf(ip)
    if 'ossUploadStart' not in resDict:
        putExecFileToOss()
    while 'ossUploadOver' not in resDict:
        time.sleep(1)
    downloadExecAndRun(ip)

def getConfigFile():
    config_name = 'config.ini'
    config_path = os.path.join(application_path, config_name)
    if not os.path.exists(config_path):
        print('配置文件不存在,请检查')
        time.sleep(9999)
        exit()
    return config_path

if __name__ == "__main__":
    conf = configparser.ConfigParser()
    conf.read(getConfigFile(), encoding='utf-8')
    ossConfDict['accessKeyId'] = conf.get('config', 'access_key_id')
    ossConfDict['accessKeySecret'] = conf.get('config', 'access_key_secret')
    ossConfDict['endpoint'] = conf.get('config', 'endpoint')
    ossConfDict['bucketName'] = conf.get('config', 'bucket_name')

    if os.path.exists('{appPath}/main'.format(appPath=application_path)) is not True:
        print('main文件夹不存在!脚本退出')
        time.sleep(9999)
        exit()

    execList = os.listdir('{appPath}/main'.format(appPath=application_path))
    execList.insert(0,'更新全部脚本')
    if '.DS_Store' in execList:
        execList.remove('.DS_Store')
    if len(execList) == 0:
        print('main文件夹下至少需要一个可执行文件!脚本退出')
        time.sleep(9999)
        exit()
    c = Choice('请选择想要执行的脚本:',
               execList,
               icon_style=StringStyle(fore=Fore.blue),
               selected_style=StringStyle(fore=Fore.blue))

    choice = c.get_choice()

    if choice:
        index, value = choice
        if value == '更新全部脚本':
            os.system('cd {path} && git pull'.format(path=application_path))
            input('更新已完成....按下任意键退出')
            exit()
        else:
            execName = value
            LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
            dt = datetime.now()
            logPath = "{appPath}/runLog".format(appPath=application_path)
            if not os.path.exists(logPath):
                os.makedirs(logPath)
            fh = logging.FileHandler(encoding='utf-8', mode='a', filename='{appPath}/runLog/{execName}-{date}.log'.format(appPath=application_path,execName=execName,date=dt.strftime('%Y-%m-%d')))
            logging.basicConfig(handlers=[fh], level=logging.INFO, format=LOG_FORMAT)

    c = Choice('请选择需要执行的操作:',
               ['服务器批量执行脚本','批量执行命令','服务器批量停止脚本','获取服务配置文件与日志至OSS','获取服务配置文件与日志至本地'],
               icon_style=StringStyle(fore=Fore.blue),
               selected_style=StringStyle(fore=Fore.blue))

    choice2 = c.get_choice()
    if choice2:
        index, runValue = choice2


    serverIp = getServerIpList()
    if runValue == '服务器批量执行脚本':
        for ip in serverIp:
            runExecAsync(ip)
        time.sleep(9999)

    elif runValue == '服务器批量停止脚本':
        for ip in serverIp:
            stopDelAsync(ip)

    elif runValue == '获取服务配置文件与日志至OSS':
        for ip in serverIp:
            fetchLogAndConfAsynctoOss(ip)
        print('服务器全部日志获取已完成')

    elif runValue == '获取服务配置文件与日志至本地':
        for ip in serverIp:
            fetchLogAndConfAsynctoLocal(ip)
        print('服务器全部日志获取已完成')

    elif runValue == '批量执行命令':
        command = input('请输入需要批量执行的命令:')
        for ip in serverIp:
            execAsync(ip,command)
        print('批量命令执行完成')
    input('脚本已停止执行....按下任意键退出')
