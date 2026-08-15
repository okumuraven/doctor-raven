"""Identifies what's actually driving CPU load/heat, once the guard trips. Read-only (`ps`), no killing/renicing."""

import subprocess

from doctor_raven.features.system_health.models import ProcessUsage

OLLAMA_PROCESS_NAMES = {"ollama", "ollama_llama_server"}


def top_processes(limit: int = 5) -> list[ProcessUsage]:
    result = subprocess.run(
        ["ps", "-eo", "pid,comm,%cpu", "--sort=-%cpu", "--no-headers"],
        capture_output=True,
        text=True,
        timeout=5,
    )

    processes = []
    for line in result.stdout.splitlines()[:limit]:
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid_str, name, cpu_str = parts
        try:
            processes.append(ProcessUsage(pid=int(pid_str), name=name, cpu_percent=float(cpu_str)))
        except ValueError:
            continue
    return processes


def build_recommendation(processes: list[ProcessUsage]) -> str:
    if not processes:
        return "No process breakdown was available — check `htop`/`ps aux` manually."

    top = processes[0]
    if top.name in OLLAMA_PROCESS_NAMES:
        return (
            f"Local Ollama inference ('{top.name}', {top.cpu_percent:.0f}% CPU) is the top consumer — "
            "this machine is GPU-less, so local generation is CPU-bound. Use `--deep` for the Claude API "
            "instead, or wait for the current run to finish before starting another."
        )

    return (
        f"'{top.name}' (pid {top.pid}, {top.cpu_percent:.0f}% CPU) is the top consumer, not Doctor Raven — "
        "consider closing it or waiting before running another heavy task."
    )
