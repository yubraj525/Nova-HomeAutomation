from dataclasses import dataclass


@dataclass
class AudioChunk:
    """
    A small piece of PCM audio.

    AudioChunk is the common audio format used between
    TTS, buffering, and audio transport.
    """

    data: bytes

    sample_rate: int = 22050
    channels: int = 1
    sample_width: int = 2

    sequence: int = 0

    @property
    def duration(self) -> float:
        """
        Duration of this audio chunk in seconds.
        """

        if not self.data:
            return 0.0

        bytes_per_second = (
            self.sample_rate
            * self.channels
            * self.sample_width
        )

        return len(self.data) / bytes_per_second