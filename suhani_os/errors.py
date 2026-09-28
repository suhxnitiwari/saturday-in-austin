"""Custom exceptions: the rules Suhani does not bend on.

Every one inherits from SuhaniError, so a caller can catch one specific rule
(`except PolyesterError`) or all of them at once (`except SuhaniError`).
"""


class SuhaniError(Exception):
    """Base class for every non-negotiable."""


class PolyesterError(SuhaniError):
    """Raised when a garment contains anything other than cotton, linen, wool or silk."""

    def __init__(self, item_name: str, offenders: list) -> None:
        self.offenders = sorted(offenders)
        super().__init__(
            f"{item_name} contains {', '.join(self.offenders)}. "
            "The fabric rule beats the brand, every time."
        )


class NotAGiftError(SuhaniError):
    """Raised when food or flowers are offered as the MAIN gift (they're welcome as extras)."""


class HorrorError(SuhaniError):
    """Raised when someone suggests a horror movie. Absolutely not."""


class OutOfFairyDust(SuhaniError):
    """Raised when mini Sitara has answered her limit of questions for the visit."""
