"""Static artifact viewer for completed Lathe builds (BL-36, Plan 08 Phase 7).

``lathe serve <build_dir>`` starts a stdlib ``http.server`` that serves
``lathe/viewer/static/`` plus the asset's ``.glb`` at ``/asset.glb``.
The ``<model-viewer>`` web component is vendored via CDN; see
``static/index.html`` for the URL and pin instructions.
"""

from __future__ import annotations

import http.server
import socketserver
from pathlib import Path
from typing import Any

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _find_glb(build_dir: Path) -> Path | None:
    stages_pkg = build_dir / "stages" / "package"
    if stages_pkg.is_dir():
        for candidate in sorted(stages_pkg.glob("*.glb")):
            return candidate
    for candidate in sorted(build_dir.rglob("*.glb")):
        return candidate
    return None


def build_handler_class(build_dir: Path, static_dir: Path = STATIC_DIR) -> type:
    """Return a ``SimpleHTTPRequestHandler`` subclass bound to ``build_dir``.

    Serves files from ``static_dir`` and exposes the build's ``.glb``
    at ``/asset.glb``.
    """
    build_dir = Path(build_dir).resolve()
    static_dir = Path(static_dir).resolve()
    glb_path = _find_glb(build_dir)

    class ViewerHandler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:  # pragma: no cover - thin shim
            if path.split("?", 1)[0].split("#", 1)[0] == "/asset.glb":
                if glb_path is None or not glb_path.exists():
                    return str(static_dir / "__missing_asset__")
                return str(glb_path)
            self.directory = str(static_dir)
            return super().translate_path(path)

        def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover
            return

    ViewerHandler.directory = str(static_dir)  # type: ignore[attr-defined]
    ViewerHandler.build_dir = build_dir  # type: ignore[attr-defined]
    ViewerHandler.glb_path = glb_path  # type: ignore[attr-defined]
    return ViewerHandler


def serve(build_dir: Path, port: int = 8765) -> None:
    """Block-serve the viewer against ``build_dir`` on ``port``."""
    handler_cls = build_handler_class(Path(build_dir))
    with socketserver.TCPServer(("127.0.0.1", int(port)), handler_cls) as httpd:
        print(f"Serving lathe viewer on http://127.0.0.1:{port}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


__all__ = ["STATIC_DIR", "build_handler_class", "serve"]
