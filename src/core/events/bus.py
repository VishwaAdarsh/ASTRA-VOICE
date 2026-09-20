"""
ASTRA Central Event Bus.
Provides a thread-safe, priority-queued, decoupled publish-subscribe event broker
with subscriber error isolation, bounded backpressure handling, and graceful shutdown.
"""

from collections import defaultdict
import fnmatch
import logging
import queue
import threading
import time
from typing import Any, Callable

from src.core.events.models import ASTRAEvent, AstraEventType, EventPriority
from src.core.logger import get_logger

logger = get_logger()

SubscriberCallback = Callable[[ASTRAEvent], None]


class EventBus:
    """
    Thread-safe Central Event Bus with Priority Queue and Background Worker.
    Decouples ASTRA subsystems while guaranteeing subscriber error isolation.
    """

    def __init__(self, max_queue_size: int = 1000, start_worker: bool = True, sync_mode: bool = False):
        self.max_queue_size = max_queue_size
        self.sync_mode = sync_mode
        self._queue: queue.PriorityQueue[ASTRAEvent] = queue.PriorityQueue(maxsize=max_queue_size)
        self._subscribers_lock = threading.RLock()

        # Specific event type subscriptions: Dict[str, list[SubscriberCallback]]
        self._exact_subscribers: dict[str, list[SubscriberCallback]] = defaultdict(list)
        # Pattern subscriptions (e.g. "VOICE_*", "*"): Dict[str, list[SubscriberCallback]]
        self._pattern_subscribers: dict[str, list[SubscriberCallback]] = defaultdict(list)

        # Worker thread lifecycle
        self._running = False
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Telemetry metrics
        self._total_published = 0
        self._total_dispatched = 0
        self._total_dropped = 0

        if start_worker and not sync_mode:
            self.start()

    def start(self) -> None:
        """Start the background worker thread for asynchronous event dispatch."""
        with self._subscribers_lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="AstraEventBusWorker",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info("ASTRA Central Event Bus worker thread started.")

    def stop(self, drain: bool = True, timeout: float = 5.0) -> None:
        """Stop the background worker thread, optionally draining queued events."""
        with self._subscribers_lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

        if drain:
            self.drain(timeout=timeout)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                logger.warning("ASTRA Event Bus worker thread did not terminate within timeout.")

        logger.info("ASTRA Central Event Bus stopped.")

    def drain(self, timeout: float = 5.0) -> None:
        """Block until all currently enqueued events have been dispatched or timeout is reached."""
        start_time = time.time()
        while not self._queue.empty():
            if time.time() - start_time > timeout:
                logger.warning(f"EventBus drain timed out with {self._queue.qsize()} events remaining.")
                break
            time.sleep(0.02)

    def subscribe(
        self,
        event_type_or_pattern: AstraEventType | str,
        callback: SubscriberCallback,
    ) -> None:
        """
        Subscribe a callback to an event type or wildcard pattern.
        Supports:
        - Exact type: AstraEventType.VOICE_TRANSCRIBED or "VOICE_TRANSCRIBED"
        - Prefix / Glob: "VOICE_*", "AGENT_*"
        - Global Wildcard: "*"
        """
        pattern = (
            event_type_or_pattern.value
            if isinstance(event_type_or_pattern, AstraEventType)
            else str(event_type_or_pattern)
        )

        with self._subscribers_lock:
            if "*" in pattern or "?" in pattern:
                if callback not in self._pattern_subscribers[pattern]:
                    self._pattern_subscribers[pattern].append(callback)
            else:
                if callback not in self._exact_subscribers[pattern]:
                    self._exact_subscribers[pattern].append(callback)

    def unsubscribe(
        self,
        event_type_or_pattern: AstraEventType | str,
        callback: SubscriberCallback,
    ) -> bool:
        """Unsubscribe a callback from an event type or pattern. Returns True if removed."""
        pattern = (
            event_type_or_pattern.value
            if isinstance(event_type_or_pattern, AstraEventType)
            else str(event_type_or_pattern)
        )

        with self._subscribers_lock:
            removed = False
            if pattern in self._exact_subscribers:
                if callback in self._exact_subscribers[pattern]:
                    self._exact_subscribers[pattern].remove(callback)
                    removed = True
                if not self._exact_subscribers[pattern]:
                    del self._exact_subscribers[pattern]

            if pattern in self._pattern_subscribers:
                if callback in self._pattern_subscribers[pattern]:
                    self._pattern_subscribers[pattern].remove(callback)
                    removed = True
                if not self._pattern_subscribers[pattern]:
                    del self._pattern_subscribers[pattern]

            return removed

    def publish(self, event: ASTRAEvent) -> bool:
        """
        Publish an event asynchronously to the priority queue.
        If sync_mode is True, immediately dispatches synchronously.
        Applies bounded queue backpressure based on event priority.
        Returns True if enqueued/dispatched, False if dropped due to backpressure.
        """
        if self.sync_mode:
            self.publish_sync(event)
            return True

        self._total_published += 1

        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            # Backpressure handling
            if event.priority in (EventPriority.LOW, EventPriority.NORMAL):
                self._total_dropped += 1
                logger.warning(
                    f"EventBus queue full ({self.max_queue_size}). Dropping {event.priority.name} event: {event.event_type}"
                )
                return False
            else:
                # For HIGH and CRITICAL events, attempt to make room by dropping a lower-priority event
                try:
                    # Non-blocking peek/get to evict an item if possible
                    evicted = self._queue.get_nowait()
                    self._total_dropped += 1
                    logger.warning(
                        f"EventBus queue full. Evicted {evicted.priority.name} event '{evicted.event_type}' to make room for {event.priority.name} event '{event.event_type}'."
                    )
                    self._queue.put_nowait(event)
                    return True
                except (queue.Empty, queue.Full):
                    # Fallback to bounded wait for critical events
                    try:
                        self._queue.put(event, timeout=0.5)
                        return True
                    except queue.Full:
                        logger.error(
                            f"EventBus critical failure: Queue full even after timeout. Could not enqueue {event.priority.name} event {event.event_type}"
                        )
                        self._total_dropped += 1
                        return False

    def publish_sync(self, event: ASTRAEvent) -> None:
        """
        Synchronously dispatch an event directly to all matching subscribers.
        Useful for deterministic testing or critical immediate paths.
        """
        self._total_published += 1
        self._dispatch(event)

    def _get_matching_subscribers(self, event_type_str: str) -> list[SubscriberCallback]:
        """Collect all exact and pattern-matched subscribers for an event type."""
        matched: list[SubscriberCallback] = []
        with self._subscribers_lock:
            # Exact matches
            if event_type_str in self._exact_subscribers:
                matched.extend(self._exact_subscribers[event_type_str])

            # Pattern matches (e.g. "VOICE_*", "*")
            for pattern, callbacks in self._pattern_subscribers.items():
                if pattern == "*" or fnmatch.fnmatch(event_type_str, pattern):
                    matched.extend(callbacks)

        # Deduplicate while preserving order
        seen = set()
        unique_callbacks = []
        for cb in matched:
            if cb not in seen:
                seen.add(cb)
                unique_callbacks.append(cb)

        return unique_callbacks

    def _dispatch(self, event: ASTRAEvent) -> None:
        """Dispatch event to matching subscribers with strict error isolation."""
        event_type_str = (
            event.event_type.value
            if isinstance(event.event_type, AstraEventType)
            else str(event.event_type)
        )
        subscribers = self._get_matching_subscribers(event_type_str)

        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                # Subscriber error isolation: handler exceptions must never crash the bus
                cb_name = getattr(callback, "__name__", str(callback))
                logger.error(
                    f"EventBus subscriber '{cb_name}' raised an unhandled exception processing {event.event_type}: {e}",
                    exc_info=True,
                )

        self._total_dispatched += 1

    def _worker_loop(self) -> None:
        """Background thread loop for consuming priority queue events."""
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=0.1)
                self._dispatch(event)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in EventBus worker loop: {e}", exc_info=True)

    def get_metrics(self) -> dict[str, Any]:
        """Return operational metrics of the Event Bus."""
        with self._subscribers_lock:
            total_subscribers = sum(len(cbs) for cbs in self._exact_subscribers.values()) + sum(
                len(cbs) for cbs in self._pattern_subscribers.values()
            )
            return {
                "running": self._running,
                "queue_size": self._queue.qsize(),
                "max_queue_size": self.max_queue_size,
                "total_published": self._total_published,
                "total_dispatched": self._total_dispatched,
                "total_dropped": self._total_dropped,
                "active_subscriber_registrations": total_subscribers,
                "exact_types_subscribed": list(self._exact_subscribers.keys()),
                "patterns_subscribed": list(self._pattern_subscribers.keys()),
            }

    def __enter__(self) -> "EventBus":
        if not self._running:
            self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop(drain=True)
