from src.core.star_components import Event, StarProcess, StarTask
import logging

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self):

        self.process_table: dict[tuple[bytes, bytes], dict[bytes, Event]] = {}
        self.process_table_reverse: dict[tuple[bytes, bytes], dict[Event, bytes]] = {}
        """        
        Process # | Machine # | Origin Event | Most Recent Event
         ------main key-----
                                ---sub key--      
        """

    def add_process(self, proc: StarProcess, peer_id: bytes):
        key = (proc.get_id(), peer_id)
        if key in self.process_table:
            return
        logger.warning(
            f"Add process to monitor: {proc.get_id().hex()} machine: {peer_id.hex()}"
        )

        self.process_table[key] = {}
        self.process_table_reverse[key] = {}

    def add_checkpoint(
        self, peer_id: bytes, origin_event: Event | None, recent_event: Event
    ):
        # Keep first 6 bytes
        process_id = recent_event.target.get_process_id()

        key = (process_id, peer_id)
        logger.debug(key)
        logger.debug(self.process_table)
        if key not in self.process_table:
            raise ValueError("Process + Machine pair not in table!")

        # automatically factors in NONCE

        if origin_event is None:
            origin_event = b""  # type: ignore
            origin_target = b""
            origin_target_nonce = 0
        else:
            origin_target = origin_event.target.get_id()
            origin_target_nonce = origin_event.nonce

        logger.warning(
            f"Add checkpoint: proc: {process_id.hex()} machine: {peer_id.hex()} origin_event: {origin_target.hex()}-{origin_target_nonce} recent-event: {recent_event.target.get_id()}-{recent_event.nonce}"
        )

        self.process_table[key][origin_target] = recent_event
        self.process_table_reverse[key][recent_event] = origin_target
        # delete old records if found.
        if origin_event in self.process_table_reverse[key]:
            old_origin_event = self.process_table_reverse[key][origin_event]
            del self.process_table[key][old_origin_event]
            del self.process_table_reverse[key][origin_event]

    def recall_most_recent_event(
        self, peer_id: bytes, process_id: bytes, task_id: bytes
    ):
        # Keep first 6 bytes

        key = (process_id, peer_id)
        if key not in self.process_table:
            return None

        logger.debug(self.process_table)
        logger.debug(key)
        logger.debug(task_id)

        return self.process_table[key].get(task_id)
