"""
Transcript Miner Module.

Dieses Modul ist für das Herunterladen von Transkripten von YouTube-Kanälen verantwortlich.
"""

# NOTE:
# Dieses Package soll bereits beim einfachen `import transcript_miner` importierbar sein,
# ohne sofort schwere/optionale Dependencies (z.B. google-api-python-client) zu benötigen.
# Deshalb werden öffentliche Symbole lazy über __getattr__ geladen.

__all__ = [
    "ChannelResolver",
    "get_channel_resolver",
    "get_youtube_client",
    "get_channel_by_handle",
    "get_channel_videos",
    "VideoDetails",
    "ChannelInfo",
    "run_miner",
    "main",
]


def __getattr__(name: str):
    """Lazy-Export für öffentliche API.

    Verhindert Import-Fehlschläge in Umgebungen, in denen optionale Runtime-Dependencies
    noch nicht installiert sind (z.B. bei reinen Smoke-Checks).
    """
    if name in {"ChannelResolver", "get_channel_resolver", "get_youtube_client"}:
        from . import channel_resolver as _cr

        return getattr(_cr, name)

    if name in {
        "get_channel_by_handle",
        "get_channel_videos",
        "VideoDetails",
        "ChannelInfo",
    }:
        from . import youtube_client as _yc

        return getattr(_yc, name)

    if name in {"run_miner", "main"}:
        from . import main as _main

        return getattr(_main, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
