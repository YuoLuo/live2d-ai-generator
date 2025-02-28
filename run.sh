#!/bin/bash

# 设置环境变量以禁用OMP警告
export KMP_WARNINGS=off
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export NUMEXPR_NUM_THREADS=4

echo "正在安装基础依赖..."
# 安装基础依赖
pip install -U pip
# 注意：指定numpy版本为2.0.x，以满足numba的要求
pip install numpy==2.0.0 pillow torch torchvision --upgrade

echo "正在安装UI和网络依赖..."
# 安装UI和网络依赖
pip install gradio httpx requests fastapi uvicorn --upgrade

echo "正在安装图像处理依赖..."
# 安装图像处理依赖
pip install opencv-python scikit-image matplotlib --upgrade
# 安装rembg和相关依赖
pip install rembg numba==0.57.0 --upgrade

echo "正在安装AI和深度学习依赖..."
# 安装AI库
pip install transformers diffusers accelerate --upgrade

echo "正在安装其他依赖..."
# 安装其他必要依赖
pip install tqdm pyyaml python-dotenv --upgrade

echo "依赖安装完成，正在启动应用..."
echo "启动Live2D AI Generator图形界面..."

# 创建一个简单的监视脚本，确保程序保持运行
cat > run_with_monitor.py << EOL
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
EOL

# 运行监视脚本
python3 run_with_monitor.py "$@" 