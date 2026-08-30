"""Safe installed-font selection for Chinese matplotlib labels."""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def configure_chinese_matplotlib() -> str:
    import matplotlib
    from matplotlib import font_manager

    candidates = (
        "Microsoft YaHei",
        "Microsoft JhengHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
    )
    installed = {font.name for font in font_manager.fontManager.ttflist}
    selected = next((name for name in candidates if name in installed), "DejaVu Sans")
    matplotlib.rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    return selected
