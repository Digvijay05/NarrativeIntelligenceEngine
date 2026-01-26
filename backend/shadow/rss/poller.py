import time
from typing import Iterator
from datetime import datetime, timezone

def shadow_tick_generator(poll_interval_seconds: int) -> Iterator[int]:
    """
    Generates deterministic logical ticks.
    Tick increments exactly once per poll interval.
    """
    tick = 0
    while True:
        tick += 1
        yield tick
        time.sleep(poll_interval_seconds)


def now_utc():
    return datetime.now(tz=timezone.utc)

def get_next_tick_from_log(events: list) -> int:
    """
    Derive the next logical tick from the event log history.
    If log is empty, start at 1.
    If log exists, next tick is max(poll_tick_id) + 1.
    """
    if not events:
        return 1
    
    # Assumes events are RawShadowEvent objects
    max_tick = 0
    for e in events:
        if e.poll_tick_id > max_tick:
            max_tick = e.poll_tick_id
            
    return max_tick + 1
