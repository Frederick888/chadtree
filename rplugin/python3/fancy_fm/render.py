from enum import IntEnum, auto
from fnmatch import fnmatch
from locale import strxfrm
from os import linesep
from os.path import sep
from typing import Callable, Iterator, Optional, Sequence, Tuple, cast

from .da import constantly
from .types import Index, Mode, Node, QuickFix, Render, Selection, Settings, VCStatus


class CompVals(IntEnum):
    FOLDER = auto()
    FILE = auto()


def comp(node: Node) -> Tuple[int, str, str]:
    node_type = CompVals.FOLDER if Mode.FOLDER in node.mode else CompVals.FILE
    return (
        node_type,
        strxfrm(node.ext or ""),
        strxfrm(node.name),
    )


def ignore(settings: Settings, vc: VCStatus) -> Callable[[Node], bool]:
    def drop(node: Node) -> bool:
        ignore = (
            node.path in vc.ignored
            or any(fnmatch(node.name, pattern) for pattern in settings.name_ignore)
            or any(fnmatch(node.path, pattern) for pattern in settings.path_ignore)
        )
        return ignore

    return drop


def paint(
    settings: Settings,
    index: Index,
    selection: Selection,
    qf: QuickFix,
    vc: VCStatus,
    current: Optional[str],
) -> Callable[[Node, int], Render]:
    icons = settings.icons

    def show_ascii(node: Node, depth: int) -> Render:
        path = node.path
        qf_count = qf.locations[path]
        qf_badge = f"({qf_count})" if qf_count else ""
        stat = vc.status.get(path)

        spaces = (depth * 2 - 1) * " "
        curr = ">" if path == current else " "
        select = "*" if path in selection else " "
        status = f"[{stat}]" if stat else ""
        name = node.name.replace(linesep, r"\n")

        if Mode.FOLDER in node.mode:
            decor = "-" if path in index else "+"
            name = f"{decor} {name}{sep}"
        if Mode.LINK in node.mode:
            name = f"  {name} ->"

        line = f"{spaces}{select}{curr} {name}"
        badge = f"{qf_badge} {status}"
        render = Render(line=line, badge=badge, highlights=())
        return render

    def show_icons(node: Node, depth: int) -> Render:
        path = node.path
        qf_count = qf.locations[path]
        qf_badge = f"({qf_count})" if qf_count else ""
        stat = vc.status.get(path)

        spaces = (depth * 2 - 1) * " "
        curr = "▶" if path == current else " "
        select = "✸" if path in selection else " "
        status = f"[{stat}]" if stat else ""
        name = node.name.replace(linesep, r"\n")

        if Mode.FOLDER in node.mode:
            decor: Optional[
                str
            ] = icons.folder_open if path in index else icons.folder_closed
            name = f"{decor} {name}"
        else:
            decor = icons.filetype.get(node.ext or "") or next(
                (v for k, v in icons.filename.items() if fnmatch(node.name, k)), None
            )
            if decor:
                name = f"{decor} {name}"
            else:
                name = f"  {name}"
        if Mode.LINK in node.mode:
            name = f"{name} {icons.link}"

        line = f"{spaces}{select}{curr} {name}"
        badge = f"{qf_badge} {status}"
        render = Render(line=line, badge=badge, highlights=())
        return render

    show = show_icons if settings.use_icons else show_ascii
    return show


def render(
    node: Node,
    *,
    settings: Settings,
    index: Index,
    selection: Selection,
    qf: QuickFix,
    vc: VCStatus,
    show_hidden: bool,
    current: Optional[str],
) -> Tuple[Sequence[Node], Sequence[Render]]:
    drop = constantly(False) if show_hidden else ignore(settings, vc)
    show = paint(
        settings, index=index, selection=selection, qf=qf, vc=vc, current=current
    )

    def render(node: Node, *, depth: int) -> Iterator[Tuple[Node, Render]]:
        rend = show(node, depth)
        children = (
            child for child in (node.children or {}).values() if not drop(child)
        )
        yield node, rend
        for child in sorted(children, key=comp):
            yield from render(child, depth=depth + 1)

    lookup, rendered = zip(*render(node, depth=0))
    return cast(Sequence[Node], lookup), cast(Sequence[Render], rendered)