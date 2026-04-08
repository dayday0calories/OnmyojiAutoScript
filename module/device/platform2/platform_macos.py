import os
import subprocess
import time
import typing as t
from dataclasses import dataclass

from module.base.decorator import cached_property
from module.device.platform2.emulator_base import EmulatorBase, EmulatorInstanceBase
from module.device.platform2.platform_base import PlatformBase, serial_to_id
from module.logger import logger


class MuMuMacEmulator(EmulatorBase):
    @classmethod
    def path_to_type(cls, path: str) -> str:
        path = (path or '').replace('\\', '/')
        if 'MuMuPlayer.app' in path or path.endswith('/mumutool'):
            return cls.MuMuPlayer12
        return ''

    def iter_instances(self) -> t.Iterable[EmulatorInstanceBase]:
        return []

    def iter_adb_binaries(self) -> t.Iterable[str]:
        return []


@dataclass
class MuMuMacInstance(EmulatorInstanceBase):
    vmindex: int = 0

    @cached_property
    def emulator(self):
        return MuMuMacEmulator(self.path)

    @cached_property
    def MuMuPlayer12_id(self):
        return self.vmindex


class PlatformMacintosh(PlatformBase):
    @staticmethod
    def _mumutool_path() -> str:
        for path in (
            '/tmp/com.netease.mumu.nemux/mumutool',
            '/Applications/MuMuPlayer.app/Contents/MacOS/mumutool',
        ):
            if os.path.isfile(path):
                return path
        return ''

    @staticmethod
    def _player_path() -> str:
        path = '/Applications/MuMuPlayer.app/Contents/MacOS/MuMuPlayer'
        return path if os.path.isfile(path) else ''

    def _instance_id(self) -> t.Optional[int]:
        serial = self.config_interface['serial']
        return serial_to_id(serial)

    def _instance_pattern(self, instance_id: int) -> str:
        return (
            '/Applications/MuMuPlayer.app/Contents/MacOS/'
            f'MuMuEmulator.app/Contents/MacOS/MuMuEmulator --index {instance_id}'
        )

    def _run_mumutool(self, *args) -> t.Optional[subprocess.CompletedProcess]:
        mumutool = self._mumutool_path()
        if not mumutool:
            logger.warning('mumutool not found on macOS')
            return None
        cmd = [mumutool, *map(str, args)]
        logger.info(f'Run mumutool on macOS: {cmd}')
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(mumutool) or None,
            capture_output=True,
            text=True,
        )
        stdout = (result.stdout or '').strip()
        stderr = (result.stderr or '').strip()
        if stdout:
            logger.info(stdout)
        if stderr:
            logger.warning(stderr)
        return result

    @cached_property
    def all_emulator_instances(self) -> t.List[EmulatorInstanceBase]:
        instance_id = self._instance_id()
        player = self._player_path()
        if instance_id is None or not player:
            return []
        serial = self.config_interface['serial']
        return [
            MuMuMacInstance(
                serial=serial,
                name=f'MuMuPlayer-12.0-{instance_id}',
                path=player,
                vmindex=instance_id,
            )
        ]

    @staticmethod
    def iter_running_emulator():
        player = '/Applications/MuMuPlayer.app/Contents/MacOS/MuMuPlayer'
        result = subprocess.run(['pgrep', '-af', 'MuMuPlayer|MuMuEmulator'], capture_output=True, text=True)
        if result.returncode != 0:
            return
        for line in (result.stdout or '').splitlines():
            if 'MuMuPlayer' in line or 'MuMuEmulator' in line:
                yield player

    def is_emulator_running(self) -> bool:
        instance = self.emulator_instance
        if instance is None:
            return False
        pattern = self._instance_pattern(instance.vmindex)
        result = subprocess.run(
            ['pgrep', '-f', pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0

    def emulator_start(self):
        instance = self.emulator_instance
        if instance is None:
            logger.info('No MuMu instance resolved on macOS, skip emulator start')
            return
        if self.is_emulator_running():
            logger.info(f'MuMu instance already running: {instance.vmindex}')
            return
        result = self._run_mumutool('open', instance.vmindex)
        if not result or result.returncode != 0:
            logger.warning('mumutool open failed on macOS')
            return
        timeout = time.time() + 60
        while time.time() < timeout:
            if self.is_emulator_running():
                return
            time.sleep(1)
        logger.warning('MuMu emulator start timeout on macOS')

    def emulator_stop(self):
        instance = self.emulator_instance
        if instance is None:
            logger.info('No MuMu instance resolved on macOS, skip emulator stop')
            return
        result = self._run_mumutool('close', instance.vmindex)
        if not result or result.returncode != 0:
            logger.warning('mumutool close failed on macOS')

