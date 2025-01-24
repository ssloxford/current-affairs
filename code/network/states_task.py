from __future__ import annotations

import asyncio
from typing import Any, Dict, List, TYPE_CHECKING, NamedTuple, Tuple

from .state_base import StateBaseClass

if TYPE_CHECKING:
    from . import ui_link
    from .. import controller

import traceback
import logging
import signal
from enum import Enum

class TaskResultEnum(Enum):
    Unknown = 0

    Running = 1

    Success = 2
    Failed = 3
    Failed_Anomaly = 4
    Failed_Retry = 6
    
    Skipped = 5

class TaskRequirement():
    task: StateTask
    cache_policy: int # -1: not allowed, 0: allowed, 1: needed
    ignore_anomaly: bool #

    def __init__(self, task: StateTask, ignore_anomaly: bool = False, cache_policy: int = 0):
        self.task = task
        self.cache_policy = cache_policy
        self.ignore_anomaly = ignore_anomaly


class StateTask(StateBaseClass):
    name: str
    parent_name: str | None

    requires: TaskRequirement | None

    user_enabled: bool
    anomalies: int
    last_run_result: TaskResultEnum


    def __init__(self, ws: "ui_link.UI_Link", name: str, requires: TaskRequirement | None):
        super().__init__(ws)

        self.name = name
        self.requires = requires
        self.parent_name = self.requires.task.name if self.requires is not None else None

        self.user_enabled = True
        self.anomalies = 0
        self.last_run_result = TaskResultEnum.Unknown
    

    async def send_state_update(self):
        await self.ws.send_broadcast({
            "type": "task",
            "name": self.name,
            "enabled": self.user_enabled,
            "result": self.last_run_result.value,
            "anomalies": self.anomalies
        })

    def get_state_init(self):
        return {
            "name": self.name,
            "parent_name": self.parent_name,
            "enabled": self.user_enabled,
            "result": self.last_run_result.value,
            "anomalies": self.anomalies
        }

    async def set_result(self, new_result):
        self.last_run_result = new_result
        if new_result == TaskResultEnum.Failed_Anomaly:
            self.anomalies += 1
        await self.send_state_update()

    async def _check_should_run(self, ctrl) -> bool:
        return True

    async def check_should_run(self, ctrl) -> bool:
        #Enabled check
        if not self.user_enabled:
            return False

        return await self._check_should_run(ctrl)

    async def _run(self, ctrl) -> TaskResultEnum:
        raise ValueError("Did not overload")

    async def run(self, ctrl: "controller.Controller", manual: bool, ignore_anomaly: bool = False, cache_policy: int = 0) -> TaskResultEnum:
        new_state: TaskResultEnum = TaskResultEnum.Failed_Anomaly

        print("Start task", self.name)

        this_task = asyncio.current_task()
        def sigint_handler(_signo, _stack_frame):
            if this_task is not None:
                this_task.cancel("SIGINT")

        signal.signal(signal.SIGINT, sigint_handler)

        try:

            if (not manual or cache_policy == 1):
                if cache_policy >= 0:
                    #Check cache
                    if len(ctrl.run_cache) and ctrl.run_cache[-1] == self and self.last_run_result != TaskResultEnum.Failed_Retry:
                        new_state = self.last_run_result
                        return new_state
                    else:
                        #Should have been cached
                        if cache_policy == 1:
                            new_state = TaskResultEnum.Skipped
                            return new_state

            if (not manual):
                #Dont re-run failed task
                if (self.last_run_result == TaskResultEnum.Failed or (self.last_run_result == TaskResultEnum.Failed_Anomaly and not ignore_anomaly)):
                    new_state = self.last_run_result
                    return new_state

            #Run pre-requisit
            if self.requires is not None:
                req_result = await self.requires.task.run(ctrl, manual, self.requires.ignore_anomaly, self.requires.cache_policy)
                if req_result != TaskResultEnum.Success:
                    new_state = req_result
                    return new_state

            #Check pre-conditions
            if not await self.check_should_run(ctrl):
                new_state = TaskResultEnum.Skipped
                return new_state

            #The task officially starts running now.
            await self.set_result(TaskResultEnum.Running)
            ctrl.run_cache.append(self)
            new_state = await self._run(ctrl)
            return new_state

        #Not even sure how that happened
        except KeyboardInterrupt:
            raise
        except asyncio.CancelledError as e:
            if (len(e.args) > 0) and e.args[0] == "SIGINT":
                print("Experiment cancelled")
                new_state = TaskResultEnum.Skipped
                return new_state
            else:
                raise
        except SystemExit: #Will be sent on SIGTERM
            raise
        except Exception as e:
            print("Task exception")
            logging.error(traceback.format_exc())
            #First crash only counts as anomaly
            new_state = TaskResultEnum.Failed_Anomaly
            return new_state
        finally:
            try:
                await self.set_result(new_state)
            except Exception as e:
                print("Cleanup exception")
                logging.error(traceback.format_exc())
            except (asyncio.CancelledError, SystemExit, KeyboardInterrupt):
                raise

    async def reset(self):
        self.crash_counter = 0
        await self.set_result(TaskResultEnum.Unknown)
        