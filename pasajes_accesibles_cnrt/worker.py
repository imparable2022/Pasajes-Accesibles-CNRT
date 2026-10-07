from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .client import CnrtClient


@dataclass
class Command:
    name: str
    args: tuple
    kwargs: dict
    callback: Optional[Callable[[Any, Optional[BaseException]], None]] = None


class CnrtWorker(threading.Thread):
    """Mantiene Playwright y todas sus llamadas dentro de un único hilo."""

    def __init__(self, dispatcher: Callable[[Callable, Any, Optional[BaseException]], None], headless: bool = True):
        super().__init__(daemon=True, name="CNRT-Worker")
        self.dispatcher = dispatcher
        self.headless = headless
        self.commands: queue.Queue[Command | None] = queue.Queue()
        self.ready = threading.Event()
        self.start_error: Optional[BaseException] = None
        self.client: Optional[CnrtClient] = None

    def run(self):
        try:
            self.client = CnrtClient(headless=self.headless)
            self.client.start()
        except BaseException as exc:
            self.start_error = exc
        finally:
            self.ready.set()
        if self.start_error:
            # Si el navegador no pudo iniciarse, respondemos a los comandos en lugar de dejar la interfaz esperando.
            while True:
                cmd = self.commands.get()
                if cmd is None:
                    return
                if cmd.callback:
                    self.dispatcher(cmd.callback, None, self.start_error)
        while True:
            cmd = self.commands.get()
            if cmd is None:
                break
            try:
                method = getattr(self.client, cmd.name)
                result = method(*cmd.args, **cmd.kwargs)
                error = None
            except BaseException as exc:
                result = None
                error = exc
            if cmd.callback:
                self.dispatcher(cmd.callback, result, error)
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass

    def submit(self, name: str, *args, callback=None, **kwargs):
        self.commands.put(Command(name=name, args=args, kwargs=kwargs, callback=callback))

    def stop(self):
        self.commands.put(None)
