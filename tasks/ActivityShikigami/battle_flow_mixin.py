# This Python file uses the following encoding: utf-8
from __future__ import annotations

import random

from module.base.protect import random_sleep
from module.base.timer import Timer
from module.logger import logger


class ActivityShikigamiBattleFlowMixin:
    def fire_appear(self) -> bool:
        return self.ocr_appear(self.O_FIRE)

    def fire_appear_click(self, interval: float = None) -> bool:
        if not self.fire_appear():
            return False
        if interval:
            timer = self.interval_timer.get(self.O_FIRE.name)
            if timer is None or timer.limit != interval:
                timer = Timer(interval)
                self.interval_timer[self.O_FIRE.name] = timer
            if not timer.reached():
                return False
            timer.reset()
        # Click inside OCR ROI (not OCR area) to avoid hitting climb-mode switch button.
        x, y, w, h = self.O_FIRE.roi
        rx = random.randint(x, x + max(w - 1, 1))
        ry = random.randint(y, y + max(h - 1, 1))
        self.device.click(x=rx, y=ry, control_name=self.O_FIRE.name)
        return True

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

    def _run_climb_loop(
        self,
        fire_appear_fn,
        on_fire_missing_fn=None,
        with_confirm: bool = False,
        with_ui_reward: bool = False,
        reward_log: str = "Reward overlay detected, fallback click to continue",
    ):
        ocr_limit_timer = Timer(1).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if with_confirm and (
                self.appear_then_click(self.I_UI_CONFIRM, interval=0.5)
                or self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5)
            ):
                continue
            if with_ui_reward and self.ui_reward_appear_click():
                continue
            if self._reward_overlay_detected():
                logger.info(reward_log)
                self.random_reward_click(
                    exclude_click=[self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP],
                    click_now=True
                )
                continue
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if not fire_appear_fn():
                if on_fire_missing_fn:
                    on_fire_missing_fn()
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

    def lock_team(self, battle_conf):
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
