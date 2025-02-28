import sys
import subprocess
import time
import os
import signal

def signal_handler(sig, frame):
    print("\n程序被用户中断，正在清理...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("正在启动Live2D AI Generator...")
try:
    # 直接在前台运行，捕获所有输出
    process = subprocess.Popen(
        ["python3", "gui_run.py"] + sys.argv[1:],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # 实时显示输出
    for line in process.stdout:
        print(line, end='')
    
    # 等待进程结束并获取返回码
    return_code = process.wait()
    
    if return_code != 0:
        print(f"程序异常退出，错误码: {return_code}")
        sys.exit(return_code)
    
except Exception as e:
    print(f"启动过程中发生错误: {e}")
    sys.exit(1)

# 保持脚本运行，防止Gradio后台进程被终止
print("服务已启动，按Ctrl+C停止...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n用户中断，正在停止服务...")
