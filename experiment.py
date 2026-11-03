#!/usr/bin/env python3
"""Сравнение наборов, RR квантов и демонстрация aging."""
import csv
from pathlib import Path
from sched import Process, metrics, read_processes, simulate


def main():
    rows = []
    for dataset in ('set1.txt', 'set2.txt', 'set3.txt'):
        processes = read_processes(dataset)
        for algorithm in ('fcfs', 'sjf', 'srtf', 'priority', 'rr'):
            m = metrics(processes, simulate(processes, algorithm, quantum=3))
            rows.append([dataset, algorithm, *[round(m[k], 3) for k in ('waiting','turnaround','response','cpu','switches')]])
    with open('comparison.csv', 'w', newline='') as f:
        csv.writer(f).writerows([['dataset', 'algorithm', 'waiting', 'turnaround', 'response', 'cpu_pct', 'switches'], *rows])
    print('comparison.csv — 5 алгоритмов × 3 набора.')
    ps = read_processes('set2.txt')
    rr_rows = []
    for q in range(1, 11):
        result = metrics(ps, simulate(ps, 'rr', quantum=q))
        rr_rows.append((q, result['waiting'], result['switches']))
        print(f'Квант={q:>2}: ожидание={result["waiting"]:.2f}, переключения={result["switches"]}')
    with open('rr_quanta.csv', 'w', newline='') as f:
        csv.writer(f).writerows([['quantum', 'avg_waiting', 'context_switches'], *rr_rows])
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('Для создания PNG установите matplotlib (pip install -r requirements.txt). CSV уже создан.')
    else:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot([r[0] for r in rr_rows], [r[1] for r in rr_rows], 'o-', label='Среднее ожидание')
        ax.set_xlabel('Квант RR')
        ax.set_ylabel('Ожидание (такты)')
        ax2 = ax.twinx()
        ax2.plot([r[0] for r in rr_rows], [r[2] for r in rr_rows], 's--', color='orange', label='Переключения')
        ax2.set_ylabel('Переключения контекста')
        ax.set_title('Round Robin на set2: квант и компромисс')
        fig.tight_layout()
        fig.savefig('rr_quanta.png', dpi=160)
        plt.close(fig)
        print('График rr_quanta.png создан.')
    # 40 высокоприоритетных коротких процессов, ожидает один P0 с приоритетом 10.
    starvation = [Process('P0',0,3,10)] + [Process(f'P{i}',i-1,1,1) for i in range(1,41)]
    base = metrics(starvation, simulate(starvation, 'priority'))
    old = simulate(starvation, 'priority')
    aged = simulate(starvation, 'priority', aging=2)
    no_first = next(start for start, _, pid in old if pid=='P0')
    yes_first = next(start for start, _, pid in aged if pid=='P0')
    print(f'Голодание P0: первый старт без aging={no_first}; с aging(2)={yes_first}')
    print('Старение ускоряет первый запуск P0:', yes_first < no_first)
    assert yes_first < no_first
    # Эталонный контроль set1
    control = read_processes('set1.txt')
    for algorithm, expected in [('srtf',(6.5,13.0)), ('rr',(13.5,20.0)),
                                ('fcfs',(8.75,15.25)), ('sjf',(7.75,14.25)),
                                ('priority',(10.75,17.25))]:
        m = metrics(control, simulate(control, algorithm, quantum=3))
        assert (m['waiting'], m['turnaround']) == expected, (algorithm, m, expected)
    print('Эталон set1: все 5 алгоритмов совпадают.')


if __name__ == '__main__':
    main()
