#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Live2D AI Generator 启动脚本
"""

import sys
import os
from pathlib import Path

# 确保可以导入main模块
root_dir = Path(__file__).parent.absolute()
sys.path.append(str(root_dir))

# 导入main模块
from main import main

if __name__ == "__main__":
    # 运行主函数
    sys.exit(main()) 