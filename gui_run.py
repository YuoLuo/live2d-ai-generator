#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI启动脚本 - 启动Live2D AI Generator的图形用户界面
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
root_dir = str(Path(__file__).absolute().parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 导入GUI模块
from modules.gui import launch_gui

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="启动Live2D AI Generator的图形用户界面")
    parser.add_argument("--config", type=str, default="config.yml", help="配置文件路径")
    parser.add_argument("--share", action="store_true", help="创建公开可访问的链接")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--port", type=int, default=7860, help="服务器端口")
    
    args = parser.parse_args()
    
    print("启动Live2D AI Generator图形界面...")
    
    # 检查Gradio是否已安装
    try:
        import gradio
    except ImportError:
        print("错误: Gradio库未安装，正在尝试安装...")
        try:
            import pip
            pip.main(['install', 'gradio'])
            print("Gradio安装成功！")
        except Exception as e:
            print(f"安装Gradio失败: {str(e)}")
            print("请手动安装Gradio: pip install gradio")
            sys.exit(1)
    
    # 启动GUI
    try:
        launch_gui(
            config_path=args.config,
            share=args.share,
            inbrowser=not args.no_browser,
            server_port=args.port
        )
    except Exception as e:
        print(f"启动GUI时出现错误: {str(e)}")
        import traceback
        traceback.print_exc() 