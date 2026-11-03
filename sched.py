#!/usr/bin/env python3
"""Симулятор FCFS, SJF, SRTF, RR и вытесняющего Priority с aging."""
import argparse
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Process:
    pid: str
    arrival: int
    burst: int
    priority: int


def pidkey(pid):
    m = re.search(r'\d+$', pid)
    return (int(m.group()) if m else 10**9, pid)


def read_processes(filename):
    processes = []
    for line in Path(filename).read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        pid, arrival, burst, priority = line.split()
        p = Process(pid, int(arrival), int(burst), int(priority))
        if p.arrival < 0 or p.burst <= 0:
            raise ValueError(f'Неверные данные: {p}')
        processes.append(p)
    if not processes or len({p.pid for p in processes}) != len(processes):
        raise ValueError('Нужны уникальные PID и хотя бы одна запись')
    return processes


def simulate(processes, algorithm, **params):
    """Вернуть [(start, end, pid|None), ...] с объединёнными соседними тактами."""
    algorithm = algorithm.lower()
    if algorithm not in ('fcfs', 'sjf', 'srtf', 'priority', 'rr'):
        raise ValueError('Алгоритм: fcfs, sjf, srtf, priority, rr')
    quantum = int(params.get('quantum', 3))
    aging = int(params.get('aging', 0))
    if quantum < 1 or aging < 0:
        raise ValueError('quantum >= 1, aging >= 0')
    by_id = {p.pid: p for p in processes}
    remaining = {p.pid: p.burst for p in processes}
    waited = {p.pid: 0 for p in processes}
    arrivals = sorted(processes, key=lambda p: (p.arrival, pidkey(p.pid)))
    idx, t = 0, 0
    current = None
    ticks_current = 0
    ready = deque()  # используется только в RR
    timeline = []

    def add_arrivals(now):
        nonlocal idx
        while idx < len(arrivals) and arrivals[idx].arrival <= now:
            if algorithm == 'rr':
                ready.append(arrivals[idx].pid)
            idx += 1

    def append_tick(pid):
        if timeline and timeline[-1][2] == pid and timeline[-1][1] == t:
            start, _, _ = timeline[-1]
            timeline[-1] = (start, t + 1, pid)
        else:
            timeline.append((t, t + 1, pid))

    while any(v > 0 for v in remaining.values()):
        add_arrivals(t)
        active = [p for p in processes if p.arrival <= t and remaining[p.pid] > 0]
        if not active:
            append_tick(None)
            t += 1
            continue
        if algorithm == 'rr':
            if current is None:
                current = ready.popleft()
                ticks_current = 0
            selected = current
        elif algorithm in ('fcfs', 'sjf') and current is not None:
            selected = current
        elif algorithm == 'fcfs':
            selected = min(active, key=lambda p: (p.arrival, pidkey(p.pid))).pid
        elif algorithm == 'sjf':
            selected = min(active, key=lambda p: (p.burst, p.arrival, pidkey(p.pid))).pid
        elif algorithm == 'srtf':
            best = min(active, key=lambda p: (remaining[p.pid], p.arrival, pidkey(p.pid)))
            if current is not None and remaining[current] <= remaining[best.pid]:
                selected = current  # только строго меньший остаток вытесняет
            else:
                selected = best.pid
        else:  # priority, with optional aging of waiting processes
            def effective(p):
                return p.priority - (waited[p.pid] // aging if aging and p.pid != current else 0)
            best = min(active, key=lambda p: (effective(p), p.arrival, pidkey(p.pid)))
            if current is not None and by_id[current].priority <= effective(best):
                selected = current  # равный приоритет не вытесняет
            else:
                selected = best.pid
        if selected != current:
            ticks_current = 0
        current = selected
        append_tick(current)
        remaining[current] -= 1
        ticks_current += 1
        # Старение: ожидающие в очереди повышают эффективный приоритет.
        if algorithm == 'priority':
            for p in active:
                if p.pid != current:
                    waited[p.pid] += 1
            waited[current] = 0
        t += 1
        if algorithm == 'rr':
            # Важно: вновь прибывшие ставятся ПЕРЕД вытесненным в тот же момент.
            add_arrivals(t)
        if remaining[current] == 0:
            current = None
            ticks_current = 0
        elif algorithm == 'rr' and ticks_current == quantum:
            ready.append(current)
            current = None
            ticks_current = 0
    return timeline


def metrics(processes, timeline):
    finish, first = {}, {}
    busy = 0
    switches = 0
    prev = None
    for begin, end, pid in timeline:
        if pid is not None:
            busy += end - begin
            first.setdefault(pid, begin)
            finish[pid] = end
            if prev is not None and pid != prev:
                switches += 1
        prev = pid
    n = len(processes)
    waits = [finish[p.pid] - p.arrival - p.burst for p in processes]
    turns = [finish[p.pid] - p.arrival for p in processes]
    responses = [first[p.pid] - p.arrival for p in processes]
    return {'waiting': sum(waits) / n,
            'turnaround': sum(turns) / n,
            'response': sum(responses) / n,
            'cpu': 100 * busy / max(end for _, end, _ in timeline),
            'switches': switches}


def gantt(timeline):
    return ' '.join(f'[{a}-{b}: {pid or "idle"}]' for a, b, pid in timeline)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    parser.add_argument('--algo', choices=['fcfs','sjf','srtf','priority','rr','all'], default='all')
    parser.add_argument('--quantum', type=int, default=3)
    parser.add_argument('--aging', type=int, default=0, help='Порог старения в тактах, 0=выключено')
    args = parser.parse_args()
    ps = read_processes(args.file)
    print(f'Набор {args.file}: {len(ps)} процессов; RR quantum={args.quantum}; aging={args.aging}')
    print(f'{"Algorithm":<12} {"Waiting":>10} {"Turnaround":>12} {"Response":>10} {"CPU %":>8} {"Switches":>10}')
    algos = ['fcfs','sjf','srtf','priority','rr'] if args.algo=='all' else [args.algo]
    for a in algos:
        tl = simulate(ps, a, quantum=args.quantum, aging=args.aging)
        r = metrics(ps, tl)
        print(f'{a:<12} {r["waiting"]:>10.2f} {r["turnaround"]:>12.2f} {r["response"]:>10.2f} {r["cpu"]:>8.2f} {r["switches"]:>10}')
        if args.algo != 'all':
            print('Диаграмма Ганта:\n', gantt(tl))


if __name__ == '__main__':
    main()
