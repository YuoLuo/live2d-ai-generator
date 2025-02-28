# Live2D AI Generator 快速上手指南

本指南将帮助您快速启动并使用Live2D AI Generator创建您的第一个Live2D模型。

## 前提条件

- 已安装Python 3.8或更高版本
- 已安装Live2D Cubism软件
- 对于更佳性能，建议使用支持CUDA的NVIDIA GPU

## 快速安装

1. 克隆或下载本项目

2. 安装依赖项：
```bash
# 在项目根目录下运行
pip install -r requirements.txt
```

3. 下载必要的模型：
```bash
python scripts/download_models.py
```

## 设置配置

1. 打开`config.yml`文件
2. 设置Cubism软件路径：
```yaml
cubism:
  executable_path: "C:/Program Files/Live2D Cubism 4.0/app/Cubism.exe"  # 替换为您的实际路径
```
3. (可选) 调整输出目录：
```yaml
io:
  output_dir: "./output"  # 所有生成的文件将保存在此目录
  temp_dir: "./temp"      # 临时文件目录
```

## 使用图形界面（推荐）

最简单的使用方式是通过图形界面：

```bash
python gui_run.py
```

界面启动后，您可以：

1. 在"一键生成"标签页上传角色图像或使用AI生成
2. 调整生成参数（提示词、风格、分辨率等）
3. 设置图层分割参数
4. 点击"开始生成"按钮启动处理流程
5. 在状态区域查看进度，在图层预览区域查看分割结果
6. 处理完成后查看导出路径并打开输出文件夹查看结果

## 命令行快速使用

如果您想通过命令行使用：

```bash
# 使用默认设置生成模型
python main.py

# 使用现有图像
python main.py --character-image 您的图像路径.png

# 跳过角色生成步骤，使用现有图层
python main.py --skip-character --layer-dir ./output/layers_某个时间戳
```

## 常见问题速查

1. **图形界面不能启动**
   - 确保已安装Gradio：`pip install gradio`
   - 尝试指定不同端口：`python gui_run.py --port 8080`

2. **模型生成失败**
   - 检查Cubism软件路径是否正确设置
   - 确保所有必要的模型已下载
   - 查看日志文件了解详细错误信息

3. **图层分割效果不理想**
   - 尝试不同的分割模型和质量设置
   - 使用更清晰、前景突出的角色图像
   - 考虑手动编辑分割结果

4. **Cubism自动化失败**
   - 确保Cubism软件已正确安装并能正常启动
   - 检查是否有其他软件干扰了UI自动化过程
   - 在相同分辨率下重试

## 下一步

- 查看完整的[README.md](README.md)了解更多详细信息
- 探索配置文件中的更多高级选项
- 尝试使用不同的角色风格和姿势
- 加入我们的社区分享您的作品和经验

祝您使用愉快！ 