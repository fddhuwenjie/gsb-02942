#!/usr/bin/env python3
"""
客户端打包脚本
将 client.py 打包为独立的 exe 文件
"""
import os
import sys
import subprocess
import shutil

def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        print(f"✓ PyInstaller 已安装 (版本: {PyInstaller.__version__})")
        return True
    except ImportError:
        print("✗ PyInstaller 未安装")
        print("  正在安装 PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        return True

def build_exe():
    """打包为 exe"""
    print("\n" + "=" * 50)
    print("开始打包客户端...")
    print("=" * 50 + "\n")
    
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    client_py = os.path.join(current_dir, "client.py")
    config_json = os.path.join(current_dir, "config.json")
    
    # 检查文件是否存在
    if not os.path.exists(client_py):
        print(f"✗ 错误: 找不到 {client_py}")
        return False
    
    # PyInstaller 参数
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                    # 打包为单个文件
        "--noconsole",                  # 无控制台窗口 (后台运行)
        "--name", "RemoteShutdownClient",  # 输出文件名
        "--icon", "NONE",               # 无图标 (可以替换为 .ico 文件路径)
        "--clean",                      # 清理临时文件
        "--noconfirm",                  # 不确认覆盖
    ]
    
    # 添加数据文件
    if os.path.exists(config_json):
        args.extend(["--add-data", f"{config_json};."])
    
    # 添加主文件
    args.append(client_py)
    
    print("执行命令:", " ".join(args))
    print()
    
    # 执行打包
    result = subprocess.run(args, cwd=current_dir)
    
    if result.returncode == 0:
        # 移动输出文件
        dist_dir = os.path.join(current_dir, "dist")
        exe_name = "RemoteShutdownClient.exe" if sys.platform == "win32" else "RemoteShutdownClient"
        exe_path = os.path.join(dist_dir, exe_name)
        
        if os.path.exists(exe_path):
            print("\n" + "=" * 50)
            print("✓ 打包成功!")
            print("=" * 50)
            print(f"\n输出文件: {exe_path}")
            print(f"文件大小: {os.path.getsize(exe_path) / 1024 / 1024:.2f} MB")
            
            # 复制配置文件到 dist 目录
            if os.path.exists(config_json):
                shutil.copy(config_json, dist_dir)
                print(f"配置文件已复制到: {os.path.join(dist_dir, 'config.json')}")
            
            print("\n使用说明:")
            print("1. 将 dist 目录下的文件复制到目标电脑")
            print("2. 修改 config.json 中的 server_url 为服务器地址")
            print("3. 运行 RemoteShutdownClient.exe")
            return True
    
    print("\n✗ 打包失败")
    return False

def clean_build():
    """清理构建文件"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    dirs_to_remove = ["build", "dist", "__pycache__"]
    files_to_remove = ["RemoteShutdownClient.spec"]
    
    for d in dirs_to_remove:
        path = os.path.join(current_dir, d)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"已删除: {path}")
    
    for f in files_to_remove:
        path = os.path.join(current_dir, f)
        if os.path.exists(path):
            os.remove(path)
            print(f"已删除: {path}")
    
    print("清理完成")

def main():
    """主函数"""
    print("=" * 50)
    print("远程关机客户端打包工具")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean_build()
        return
    
    # 检查依赖
    if not check_pyinstaller():
        return
    
    # 执行打包
    build_exe()

if __name__ == "__main__":
    main()
