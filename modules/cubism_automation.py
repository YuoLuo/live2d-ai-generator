#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cubism自动化模块 - 自动操作Live2D Cubism软件，进行模型创建
"""

import os
import logging
import time
import subprocess
import platform
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import shutil

import pyautogui
from pynput import keyboard, mouse
import cv2
import numpy as np
from PIL import Image, ImageGrab

logger = logging.getLogger("live2d_generator.cubism_automation")

class CubismAutomation:
    """Cubism自动化类，负责与Live2D Cubism软件交互"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Cubism自动化类
        
        Args:
            config: 配置字典，包含Cubism自动化的相关设置
        """
        self.config = config
        self.cubism_config = config['cubism']
        self.output_dir = os.path.join(config['export']['output_dir'], 'model')
        self.temp_dir = config['misc']['temp_dir']
        
        # Cubism可执行文件路径
        self.exe_path = self.cubism_config['executable_path']
        
        # 检查可执行文件路径
        if not os.path.exists(self.exe_path) and platform.system() == "Darwin":
            # macOS上的默认路径
            default_paths = [
                "/Applications/Live2D Cubism 4.1/Cubism.app/Contents/MacOS/Cubism",
                "/Applications/Live2D Cubism 4.0/Cubism.app/Contents/MacOS/Cubism"
            ]
            for path in default_paths:
                if os.path.exists(path):
                    self.exe_path = path
                    break
        
        # 自动化方法
        self.automation_method = self.cubism_config['automation_method']
        
        # 确保输出目录存在
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # UI控制设置
        pyautogui.PAUSE = 0.5  # 操作间隔时间
        pyautogui.FAILSAFE = True  # 启用故障保护
        
        # 常用UI元素的图像模板
        self.templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        if not os.path.exists(self.templates_dir):
            # 如果模板目录不存在，则创建并添加示例模板
            Path(self.templates_dir).mkdir(parents=True, exist_ok=True)
            logger.warning(f"模板目录不存在，已创建: {self.templates_dir}")
            logger.warning("请将Cubism UI元素的截图添加到此目录")
        
        # 缓存的窗口信息
        self.window_info = None
    
    def _start_cubism(self) -> bool:
        """启动Cubism软件
        
        Returns:
            是否成功启动
        """
        logger.info("启动Live2D Cubism软件...")
        
        try:
            # 检查Cubism是否已经在运行
            if self._is_cubism_running():
                logger.info("Cubism已经在运行")
                return True
            
            # 启动Cubism
            if platform.system() == "Windows":
                subprocess.Popen([self.exe_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", self.exe_path])
            else:
                logger.error(f"不支持的操作系统: {platform.system()}")
                return False
            
            # 等待软件启动
            for _ in range(30):  # 最多等待30秒
                time.sleep(1)
                if self._is_cubism_running():
                    break
            
            # 等待启动画面消失
            time.sleep(5)
            
            # 激活窗口
            self._activate_cubism_window()
            
            # 等待窗口完全加载
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"启动Cubism时出错: {str(e)}")
            return False
    
    def _is_cubism_running(self) -> bool:
        """检查Cubism是否正在运行
        
        Returns:
            是否正在运行
        """
        # 通过查找窗口来检查软件是否在运行
        if platform.system() == "Windows":
            # Windows实现
            try:
                import win32gui
                windows = []
                win32gui.EnumWindows(lambda hwnd, windows: windows.append((hwnd, win32gui.GetWindowText(hwnd))), windows)
                for hwnd, title in windows:
                    if "Cubism" in title and win32gui.IsWindowVisible(hwnd):
                        return True
                return False
            except ImportError:
                logger.warning("未安装win32gui，无法检查Cubism是否运行")
                return True  # 假设正在运行
                
        elif platform.system() == "Darwin":  # macOS
            try:
                output = subprocess.check_output(["ps", "-A"]).decode("utf-8")
                return "Cubism" in output
            except Exception:
                return False
                
        else:
            logger.warning(f"不支持的操作系统: {platform.system()}")
            return False
    
    def _activate_cubism_window(self) -> bool:
        """激活Cubism窗口
        
        Returns:
            是否成功激活
        """
        logger.info("激活Cubism窗口...")
        
        try:
            if platform.system() == "Windows":
                # Windows实现
                try:
                    import win32gui
                    import win32con
                    
                    def callback(hwnd, windows):
                        if win32gui.IsWindowVisible(hwnd) and "Cubism" in win32gui.GetWindowText(hwnd):
                            windows.append(hwnd)
                    
                    windows = []
                    win32gui.EnumWindows(callback, windows)
                    
                    if windows:
                        hwnd = windows[0]
                        # 激活窗口
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        
                        # 保存窗口信息
                        rect = win32gui.GetWindowRect(hwnd)
                        self.window_info = {
                            "hwnd": hwnd,
                            "rect": rect,
                            "left": rect[0],
                            "top": rect[1],
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1]
                        }
                        
                        return True
                    return False
                    
                except ImportError:
                    logger.warning("未安装win32gui，使用pyautogui代替")
                    # 使用pyautogui查找窗口
                    window = pyautogui.getWindowsWithTitle("Cubism")
                    if window:
                        window[0].activate()
                        return True
                    return False
                    
            elif platform.system() == "Darwin":  # macOS
                try:
                    subprocess.run(["osascript", "-e", 'tell application "Cubism" to activate'], check=True)
                    # 在macOS上无法直接获取窗口位置，使用全屏操作
                    self.window_info = {
                        "left": 0,
                        "top": 0,
                        "width": pyautogui.size()[0],
                        "height": pyautogui.size()[1]
                    }
                    return True
                except Exception as e:
                    logger.error(f"激活Cubism窗口失败: {str(e)}")
                    return False
                    
            else:
                logger.warning(f"不支持的操作系统: {platform.system()}")
                return False
                
        except Exception as e:
            logger.error(f"激活Cubism窗口时出错: {str(e)}")
            return False
    
    def _find_ui_element(self, template_name: str, confidence: float = 0.8, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Tuple[int, int]]:
        """在屏幕上查找UI元素
        
        Args:
            template_name: 模板图像名称
            confidence: 匹配置信度
            region: 搜索区域 (left, top, width, height)
            
        Returns:
            元素的中心坐标，如果未找到则返回None
        """
        # 模板路径
        template_path = os.path.join(self.templates_dir, f"{template_name}.png")
        
        if not os.path.exists(template_path):
            logger.warning(f"模板文件不存在: {template_path}")
            return None
        
        try:
            # 捕获屏幕
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            # 转换为OpenCV格式
            screenshot = np.array(screenshot)
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            
            # 加载模板
            template = cv2.imread(template_path)
            
            # 执行模板匹配
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= confidence:
                # 计算中心坐标
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                
                # 如果使用了region，需要调整坐标
                if region:
                    center_x += region[0]
                    center_y += region[1]
                
                return (center_x, center_y)
            
            return None
            
        except Exception as e:
            logger.error(f"查找UI元素时出错: {str(e)}")
            return None
    
    def _import_psd(self, psd_path: str) -> bool:
        """导入PSD文件
        
        Args:
            psd_path: PSD文件路径
            
        Returns:
            是否成功导入
        """
        logger.info(f"导入PSD文件: {psd_path}")
        
        try:
            # 确保PSD文件存在
            if not os.path.exists(psd_path):
                logger.error(f"PSD文件不存在: {psd_path}")
                return False
            
            # 使用Cubism的File -> Import -> PSD菜单
            # 按下Alt键显示菜单
            pyautogui.hotkey('alt')
            time.sleep(0.5)
            
            # 点击File菜单
            pyautogui.press('f')
            time.sleep(0.5)
            
            # 点击Import子菜单
            pyautogui.press('i')
            time.sleep(0.5)
            
            # 点击PSD选项
            pyautogui.press('p')
            time.sleep(1)
            
            # 在文件选择对话框中输入文件路径
            pyautogui.write(psd_path)
            time.sleep(0.5)
            pyautogui.press('enter')
            
            # 等待导入完成
            wait_time = self.cubism_config['import_wait_time']
            logger.info(f"等待PSD导入完成，预计需要{wait_time}秒...")
            time.sleep(wait_time)
            
            # 检查是否导入成功（这里可以添加导入成功的验证逻辑）
            
            return True
            
        except Exception as e:
            logger.error(f"导入PSD文件时出错: {str(e)}")
            return False
    
    def _setup_parameters(self) -> bool:
        """设置模型参数
        
        Returns:
            是否成功设置
        """
        logger.info("设置模型参数...")
        
        try:
            # 创建基本参数（这里需要根据Cubism界面进行自定义）
            # 创建Angle X参数
            self._create_parameter("AngleX", -30, 30)
            
            # 创建Angle Y参数
            self._create_parameter("AngleY", -30, 30)
            
            # 创建Angle Z参数
            self._create_parameter("AngleZ", -30, 30)
            
            # 创建Eye L Open参数
            self._create_parameter("EyeLOpen", 0, 1)
            
            # 创建Eye R Open参数
            self._create_parameter("EyeROpen", 0, 1)
            
            # 创建Eye Ball X参数
            self._create_parameter("EyeBallX", -1, 1)
            
            # 创建Eye Ball Y参数
            self._create_parameter("EyeBallY", -1, 1)
            
            # 创建Mouth Open参数
            self._create_parameter("MouthOpen", 0, 1)
            
            # 创建Mouth Form参数
            self._create_parameter("MouthForm", -1, 1)
            
            # 创建Body X参数
            self._create_parameter("BodyX", -10, 10)
            
            # 创建Body Y参数
            self._create_parameter("BodyY", -10, 10)
            
            # 创建Body Z参数
            self._create_parameter("BodyZ", -10, 10)
            
            # 创建Breath参数（呼吸）
            self._create_parameter("Breath", 0, 1)
            
            # 创建Hair Move参数（头发物理）
            self._create_parameter("HairMove", 0, 1)
            
            return True
            
        except Exception as e:
            logger.error(f"设置模型参数时出错: {str(e)}")
            return False
    
    def _create_parameter(self, name: str, min_value: float, max_value: float) -> bool:
        """创建参数
        
        Args:
            name: 参数名称
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            是否成功创建
        """
        logger.info(f"创建参数: {name}")
        
        try:
            # 点击Parameters面板
            # 这里需要根据实际UI添加点击Parameters面板的逻辑
            
            # 点击添加参数按钮
            # 这里需要根据实际UI添加点击添加参数按钮的逻辑
            
            # 输入参数名称
            pyautogui.write(name)
            time.sleep(0.2)
            pyautogui.press('tab')
            
            # 输入最小值
            pyautogui.write(str(min_value))
            time.sleep(0.2)
            pyautogui.press('tab')
            
            # 输入最大值
            pyautogui.write(str(max_value))
            time.sleep(0.2)
            pyautogui.press('tab')
            
            # 确认创建
            pyautogui.press('enter')
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"创建参数时出错: {str(e)}")
            return False
    
    def _setup_deformers(self) -> bool:
        """设置变形器
        
        Returns:
            是否成功设置
        """
        logger.info("设置变形器...")
        
        try:
            # 这里需要添加设置变形器的逻辑
            # 由于变形器设置比较复杂，可能需要根据不同部位分别设置
            
            # 设置头部旋转变形器
            self._setup_head_rotation()
            
            # 设置眼睛变形器
            self._setup_eye_deformers()
            
            # 设置嘴部变形器
            self._setup_mouth_deformers()
            
            # 设置身体变形器
            self._setup_body_deformers()
            
            return True
            
        except Exception as e:
            logger.error(f"设置变形器时出错: {str(e)}")
            return False
    
    def _setup_head_rotation(self) -> bool:
        """设置头部旋转变形器
        
        Returns:
            是否成功设置
        """
        logger.info("设置头部旋转变形器...")
        
        # 这里添加头部旋转变形器的具体实现
        # 由于过程比较复杂，需要根据实际操作步骤实现
        
        return True
    
    def _setup_eye_deformers(self) -> bool:
        """设置眼睛变形器
        
        Returns:
            是否成功设置
        """
        logger.info("设置眼睛变形器...")
        
        # 这里添加眼睛变形器的具体实现
        
        return True
    
    def _setup_mouth_deformers(self) -> bool:
        """设置嘴部变形器
        
        Returns:
            是否成功设置
        """
        logger.info("设置嘴部变形器...")
        
        # 这里添加嘴部变形器的具体实现
        
        return True
    
    def _setup_body_deformers(self) -> bool:
        """设置身体变形器
        
        Returns:
            是否成功设置
        """
        logger.info("设置身体变形器...")
        
        # 这里添加身体变形器的具体实现
        
        return True
    
    def _setup_physics(self) -> bool:
        """设置物理效果
        
        Returns:
            是否成功设置
        """
        logger.info("设置物理效果...")
        
        try:
            # 检查是否需要设置物理效果
            if not self.cubism_config['physics_enabled']:
                logger.info("物理效果已禁用，跳过设置")
                return True
            
            # 这里需要添加设置物理效果的逻辑
            # 主要包括头发和衣服等部位的物理效果设置
            
            # 设置头发物理
            self._setup_hair_physics()
            
            # 设置衣服物理
            self._setup_cloth_physics()
            
            return True
            
        except Exception as e:
            logger.error(f"设置物理效果时出错: {str(e)}")
            return False
    
    def _setup_hair_physics(self) -> bool:
        """设置头发物理效果
        
        Returns:
            是否成功设置
        """
        logger.info("设置头发物理效果...")
        
        # 这里添加头发物理效果的具体实现
        
        return True
    
    def _setup_cloth_physics(self) -> bool:
        """设置衣服物理效果
        
        Returns:
            是否成功设置
        """
        logger.info("设置衣服物理效果...")
        
        # 这里添加衣服物理效果的具体实现
        
        return True
    
    def _create_expressions(self) -> bool:
        """创建表情预设
        
        Returns:
            是否成功创建
        """
        logger.info("创建表情预设...")
        
        try:
            # 创建常用表情预设
            expressions = self.config['parameters']['mouth']['preset_expressions']
            
            for expression in expressions:
                self._create_expression(expression)
            
            return True
            
        except Exception as e:
            logger.error(f"创建表情预设时出错: {str(e)}")
            return False
    
    def _create_expression(self, name: str) -> bool:
        """创建单个表情预设
        
        Args:
            name: 表情名称
            
        Returns:
            是否成功创建
        """
        logger.info(f"创建表情预设: {name}")
        
        try:
            # 这里需要添加创建表情预设的逻辑
            # 不同表情需要设置不同的参数值
            
            if name == "smile":
                # 设置微笑表情
                # 设置MouthForm参数为0.7（微笑）
                # 设置EyeLOpen和EyeROpen参数为0.7（眯眼）
                pass
                
            elif name == "sad":
                # 设置悲伤表情
                # 设置MouthForm参数为-0.5（撇嘴）
                # 设置EyeLOpen和EyeROpen参数为0.8
                # 设置EyeBallY参数为-0.5（眼睛向下看）
                pass
                
            elif name == "angry":
                # 设置生气表情
                # 设置MouthForm参数为-0.7（撇嘴）
                # 设置EyeLOpen和EyeROpen参数为0.6（眯眼）
                # 设置EyeBallY参数为0.3（眼睛微向上看）
                pass
                
            elif name == "surprised":
                # 设置惊讶表情
                # 设置MouthOpen参数为0.8（嘴巴大开）
                # 设置MouthForm参数为0
                # 设置EyeLOpen和EyeROpen参数为1.0（眼睛睁大）
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"创建表情预设时出错: {str(e)}")
            return False
    
    def _save_project(self, output_path: str) -> bool:
        """保存Cubism项目
        
        Args:
            output_path: 输出路径
            
        Returns:
            是否成功保存
        """
        logger.info(f"保存Cubism项目到: {output_path}")
        
        try:
            # 使用Cubism的File -> Save As菜单
            # 按下Alt键显示菜单
            pyautogui.hotkey('alt')
            time.sleep(0.5)
            
            # 点击File菜单
            pyautogui.press('f')
            time.sleep(0.5)
            
            # 点击Save As选项
            pyautogui.press('a')
            time.sleep(1)
            
            # 在文件对话框中输入保存路径
            pyautogui.write(output_path)
            time.sleep(0.5)
            pyautogui.press('enter')
            
            # 等待保存完成
            time.sleep(2)
            
            # 检查文件是否已保存
            if not os.path.exists(output_path):
                logger.warning(f"保存后未找到文件: {output_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"保存Cubism项目时出错: {str(e)}")
            return False
    
    def _close_cubism(self) -> bool:
        """关闭Cubism软件
        
        Returns:
            是否成功关闭
        """
        logger.info("关闭Cubism软件...")
        
        try:
            # 使用Alt+F4关闭软件
            pyautogui.hotkey('alt', 'f4')
            time.sleep(1)
            
            # 如果弹出保存对话框，点击"不保存"
            # 这里需要根据实际UI添加处理保存对话框的逻辑
            
            # 等待软件关闭
            for _ in range(5):  # 最多等待5秒
                time.sleep(1)
                if not self._is_cubism_running():
                    return True
            
            # 如果软件未关闭，尝试强制关闭
            if platform.system() == "Windows":
                os.system("taskkill /f /im Cubism.exe")
            elif platform.system() == "Darwin":  # macOS
                os.system("pkill -f Cubism")
            
            return True
            
        except Exception as e:
            logger.error(f"关闭Cubism软件时出错: {str(e)}")
            return False
    
    def automate(self, layers_dir: str) -> str:
        """自动化Cubism操作流程
        
        Args:
            layers_dir: 图层目录路径
            
        Returns:
            Cubism项目路径
        """
        # 查找PSD文件
        psd_path = os.path.join(layers_dir, "character_layers.psd")
        if not os.path.exists(psd_path):
            logger.error(f"PSD文件不存在: {psd_path}")
            return ""
        
        # 创建输出目录
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_subdir = os.path.join(self.output_dir, f"model_{timestamp}")
        Path(output_subdir).mkdir(parents=True, exist_ok=True)
        
        # 项目文件路径
        project_path = os.path.join(output_subdir, "character_model.cmo3")
        
        # 复制PSD文件到输出目录
        psd_copy_path = os.path.join(output_subdir, "character_layers.psd")
        shutil.copy2(psd_path, psd_copy_path)
        
        if self.automation_method == "ui_automation":
            # 使用UI自动化方法
            # 启动Cubism
            if not self._start_cubism():
                logger.error("启动Cubism失败")
                return ""
            
            # 执行自动化步骤
            steps = self.cubism_config['automated_steps']
            
            for step in steps:
                if step == "import_psd":
                    if not self._import_psd(psd_path):
                        logger.error("导入PSD文件失败")
                        return ""
                        
                elif step == "setup_parameters" and self.cubism_config['auto_parameters']:
                    if not self._setup_parameters():
                        logger.error("设置参数失败")
                        return ""
                        
                elif step == "setup_deformers":
                    if not self._setup_deformers():
                        logger.error("设置变形器失败")
                        return ""
                        
                elif step == "setup_physics" and self.cubism_config['physics_enabled']:
                    if not self._setup_physics():
                        logger.error("设置物理效果失败")
                        return ""
                        
                elif step == "create_expressions":
                    if not self._create_expressions():
                        logger.error("创建表情预设失败")
                        return ""
            
            # 保存项目
            if not self._save_project(project_path):
                logger.error("保存项目失败")
                return ""
            
            # 关闭Cubism
            self._close_cubism()
            
        elif self.automation_method == "sdk_integration":
            # 使用SDK集成方法（需要Cubism SDK支持）
            logger.warning("SDK集成方法尚未实现")
            return ""
            
        elif self.automation_method == "manual":
            # 手动处理，仅准备文件
            logger.info("使用手动模式，已准备好PSD文件")
            
            # 创建说明文件
            instructions_path = os.path.join(output_subdir, "README.txt")
            with open(instructions_path, "w", encoding="utf-8") as f:
                f.write("Live2D模型创建说明\n")
                f.write("=================\n\n")
                f.write(f"1. 使用Live2D Cubism打开PSD文件: {psd_copy_path}\n")
                f.write("2. 设置模型参数和变形器\n")
                f.write("3. 设置物理效果\n")
                f.write("4. 创建表情预设\n")
                f.write(f"5. 将项目保存为: {project_path}\n")
            
            logger.info(f"已创建说明文件: {instructions_path}")
            
        else:
            logger.error(f"不支持的自动化方法: {self.automation_method}")
            return ""
        
        return output_subdir 