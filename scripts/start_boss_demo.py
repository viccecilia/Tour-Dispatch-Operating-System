import os
import subprocess
import sys
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765").rstrip("/")
FRONTEND_URL = os.environ.get("WX_DISPATCH_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def main() -> None:
    print("老板演示三屏模式")
    print("=" * 60)
    print("1. 左屏：微信开发者工具，打开司机端小程序")
    print(f"   小程序项目：{ROOT_DIR / 'miniapp'}")
    print("   页面：pages/driver/index?driver_id=1")
    print()
    print("2. 中屏：React 后台运营端")
    print(f"   调度页：{FRONTEND_URL}/#dispatch")
    print(f"   司机监控：{FRONTEND_URL}/#driver-monitor")
    print(f"   财务页：{FRONTEND_URL}/#finance")
    print()
    print("3. 右屏：流程解释窗口")
    print("   将打开一个 PowerShell 窗口运行：python scripts/demo_full_runtime_flow.py --driver-id 1")
    print("   每一步会暂停，按回车继续。")
    print("=" * 60)

    webbrowser.open(f"{FRONTEND_URL}/#dispatch")

    powershell_command = (
        f"Set-Location -LiteralPath '{ROOT_DIR}'; "
        "Write-Host '三屏演示流程已启动。'; "
        "Write-Host '请把本窗口放在右侧，后台放中间，微信开发者工具放左侧。'; "
        "Write-Host ''; "
        "python scripts/demo_full_runtime_flow.py --driver-id 1"
    )
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        ["powershell.exe", "-NoExit", "-Command", powershell_command],
        cwd=str(ROOT_DIR),
        stdin=None,
        stdout=None,
        stderr=None,
        creationflags=creationflags,
    )

    print()
    print("已打开后台调度页，并启动右侧流程解释窗口。")
    print("微信开发者工具如果还没打开，请手动打开 miniapp 项目，关闭“可视化”，点击“编译”。")


if __name__ == "__main__":
    main()
