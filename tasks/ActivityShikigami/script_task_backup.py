# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum, auto
from time import sleep
from datetime import datetime, timedelta
import cv2
import numpy as np
import random
from typing import Any
from cached_property import cached_property

from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.ocr import RuleOcr
from module.base.protect import random_sleep
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import SwitchSoulConfig, GeneralBattleConfig, ActivityShikigami
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import GeneralClimb
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
import tasks.Component.GeneralBattle.config_general_battle
import tasks.ActivityShikigami.page as game


def _prepare_image_for_ocr(image: np.ndarray, asset: RuleOcr) -> np.ndarray:
    image_copy = image.copy()
    x, y, w, h = asset.roi
    roi_to_process = image_copy[y:y + h, x:x + w]
    if len(roi_to_process.shape) == 3:
        gray_image = cv2.cvtColor(roi_to_process, cv2.COLOR_BGR2GRAY)
    else:
        gray_image = roi_to_process
    # 自适应二值化
    _, binary_norm = cv2.threshold(gray_image, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    _, binary_inv = cv2.threshold(gray_image, 127, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if cv2.countNonZero(binary_norm) < cv2.countNonZero(binary_inv):
        binary_correct = binary_norm
    else:
        binary_correct = binary_inv
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
    dilated_image = cv2.dilate(binary_correct, kernel, iterations=1)
    # 找轮廓
    contours, _ = cv2.findContours(dilated_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    processed_roi_content = None
    if contours:
        all_points = np.concatenate(contours, axis=0)
        bx, by, bw, bh = cv2.boundingRect(all_points)
        processed_roi_content = binary_correct[by:by + bh, bx:bx + bw]
    centered_roi = np.full((h, w), 255, dtype=np.uint8)  # 255代表白色
    if processed_roi_content is not None:
        content_h, content_w = processed_roi_content.shape
        if content_h <= h and content_w <= w:
            # 计算居中粘贴的位置，放到中间
            start_y = (h - content_h) // 2
            start_x = (w - content_w) // 2
            paste_area = centered_roi[start_y:start_y + content_h, start_x:start_x + content_w]
            paste_area[processed_roi_content == 255] = 0
        else:
            logger.warning(f"Content for asset '{asset.name}' is larger than ROI. Skipping centering.")
            # 内容过大，直接使用原始二值图的反转作为结果
            centered_roi = cv2.bitwise_not(binary_correct)
    else:
        logger.warning(f"No content found in ROI for asset: {asset.name}. ROI will be blank.")
    processed_roi_bgr = cv2.cvtColor(centered_roi, cv2.COLOR_GRAY2BGR)
    image_copy[y:y + h, x:x + w] = processed_roi_bgr
    return image_copy


class LimitTimeOut(Exception):
    pass


class LimitCountOut(Exception):
    pass


class StateMachine(BaseTask):
    run_idx: int = 0  # 当前爬塔类型
    _count_map = None

    @cached_property
    def conf(self) -> GeneralClimb:
        return self.config.model.activity_shikigami

    @property
    def climb_type(self) -> str:
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            return self.conf.general_climb.run_sequence_v[-1]
        return self.conf.general_climb.run_sequence_v[self.run_idx]

    @property
    def count_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: run count
        """
        if not getattr(self, "_count_map", None):
            self._count_map = {climb_type: 0 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._count_map

    # ----------------------------------------------------

    @property
    def slow_factor(self) -> float:
        """
        Scale timing when slow mode is enabled (battery saver, low FPS).
        """
        slow_cfg = getattr(self.conf, "slow_mode_config", None)
        if not slow_cfg:
            return 1.0
        return slow_cfg.factor if slow_cfg.enable else 1.0

    def put_status(self):
        """
        更新全局状态
        """

        def get_count(self) -> int:
            return self.count_map[self.climb_type]

        def get_limit(self) -> int:
            limit = getattr(self.conf.general_climb, f'{self.climb_type}_limit', 0)
            return 0 if not limit else limit

        # 超过运行时间
        if self.limit_time is not None and datetime.now() - self.start_time >= self.limit_time:
            logger.info(f"Climb type {self.climb_type} time out")
            raise LimitTimeOut
        # 次数达到限制
        if get_count(self) >= get_limit(self):
            logger.info(f"Climb type {self.climb_type} count limit reached")
            raise LimitCountOut

    def switch_next(self):
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            logger.info('All climbing activities have been completed')
            return False
        # 切换爬塔类型了, 恢复所有状态
        self.current_count = 0
        logger.hr(f'Climb switch to {self.climb_type}', 2)
        return True


class ScriptTask(StateMachine, GameUi, BaseActivity, SwitchSoul, ActivityShikigamiAssets):
    """
    更新前请先看 ./README.md
    """

    def run(self) -> None:
        self.limit_time: timedelta = self.conf.general_climb.limit_time_v
        #
        for climb_type in self.conf.general_climb.run_sequence_v:
            # 进入到活动的主页面，不是具体的战斗页面
            self.ui_get_current_page()
            self.ui_goto(game.page_climb_act)
            try:
                method_func = getattr(self, f'_run_{climb_type}')
                method_func()
            except LimitCountOut as e:
                self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_MAIN, interval=1)
            except LimitTimeOut as e:
                break
            finally:
                # 切换下一个爬塔类型
                self.switch_next()

        # 返回庭院
        logger.hr("Exit Shikigami", 2)
        self.ui_get_current_page(False)
        self.ui_goto(game.page_main)
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def fire_appear(self) -> bool:
        return self.ocr_appear(self.O_FIRE)

    def fire_appear_click(self, interval: float = None) -> bool:
        return self.ocr_appear_click(self.O_FIRE, interval=interval)

    def wait_until_fire(self, wait_time: float = None) -> bool:
        wait_timer = Timer(wait_time).start() if wait_time else None
        while 1:
            self.screenshot()
            if self.fire_appear():
                return True
            if wait_timer and wait_timer.reached():
                logger.warning("Wait until fire timeout")
                return False

    def boss_fire_appear(self) -> bool:
        return self.appear(self.I_BOSS_FIRE)

    def boss_fire_appear_click(self, interval: float = None) -> bool:
        return self.appear_then_click(self.I_BOSS_FIRE, interval=interval)

    def _reward_overlay_detected(self) -> bool:
        reward_markers = (
            self.I_REWARD,
            self.I_REWARD_PURPLE_SNAKE_SKIN,
            self.I_REWARD_GOLD,
            self.I_REWARD_GOLD_SNAKE_SKIN,
            self.I_REWARD_EXP_SOUL_4,
            self.I_REWARD_SOUL_5,
            self.I_REWARD_SOUL_6,
        )
        return any(self.appear(marker) for marker in reward_markers)

    def _run_pass(self):
        """
            更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type PASS', 1)
        self.ui_clicks([self.I_TO_BATTLE_MAIN, self.I_TO_BATTLE_MAIN_2],
                       stop=self.I_CHECK_BATTLE_MAIN, interval=1)
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_CHECK_BATTLE_MAIN)
        self.switch_climb_mode_in_game('pass')

        ocr_limit_timer = Timer(1).start()
        click_limit_timer = Timer(4).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if (self.appear_then_click(self.I_UI_CONFIRM, interval=0.5)
                    or self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5)):
                continue
            if self.ui_reward_appear_click():
                continue
            if self._reward_overlay_detected():
                logger.info("Reward overlay detected, fallback click to continue")
                self.random_reward_click(
                    exclude_click=[self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP],
                    click_now=True
                )
                continue
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if not self.fire_appear():
                continue
            #  --------------------------------------------------------------
            self.lock_team(self.conf.general_battle)
            if not self.check_tickets_enough():
                logger.warning(f'No tickets left, wait for next time')
                break
            if self.conf.general_climb.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue

        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_MAIN, interval=1)

    def _run_ap(self):
        """
            更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type AP')
        self.ui_clicks([self.I_TO_BATTLE_MAIN, self.I_TO_BATTLE_MAIN_2],
                       stop=self.I_CHECK_BATTLE_MAIN, interval=1)
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_CHECK_BATTLE_MAIN)
        self.switch_climb_mode_in_game('ap')

        ocr_limit_timer = Timer(1).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if self._reward_overlay_detected():
                logger.info("Reward overlay detected, fallback click to continue")
                self.random_reward_click(
                    exclude_click=[self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP],
                    click_now=True
                )
                continue
            if not self.fire_appear():
                self.appear_then_click(self.I_CHECK_BATTLE_MAIN, interval=4)
                continue
            #  --------------------------------------------------------------
            self.lock_team(self.conf.general_battle)
            if not self.check_tickets_enough():
                logger.warning(f'No tickets left, wait for next time')
                break
            if self.conf.general_climb.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue

        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_MAIN, interval=1)

    def _run_boss(self):
        """
        更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type BOSS')
        self.ui_click(self.I_TO_BATTLE_BOSS, stop=self.I_CHECK_BATTLE_BOSS, interval=1)
        if not self.appear(self.I_CHECK_BATTLE_BOSS):
            logger.warning("Cannot enter boss battle page, skip boss run")
            return

        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_CHECK_BATTLE_BOSS)

        ocr_limit_timer = Timer(1).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if (self.appear_then_click(self.I_UI_CONFIRM, interval=0.5)
                    or self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5)):
                continue
            if self.ui_reward_appear_click():
                continue
            if self._reward_overlay_detected():
                logger.info("Boss reward overlay detected, fallback click to continue")
                self.random_reward_click(
                    exclude_click=[self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP],
                    click_now=True
                )
                continue
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if not self.boss_fire_appear():
                continue
            #  --------------------------------------------------------------
            self.lock_team(self.conf.general_battle)
            if not self.check_tickets_enough():
                logger.warning(f'No tickets left, wait for next time')
                break
            if self.conf.general_climb.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue

        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_BOSS, interval=1)

    def start_battle(self):
        click_times = 0
        max_times = max(2, int(round(random.randint(2, 4) * self.slow_factor)))
        while 1:
            self.screenshot()
            # Only treat it as "in battle" if the challenge button is gone.
            fire_appear = self.boss_fire_appear() if self.climb_type == 'boss' else self.fire_appear()
            if self.is_in_battle(False) and not fire_appear:
                break
            if click_times >= max_times:
                logger.warning(f'Climb {self.climb_type} cannot enter, maybe already end, try next')
                return
            if (self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1 * self.slow_factor) or
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1 * self.slow_factor)):
                continue
            fire_clicked = (
                self.boss_fire_appear_click(interval=2 * self.slow_factor)
                if self.climb_type == 'boss'
                else self.fire_appear_click(interval=2 * self.slow_factor)
            )
            if fire_clicked:
                click_times += 1
                logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                continue
        # 运行战斗
        self.run_general_battle(config=self.get_general_battle_conf())

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 通用战斗结束判断
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info(f"Start {self.climb_type} battle process")
        self.count_map[self.climb_type] = self.current_count
        for btn in (self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM):
            btn.name = "BATTLE_RANDOM"
        reward_markers = (
            self.I_REWARD,
            self.I_REWARD_PURPLE_SNAKE_SKIN,
            self.I_REWARD_GOLD,
            self.I_REWARD_GOLD_SNAKE_SKIN,
            self.I_REWARD_EXP_SOUL_4,
            self.I_REWARD_SOUL_5,
            self.I_REWARD_SOUL_6,
        )
        win_seen = False
        post_win_click_timer = Timer(max(1.0, 1.0 * self.slow_factor)).start()
        post_win_timeout = Timer(max(20, int(round(20 * self.slow_factor)))).start()
        ok_cnt, max_retry = 0, max(5, int(round(5 * self.slow_factor)))
        battle_wait_timeout = Timer(max(45, int(round(45 * self.slow_factor)))).start()
        while 1:
            sleep(random.uniform(0.5, 1.5) * self.slow_factor)
            self.screenshot()
            ok_cnt += 1
            if battle_wait_timeout.reached():
                logger.warning("Battle wait timeout reached, fallback return success")
                return True
            # 达到最大重试次数则直接交给上层处理
            if ok_cnt > max_retry:
                break
            # 识别到挑战说明已经退出战斗
            fire_appear = self.boss_fire_appear() if self.climb_type == 'boss' else self.fire_appear()
            if ok_cnt > 0 and fire_appear:
                return True
            # 战斗失败
            if self.appear(self.I_FALSE):
                logger.warning("Battle failed")
                self.ui_click_until_smt_disappear(self.random_reward_click(click_now=False), self.I_FALSE, interval=1.5 * self.slow_factor)
                return False
            # 战斗成功
            if self.appear_then_click(self.I_WIN, interval=2 * self.slow_factor):
                win_seen = True
                post_win_click_timer.reset()
                post_win_timeout.reset()
                continue
            # 出现结算奖励标识（兼容不同奖励形态）
            appear_reward_like = any(self.appear(marker) for marker in reward_markers)
            if appear_reward_like:
                logger.info('Win battle')
                reward_wait_timeout = Timer(max(15, int(round(15 * self.slow_factor)))).start()
                while 1:
                    self.screenshot()
                    if reward_wait_timeout.reached():
                        logger.warning("Reward wait timeout, force clicking continue area")
                        self.random_reward_click(
                            exclude_click=[self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP],
                            click_now=True
                        )
                        sleep(0.5 * self.slow_factor)
                        return True
                    appear_reward = self.appear_then_click(self.I_REWARD)
                    appear_reward_like = appear_reward or any(self.appear(marker) for marker in reward_markers[1:])
                    if not appear_reward_like:
                        break
                    if appear_reward_like:
                        # Prefer bottom area to avoid top-bar accidental page opens.
                        self.click(self.C_RANDOM_BOTTOM, interval=1.8 * self.slow_factor)
                        continue
                return True
            # 已点击过胜利，但奖励模板被遮挡时，主动点击“点击屏幕继续”区域推进
            if win_seen:
                if post_win_click_timer.reached_and_reset():
                    logger.info("Post-win fallback click to clear covered reward page")
                    self.random_reward_click(
                        exclude_click=[self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP],
                        click_now=True
                    )
                fire_appear = self.boss_fire_appear() if self.climb_type == 'boss' else self.fire_appear()
                if fire_appear:
                    return True
                if post_win_timeout.reached():
                    logger.warning("Post-win fallback timeout reached, continue as success")
                    return True
                continue
            # 已经不在战斗中了, 且奖励也识别过了, 则随机点击
            # if ok_cnt > 0 and not self.is_in_battle(False):
            #     self.random_reward_click(exclude_click=[self.C_RANDOM_BOTTOM])
            #     ok_cnt += 1
            #     continue
            # 战斗中随机滑动
            if ok_cnt == 0 and random_click_swipt_enable:
                self.random_click_swipt()
        return True

    def switch_soul(self, enter_button: RuleImage, cur_img: RuleImage):
        conf = self.conf.switch_soul_config
        conf.validate_switch_soul()
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{self.climb_type}_by_name", False)
        if not enable_switch and not enable_by_name:
            return
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"{self.climb_type}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team")
            self.run_switch_soul(group_team)
        self.ui_click(self.I_UI_BACK_YELLOW, stop=cur_img, interval=1)

    def switch_climb_mode_in_game(self, mode: str = 'ap'):
        map_check = {
            'ap': self.I_CLIMB_MODE_AP,
            'pass': self.I_CLIMB_MODE_PASS,
        }
        logger.info(f'Switch climb mode to {mode}')
        target_check = map_check[mode]
        switch_timeout = Timer(max(20, int(round(20 * self.slow_factor)))).start()
        while 1:
            self.screenshot()
            if self.appear(target_check):
                logger.info(f'Climb mode already at {mode}')
                return
            if self.appear_then_click(self.I_CLIMB_MODE_SWITCH, interval=1.9 * self.slow_factor):
                continue
            if switch_timeout.reached():
                logger.warning(f'Switch climb mode to {mode} timeout, try recover page once')
                self.ui_get_current_page(skip_first_screenshot=False)
                self.ui_goto(game.page_climb_act, timeout=20)
                if self.appear(target_check):
                    logger.info(f'Climb mode switched to {mode} after recovery')
                    return
                logger.warning(f'Switch climb mode to {mode} still failed after recovery')
                return

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁
        """
        enable_preset = getattr(battle_conf, f"enable_{self.climb_type}_preset", False)
        lock_timeout = Timer(max(8, int(round(8 * self.slow_factor)))).start()
        if self.climb_type == 'boss':
            stop_img = self.I_UNLOCK if enable_preset else self.I_BOSS_LOCK
            click_img = self.I_BOSS_LOCK if enable_preset else self.I_UNLOCK
        else:
            stop_img = self.I_UNLOCK if enable_preset else self.I_LOCK
            click_img = self.I_LOCK if enable_preset else self.I_UNLOCK

        # Some boss pages may hide lock controls; avoid infinite ui_click loop.
        while 1:
            self.screenshot()
            if self.appear(stop_img):
                logger.info(f'{"Unlock" if enable_preset else "Lock"} {self.climb_type} team')
                return
            if self.appear_then_click(click_img, interval=1.5 * self.slow_factor):
                continue
            if lock_timeout.reached():
                logger.warning(f'Lock team control not found for {self.climb_type}, skip lock operation')
                return

    def check_tickets_enough(self) -> bool:
        """
        判断当前爬塔门票是否足够
        :return: True 可以运行 or False
        """
        logger.hr(f'Check {self.climb_type} tickets')
        if self.climb_type == 'boss':
            fire_ready = self.wait_until_appear(self.I_BOSS_FIRE, wait_time=3 * self.slow_factor)
        else:
            fire_ready = self.wait_until_fire(wait_time=3 * self.slow_factor)
        if not fire_ready:
            logger.warning(f'Detect fire fail, try reidentify')
            # Reward overlay may cover FIRE OCR; force click screen to continue and retry.
            for _ in range(2):
                self.random_reward_click(
                    exclude_click=[self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP],
                    click_now=True
                )
                sleep(0.4 * self.slow_factor)
                if self.climb_type == 'boss':
                    fire_ready = self.wait_until_appear(self.I_BOSS_FIRE, wait_time=1.5 * self.slow_factor)
                else:
                    fire_ready = self.wait_until_fire(wait_time=1.5 * self.slow_factor)
                if fire_ready:
                    break
            else:
                return False
        self.screenshot()
        remain_times = 0
        if self.climb_type == 'pass':
            remain_times = self.O_REMAIN_PASS.ocr_digit(
                _prepare_image_for_ocr(self.device.image, asset=self.O_REMAIN_PASS))
        if self.climb_type == 'ap':
            remain_times = self.O_REMAIN_AP.ocr_digit(
                _prepare_image_for_ocr(self.device.image, asset=self.O_REMAIN_AP))
        if self.climb_type == 'boss':
            _, remain_times, _ = self.O_REMAIN_BOSS.ocr_digit_counter(self.device.image)
        if self.climb_type == 'ap100':
            remain_times = self.O_REMAIN_AP100.ocr_digit(
                _prepare_image_for_ocr(self.device.image, asset=self.O_REMAIN_AP100))
        return remain_times > 0

    def get_general_battle_conf(self) -> tasks.Component.GeneralBattle.config_general_battle.GeneralBattleConfig:
        from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig as gbc
        self.conf.validate_switch_preset()
        enable_preset = getattr(self.conf.general_battle, f'enable_{self.climb_type}_preset', False)
        group, team = getattr(self.conf.switch_soul_config, f'{self.climb_type}_group_team').split(',')
        return gbc(lock_team_enable=not enable_preset,
                   preset_enable=enable_preset,
                   preset_group=group if enable_preset else 1,
                   preset_team=team if enable_preset else 1,
                   green_enable=getattr(self.conf.general_battle, f'enable_{self.climb_type}_green', False),
                   green_mark=getattr(self.conf.general_battle, f'{self.climb_type}_green_mark'),
                   random_click_swipt_enable=getattr(self.conf.general_battle, f'enable_{self.climb_type}_anti_detect',
                                                     False), )

    def random_reward_click(self, exclude_click: list = None, click_now: bool = True) -> RuleClick:
        """
        随机点击
        :param exclude_click: 排除的点击位置
        :param click_now: 是否立即点击
        :return: 随机的点击位置
        """
        options = [self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM]
        if exclude_click:
            options = [option for option in options if option not in exclude_click]
        target = random.choice(options)
        if click_now:
            self.click(target, interval=1.8)
        return target


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
