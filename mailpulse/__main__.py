"""CLI entry point for running MailPulse with uvicorn.

Invoke via ``python -m mailpulse`` or the ``mailpulse`` console script.
"""

import uvicorn

from mailpulse.core.config import get_settings


def main() -> None:
    """Start the MailPulse HTTP server using settings from the environment."""
    settings = get_settings()
    uvicorn.run(
        "mailpulse.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
