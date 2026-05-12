import os
import sys
import time

import psutil

from astrbot.core import logger
from astrbot.core.utils.astrbot_path import get_astrbot_path

from .zip_updator import RepoZipUpdator


class AstrBotUpdator(RepoZipUpdator):
    """AstrBot 更新器，继承自 RepoZipUpdator 类
    该类用于处理 AstrBot 的重启操作
    """

    def __init__(self, repo_mirror: str = "", verify: str | bool | None = None) -> None:
        super().__init__(repo_mirror, verify=verify)
        self.MAIN_PATH = get_astrbot_path()

    def terminate_child_processes(self) -> None:
        """终止当前进程的所有子进程
        使用 psutil 库获取当前进程的所有子进程，并尝试终止它们
        """
        try:
            parent = psutil.Process(os.getpid())
            children = parent.children(recursive=True)
            logger.info(f"正在终止 {len(children)} 个子进程。")
            for child in children:
                logger.info(f"正在终止子进程 {child.pid}")
                child.terminate()
                try:
                    child.wait(timeout=3)
                except psutil.NoSuchProcess:
                    continue
                except psutil.TimeoutExpired:
                    logger.info(f"子进程 {child.pid} 没有被正常终止, 正在强行杀死。")
                    child.kill()
        except psutil.NoSuchProcess:
            pass

    @staticmethod
    def _is_option_arg(arg: str) -> bool:
        return arg.startswith("-")

    @classmethod
    def _collect_flag_values(cls, argv: list[str], flag: str) -> str | None:
        try:
            idx = argv.index(flag)
        except ValueError:
            return None

        if idx + 1 >= len(argv):
            return None

        value_parts: list[str] = []
        for arg in argv[idx + 1 :]:
            if cls._is_option_arg(arg):
                break
            if arg:
                value_parts.append(arg)

        if not value_parts:
            return None

        return " ".join(value_parts).strip() or None

    @classmethod
    def _resolve_webui_dir_arg(cls, argv: list[str]) -> str | None:
        return cls._collect_flag_values(argv, "--webui-dir")

    def _build_frozen_reboot_args(self) -> list[str]:
        argv = list(sys.argv[1:])
        webui_dir = self._resolve_webui_dir_arg(argv)
        if not webui_dir:
            webui_dir = os.environ.get("ASTRBOT_WEBUI_DIR")

        if webui_dir:
            return ["--webui-dir", webui_dir]
        return []

    @staticmethod
    def _reset_pyinstaller_environment() -> None:
        if not getattr(sys, "frozen", False):
            return
        os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        for key in list(os.environ.keys()):
            if key.startswith("_PYI_"):
                os.environ.pop(key, None)

    def _build_reboot_argv(self, executable: str) -> list[str]:
        if os.environ.get("ASTRBOT_CLI") == "1":
            args = sys.argv[1:]
            return [executable, "-m", "astrbot.cli.__main__", *args]
        if getattr(sys, "frozen", False):
            args = self._build_frozen_reboot_args()
            return [executable, *args]
        return [executable, *sys.argv]

    @staticmethod
    def _exec_reboot(executable: str, argv: list[str]) -> None:
        if os.name == "nt" and getattr(sys, "frozen", False):
            quoted_executable = f'"{executable}"' if " " in executable else executable
            quoted_args = [f'"{arg}"' if " " in arg else arg for arg in argv[1:]]
            os.execl(executable, quoted_executable, *quoted_args)
            return
        os.execv(executable, argv)

    def _reboot(self, delay: int = 3) -> None:
        """重启当前程序
        在指定的延迟后，终止所有子进程并重新启动程序
        这里只能使用 os.exec* 来重启程序
        """
        time.sleep(delay)
        self.terminate_child_processes()
        executable = sys.executable

        try:
            self._reset_pyinstaller_environment()
            reboot_argv = self._build_reboot_argv(executable)
            self._exec_reboot(executable, reboot_argv)
        except Exception as e:
            logger.error(f"重启失败（{executable}, {e}），请尝试手动重启。")
            raise e
