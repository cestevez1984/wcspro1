from .message import Message


class Transmission:
    """A complete HIS transmission: open record + data record + close record."""

    def __init__(self, open_msg: Message, data_msg: Message, close_msg: Message):
        self.open_msg  = open_msg
        self.data_msg  = data_msg
        self.close_msg = close_msg

    def display(self) -> str:
        return '\n\n'.join([
            self.open_msg.display(),
            self.data_msg.display(),
            self.close_msg.display(),
        ])

