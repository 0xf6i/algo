#!/usr/bin/env python3
"""Interactive terminal visualizer that dynamically discovers and traces
sorting/search algorithms from lab_a/."""

import copy
import importlib.util
import inspect
import io
import os
import random
import sys
import time
from pathlib import Path

ALGO_ROOT = Path(__file__).parent / "lab_a"

# --- ANSI helpers ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

BAR_CHAR = "\u2588"


def clear():
    # ANSI escape — instant, no subprocess spawn
    sys.stdout.write("\033[H\033[2J\033[3J")
    sys.stdout.flush()


# --- Discovery ---


def _load_module(path: Path):
    name = path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Suppress prints during import (e.g. insertion.py prints at module level)
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = old_stdout
    return mod


def _find_main_func(mod):
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if not name.startswith("_") and obj.__module__ == mod.__name__:
            return name, obj
    return None, None


def _func_is_stub(func):
    src = inspect.getsource(func)
    lines = [
        l.strip()
        for l in src.splitlines()
        if l.strip() and not l.strip().startswith(("def ", "#"))
    ]
    return lines == ["pass"] or not lines


def _build_sort_caller(func):
    """Build a callable that invokes a sort function with the right args.

    Handles both func(arr) and func(arr, low, high) style signatures.
    Returns (caller, is_inplace_hint).
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) == 1:
        # func(arr)
        return lambda arr: func(list(arr))
    elif len(params) == 3:
        # func(arr, low, high) — quicksort style, likely in-place
        return lambda arr: (func(a := list(arr), 0, len(a) - 1), a)[-1]
    elif len(params) == 2:
        # func(arr, n) — some algorithms pass length
        return lambda arr: func(list(arr), len(arr))
    else:
        return lambda arr: func(list(arr))


def _build_search_caller(func):
    """Build a callable that invokes a search function with the right args.

    Handles func(arr, t), func(arr, t, i), func(arr, t, lo, hi), etc.
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) == 2:
        return lambda arr, t: func(list(arr), t)
    elif len(params) == 3:
        # func(arr, t, start_index) — like linear_rec(arr, t, 0)
        return lambda arr, t: func(list(arr), t, 0)
    elif len(params) == 4:
        # func(arr, t, low, high) — binary search variant
        return lambda arr, t: func(list(arr), t, 0, len(arr) - 1)
    else:
        return lambda arr, t: func(list(arr), t)


def discover_algorithms():
    """Scan lab_a/sort/ and lab_a/search/ — directory determines type."""
    algos = {"sort": [], "search": []}
    for kind in ("sort", "search"):
        kind_dir = ALGO_ROOT / kind
        if not kind_dir.is_dir():
            continue
        for py_file in sorted(kind_dir.rglob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                mod = _load_module(py_file)
                fname, func = _find_main_func(mod)
                if func is None or _func_is_stub(func):
                    continue
                rel = py_file.relative_to(kind_dir).with_suffix("")
                parts = list(rel.parts)
                label = " / ".join(p.replace("_", " ").title() for p in parts)

                if kind == "sort":
                    caller = _build_sort_caller(func)
                else:
                    caller = _build_search_caller(func)

                algos[kind].append((label, func, caller, py_file))
            except Exception:
                continue
    return algos


# --- Tracing engine ---


def _is_num_list(v):
    return isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v)


def _get_all_module_codes(func):
    """Get all code objects for functions defined in the same file as func."""
    func_file = os.path.abspath(inspect.getfile(func))
    codes = set()
    codes.add(func.__code__)
    # Also find helper functions (like _merge for merge sort)
    # by scanning the module that contains func
    for obj in func.__globals__.values():
        if inspect.isfunction(obj):
            try:
                if os.path.abspath(inspect.getfile(obj)) == func_file:
                    codes.add(obj.__code__)
            except (TypeError, OSError):
                continue
    return func_file, codes


def trace_sort(func, caller, arr):
    """Run a sort function, capturing snapshots at every line.

    For in-place sorts: tracks the main array.
    For recursive sorts: tracks all sub-arrays and reconstructs progress.

    Returns list of (display_arr, highlights, lineno, src_line, locals_info).
    """
    n = len(arr)
    func_file, valid_codes = _get_all_module_codes(func)
    source_lines = inspect.getsource(func).splitlines()
    _, func_start = inspect.getsourcelines(func)

    # We keep a flat "canvas" representing the full array state.
    # For in-place sorts, it's directly the working array.
    # For recursive sorts, we update slices as sub-calls return.
    canvas = list(arr)
    frames = []
    prev_canvas = None
    # Stack of (offset, initial_arr_snapshot) per call frame
    call_stack_arrs = []
    # Track each frame's initial array value so we can detect true in-place mutations
    frame_initial_arr = {}  # id(frame) -> list snapshot

    def _find_offset(sub_vals):
        """Find where a sub-array sits within canvas by matching a contiguous
        region with the same multiset of values."""
        m = len(sub_vals)
        sub_sorted = sorted(sub_vals)
        for start in range(n - m + 1):
            if sorted(canvas[start : start + m]) == sub_sorted:
                return start
        return None

    def tracer(frame, event, arg):
        nonlocal prev_canvas
        if frame.f_code not in valid_codes:
            return tracer

        if event == "call":
            # Track array argument for recursion offset detection
            arr_param = None
            for v in frame.f_locals.values():
                if _is_num_list(v):
                    arr_param = list(v)
                    break
            if arr_param and len(arr_param) < n:
                offset = _find_offset(arr_param)
                call_stack_arrs.append((offset, arr_param))
            else:
                call_stack_arrs.append((0, arr_param))
            # Snapshot the full-length array param so we can detect mutations
            if arr_param and len(arr_param) == n:
                frame_initial_arr[id(frame)] = list(arr_param)
            return tracer

        if event == "return":
            frame_initial_arr.pop(id(frame), None)
            if call_stack_arrs:
                offset, original_sub = call_stack_arrs.pop()
            else:
                offset, original_sub = 0, None

            # If function returned a list, update canvas at the right offset
            if _is_num_list(arg) and len(arg) <= n and offset is not None:
                for i, v in enumerate(arg):
                    if offset + i < n:
                        canvas[offset + i] = v
                _record(frame, arg)
            return tracer

        if event != "line":
            return tracer

        # Find a full-length array in locals (for in-place sorts)
        local_arr = None
        for v in frame.f_locals.values():
            if isinstance(v, list) and len(v) == n and _is_num_list(v):
                local_arr = v
                break

        if local_arr is not None:
            local_snap = list(local_arr)
            initial = frame_initial_arr.get(id(frame))
            # Only update canvas if the array has been mutated from its
            # initial value (true in-place sort). If it still matches what
            # was passed in, it's an unchanged parameter — skip it to avoid
            # regressing canvas for recursive sorts.
            if initial is None or local_snap != initial:
                if local_snap != canvas:
                    for i in range(n):
                        canvas[i] = local_snap[i]

        _record(frame, None)
        return tracer

    main_code = func.__code__
    prev_lineno = [None]
    prev_locals = [None]

    def _record(frame, returned_arr):
        nonlocal prev_canvas
        lineno = frame.f_lineno - func_start
        src = source_lines[lineno].strip() if 0 <= lineno < len(source_lines) else ""

        snap = list(canvas)
        changed = set()
        if prev_canvas is not None:
            for i in range(n):
                if snap[i] != prev_canvas[i]:
                    changed.add(i)

        if changed:
            prev_canvas = list(snap)

        # Build a compact locals summary
        interesting = {}
        for k, v in frame.f_locals.items():
            if k.startswith("_"):
                continue
            if isinstance(v, (int, float)):
                interesting[k] = v
            elif _is_num_list(v) and len(v) < n:
                interesting[k] = v

        # For helper functions (not the main algo), only record when array changed
        in_main = frame.f_code is main_code
        if not in_main and not changed:
            return

        # Skip if nothing visibly changed (same line, same vars, same array)
        if lineno == prev_lineno[0] and interesting == prev_locals[0] and not changed:
            return

        # Skip if only the line changed but vars and array are identical
        # (e.g. loop header re-evaluation with no state change)
        if not changed and interesting == prev_locals[0] and lineno != prev_lineno[0]:
            # Still update lineno so the next real change is recorded
            prev_lineno[0] = lineno
            return

        prev_lineno[0] = lineno
        prev_locals[0] = dict(interesting)
        frames.append((list(snap), changed, lineno, src, interesting))

    old_trace = sys.gettrace()
    sys.settrace(tracer)
    try:
        result = caller(arr)
    finally:
        sys.settrace(old_trace)

    # Final frame
    if isinstance(result, list):
        for i, v in enumerate(result):
            if i < n:
                canvas[i] = v
    final = list(canvas)
    frames.append((final, set(range(n)), -1, "done", {}))
    return frames


SEARCH_POINTER_NAMES = {"low", "high", "mid", "left", "right", "i", "j", "start", "end"}


def trace_search(func, caller, arr, target):
    """Run a search function, capturing pointer state at each line."""
    func_file, valid_codes = _get_all_module_codes(func)
    source_lines = inspect.getsource(func).splitlines()
    _, func_start = inspect.getsourcelines(func)
    frames = []
    prev_lineno = [None]
    prev_ptrs = [None]

    def tracer(frame, event, arg):
        if frame.f_code not in valid_codes:
            return tracer
        if event not in ("line",):
            return tracer

        lineno = frame.f_lineno - func_start
        src = source_lines[lineno].strip() if 0 <= lineno < len(source_lines) else ""

        pointers = {}
        for name in SEARCH_POINTER_NAMES:
            if name in frame.f_locals and isinstance(frame.f_locals[name], int):
                pointers[name] = frame.f_locals[name]

        # Skip if nothing visibly changed
        if lineno == prev_lineno[0] and pointers == prev_ptrs[0]:
            return tracer

        prev_lineno[0] = lineno
        prev_ptrs[0] = dict(pointers)
        frames.append((dict(pointers), lineno, src))
        return tracer

    old_trace = sys.gettrace()
    sys.settrace(tracer)
    try:
        result = caller(arr, target)
    finally:
        sys.settrace(old_trace)

    return frames, result


# --- Rendering ---


def colored_bar(value, max_val, color=CYAN, width=50):
    bar_len = int((value / max_val) * width) if max_val else 0
    return f"{color}{BAR_CHAR * bar_len}{RESET}"


def _render_source_with_vars(source_lines, lineno, locals_info):
    """Render source code with current line highlighted and variable values
    shown inline to the right of the executing line."""
    lines = []
    # Find the max source line length for alignment
    raw_lengths = [len(sl) for sl in source_lines]
    pad_to = min(max(raw_lengths) + 4, 60) if raw_lengths else 40

    lines.append(f"  {BOLD}Source:{RESET}")
    for i, sl in enumerate(source_lines):
        if i == lineno:
            padded = sl.ljust(pad_to)
            # Show variable values inline next to the current line
            if locals_info:
                var_str = "  ".join(f"{k}={v}" for k, v in locals_info.items())
                lines.append(
                    f"  {YELLOW}{BOLD} > {padded}{RESET}  {MAGENTA}{var_str}{RESET}"
                )
            else:
                lines.append(f"  {YELLOW}{BOLD} > {sl}{RESET}")
        else:
            lines.append(f"  {DIM}   {sl}{RESET}")
    lines.append("")

    # Variable table below source
    if locals_info:
        lines.append(f"  {BOLD}Variables:{RESET}")
        for k, v in locals_info.items():
            lines.append(f"    {WHITE}{k:>12}{RESET} = {CYAN}{BOLD}{v}{RESET}")
        lines.append("")

    return lines


def render_sort_frame(
    arr, max_val, changed, label, src_line, lineno, source_lines, locals_info
):
    lines = []
    lines.append(f"\n  {BOLD}{CYAN}{label}{RESET}")
    lines.append("")

    # Source with inline vars
    lines.extend(_render_source_with_vars(source_lines, lineno, locals_info))

    # Array bars
    lines.append(f"  {BOLD}Array:{RESET}")
    for i, v in enumerate(arr):
        color = GREEN if i in changed else CYAN
        idx_str = f"  {DIM}[{i:>2}]{RESET}"
        val_str = f" {v:>3} "
        bar = colored_bar(v, max_val, color)
        lines.append(f"{idx_str}{val_str}{bar}")
    lines.append("")
    return "\n".join(lines)


def render_search_frame(arr, target, pointers, label, src_line, lineno, source_lines):
    lines = []
    lines.append(
        f"\n  {BOLD}{CYAN}{label}{RESET}    target = {YELLOW}{BOLD}{target}{RESET}"
    )
    lines.append("")

    # Source with inline vars — pointers are the interesting variables here
    locals_info = {k: v for k, v in pointers.items()}
    lines.extend(_render_source_with_vars(source_lines, lineno, locals_info))

    # Pointer labels
    ptr_line = "        "
    for i in range(len(arr)):
        labels_here = [name for name, idx in pointers.items() if idx == i]
        if labels_here:
            ptr_line += f" {MAGENTA}{BOLD}{','.join(labels_here):^5}{RESET}"
        else:
            ptr_line += "      "
    lines.append(ptr_line)

    # Array cells
    cell_line = "        "
    active = set(pointers.values())
    mid_idx = pointers.get("mid")
    lo = pointers.get("low", 0)
    hi = pointers.get("high", len(arr) - 1)
    for i, v in enumerate(arr):
        if i == mid_idx:
            color = YELLOW
        elif i in active:
            color = MAGENTA
        elif "low" in pointers and (i < lo or i > hi):
            color = DIM
        else:
            color = WHITE
        cell_line += f" {color}{BOLD}[{v:>2}]{RESET} "
    lines.append(cell_line)

    # Index labels
    idx_line = "        "
    for i in range(len(arr)):
        idx_line += f" {DIM} {i:>2}  {RESET}"
    lines.append(idx_line)
    lines.append("")
    return "\n".join(lines)


# --- Interactive runner ---


def get_speed():
    print(f"\n  {BOLD}Speed:{RESET}")
    print(f"    1) Fast    (0.2s)")
    print(f"    2) Medium  (0.5s)")
    print(f"    3) Slow    (1.0s)")
    print(f"    s) Step-by-step (press Enter)")
    choice = input(f"\n  > ").strip()
    speeds = {"1": 0.2, "2": 0.5, "3": 1.0}
    if choice == "s":
        return None
    return speeds.get(choice, 0.5)


def get_sort_array():
    print(f"\n  {BOLD}Array:{RESET}")
    print(f"    1) Random (10 elements)")
    print(f"    2) Nearly sorted")
    print(f"    3) Reversed")
    print(f"    4) Custom")
    choice = input(f"\n  > ").strip()
    if choice == "1":
        return random.sample(range(1, 51), 10)
    elif choice == "2":
        a = list(range(1, 11))
        a[3], a[7] = a[7], a[3]
        a[1], a[5] = a[5], a[1]
        return a
    elif choice == "3":
        return list(range(10, 0, -1))
    elif choice == "4":
        raw = input(f"  Enter numbers separated by spaces: ").strip()
        return [int(x) for x in raw.split()]
    return random.sample(range(1, 51), 10)


def get_search_array_and_target():
    print(f"\n  {BOLD}Array:{RESET}")
    print(f"    1) Random sorted (15 elements)")
    print(f"    2) Custom")
    choice = input(f"\n  > ").strip()
    if choice == "2":
        raw = input(f"  Enter sorted numbers separated by spaces: ").strip()
        arr = [int(x) for x in raw.split()]
    else:
        arr = sorted(random.sample(range(1, 100), 15))
    print(f"\n  Array: {arr}")
    raw_t = input(f"  Enter target value: ").strip()
    return arr, int(raw_t)


def run_sort(label, func, caller):
    arr = get_sort_array()
    speed = get_speed()

    source_lines = inspect.getsource(func).splitlines()
    frames = trace_sort(func, caller, arr)

    if not frames:
        print(f"\n  {RED}No frames captured.{RESET}")
        input(f"  {DIM}Press Enter...{RESET}")
        return

    max_val = max(max(f[0]) for f in frames)

    for snap, changed, lineno, src, locals_info in frames:
        clear()
        print(
            render_sort_frame(
                snap, max_val, changed, label, src, lineno, source_lines, locals_info
            )
        )
        if speed is None:
            input(f"  {DIM}[Enter] next step > {RESET}")
        else:
            time.sleep(speed)

    # Final frame
    clear()
    final = frames[-1][0]
    print(
        render_sort_frame(
            final, max_val, set(range(len(final))), label, "done", -1, source_lines, {}
        )
    )
    print(f"  {GREEN}{BOLD}Sorted!{RESET}")
    input(f"\n  {DIM}Press Enter to return to menu...{RESET}")


def run_search(label, func, caller):
    arr, target = get_search_array_and_target()
    speed = get_speed()

    source_lines = inspect.getsource(func).splitlines()
    frames, result = trace_search(func, caller, arr, target)

    if not frames:
        print(f"\n  {RED}No frames captured.{RESET}")
        input(f"  {DIM}Press Enter...{RESET}")
        return

    for pointers, lineno, src in frames:
        clear()
        print(
            render_search_frame(arr, target, pointers, label, src, lineno, source_lines)
        )
        if speed is None:
            input(f"  {DIM}[Enter] next step > {RESET}")
        else:
            time.sleep(speed)

    # Result
    clear()
    last_ptrs = frames[-1][0]
    print(render_search_frame(arr, target, last_ptrs, label, "", -1, source_lines))
    if result is not None and result >= 0:
        print(f"  {GREEN}{BOLD}Found {target} at index {result}{RESET}")
    else:
        print(f"  {RED}{BOLD}{target} not found{RESET}")
    input(f"\n  {DIM}Press Enter to return to menu...{RESET}")


def main():
    while True:
        algos = discover_algorithms()
        sort_algos = algos["sort"]
        search_algos = algos["search"]

        clear()
        print(f"\n  {BOLD}{CYAN}Algorithm Visualizer{RESET}")
        print(f"  {DIM}Auto-discovered from lab_a/{RESET}")
        print(f"  {'=' * 40}\n")

        menu = []
        if sort_algos:
            print(f"  {BOLD}Sorting:{RESET}")
            for i, (label, func, caller, path) in enumerate(sort_algos):
                num = i + 1
                menu.append(("sort", label, func, caller))
                rel = path.relative_to(ALGO_ROOT)
                print(f"    {num}) {label}  {DIM}({rel}){RESET}")
            print()

        if search_algos:
            print(f"  {BOLD}Searching:{RESET}")
            for i, (label, func, caller, path) in enumerate(search_algos):
                num = len(sort_algos) + i + 1
                menu.append(("search", label, func, caller))
                rel = path.relative_to(ALGO_ROOT)
                print(f"    {num}) {label}  {DIM}({rel}){RESET}")
            print()

        if not menu:
            print(f"  {RED}No implemented algorithms found in lab_a/{RESET}")
            print(f"  {DIM}(Stub functions with just `pass` are skipped){RESET}\n")

        print(f"  {DIM}q) Quit{RESET}\n")

        choice = input(f"  > ").strip().lower()
        if choice == "q":
            clear()
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(menu):
                kind, label, func, caller = menu[idx]
                if kind == "sort":
                    run_sort(label, func, caller)
                else:
                    run_search(label, func, caller)
        except (ValueError, IndexError):
            continue


if __name__ == "__main__":
    main()
