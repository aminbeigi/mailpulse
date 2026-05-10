import uvicorn

from mailpulse.core.config import get_settings


def main() -> None:
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
