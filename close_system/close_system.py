import streamlit as st
import random
import heapq
import pandas as pd
from collections import deque

# Symulator zamkniętego systemu kolejkowego z obsługą indywidualną (przykład magazynu)
# M/M_i/m/FIFO/N/F  -  każdy robot ma własną intensywność obsługi μ_i
#
# kanały obsługi       - roboty w magazynie (robot i obsługuje z intensywnością μ_i)
# źródła zgłoszeń      - doki/bramy magazynowe (każdy generuje paczki z intensywnością λ)
# N                    - maks. liczba paczek w systemie (w obsłudze + w kolejce)
#
# Ponieważ roboty są różne, liczy się KTÓRY robot dostaje paczkę. Reguła przydziału:
#   - "Kolejność robotów"  - pierwszy wolny robot wg numeru (robot 1 ma pierwszeństwo)
#   - "Najszybszy wolny"   - wolny robot o największym μ_i
#
# Paczka, która przychodzi do pełnego systemu (N paczek), czeka przed wejściem
# (dok jest zablokowany) i wchodzi do kolejki, gdy zwolni się miejsce.

RULE_ORDER = "Kolejność robotów (robot 1 ma pierwszeństwo)"
RULE_FASTEST = "Najszybszy wolny robot (największe μ)"


def robot_priority(mus, rule):
    """Kolejność, w jakiej sprawdzamy wolne roboty przy przydziale paczki."""
    order = list(range(len(mus)))
    if rule == RULE_FASTEST:
        # stabilne sortowanie: przy równych μ decyduje numer robota
        order.sort(key=lambda r: -mus[r])
    return order


# ---------------------------------------------------------------------------
# Symulacja zdarzeń dyskretnych
# ---------------------------------------------------------------------------

def simulate(F, m, N, lam, mus, rule, sim_time, seed):
    random.seed(seed)
    order = robot_priority(mus, rule)

    events = []
    event_counter = 0
    current_time = 0.0
    queue = deque()
    blocked = deque()
    in_system = 0
    busy_servers = {}

    completed = 0
    completed_per_robot = [0] * m
    busy_time = [0.0] * m
    waiting_times = []
    system_times = []
    queue_history = [(0.0, 0)]
    system_history = [(0.0, 0)]

    robot_history = {r: [(0.0, 0)] for r in range(m)}

    def schedule(time, event_type, source, server=None):
        nonlocal event_counter
        event_counter += 1
        heapq.heappush(events, (time, event_counter, event_type, source, server))

    def admit(source, arrival_time):
        nonlocal in_system
        in_system += 1
        queue.append((source, arrival_time))
        queue_history.append((current_time, len(queue)))
        system_history.append((current_time, in_system))

    def dispatch():
        while queue and len(busy_servers) < m:
            source, arrival_time = queue.popleft()
            server = next(s for s in order if s not in busy_servers)

            waiting_times.append(current_time - arrival_time)

            service_time = random.expovariate(mus[server])
            busy_servers[server] = (source, arrival_time, current_time)
            robot_history[server].append((current_time, 1))
            queue_history.append((current_time, len(queue)))

            schedule(current_time + service_time, "departure", source, server)

    for source in range(F):
        schedule(random.expovariate(lam), "arrival", source)

    while events:
        time, _, event_type, source, server = heapq.heappop(events)
        if time > sim_time:
            break
        current_time = time

        if event_type == "arrival":
            if in_system < N:
                admit(source, time)
                dispatch()
            else:
                blocked.append((source, time))

        elif event_type == "departure":
            completed += 1
            completed_per_robot[server] += 1
            old_source, arrival_time, start_time = busy_servers.pop(server)

            busy_time[server] += time - start_time
            system_times.append(time - arrival_time)
            in_system -= 1
            robot_history[server].append((current_time, 0))

            schedule(time + random.expovariate(lam), "arrival", old_source)

            if blocked:
                blocked_source, blocked_time = blocked.popleft()
                admit(blocked_source, blocked_time)

            system_history.append((time, in_system))
            dispatch()

    # Obsługi trwające w chwili końca symulacji też liczą się do czasu pracy
    for server, (_, _, start_time) in busy_servers.items():
        busy_time[server] += sim_time - start_time

    def time_average(history, predicate=None):
        total = 0.0
        points = history + [(sim_time, history[-1][1])]
        for (t0, v), (t1, _) in zip(points, points[1:]):
            value = (1.0 if predicate(v) else 0.0) if predicate else v
            total += value * (t1 - t0)
        return total / sim_time

    util = [bt / sim_time for bt in busy_time]

    return {
        "completed": completed,
        "completed_per_robot": completed_per_robot,
        "throughput": completed / sim_time,
        "util": util,
        "avg_busy": sum(util),
        "avg_wait": (sum(waiting_times) / len(waiting_times)) if waiting_times else 0,
        "avg_system": (sum(system_times) / len(system_times)) if system_times else 0,
        "avg_queue": time_average(queue_history),
        "avg_in_system": time_average(system_history),
        "p0": time_average(system_history, lambda v: v == 0),
        "queue_history": queue_history,
        "system_history": system_history,
        "robot_history": robot_history,
        "waiting_times": waiting_times,
        "remaining": in_system,
        "remaining_queue": len(queue),
    }


# ---------------------------------------------------------------------------
# Interfejs
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Symulator magazynu", layout="wide")

st.title("Symulator systemu kolejkowego magazynu")
st.markdown(
    "Zamknięty system z **obsługą indywidualną** M/M<sub>i</sub>/m/FIFO/N/F – "
    "każdy robot ma własną intensywność obsługi μ<sub>i</sub>.",
    unsafe_allow_html=True,
)

st.sidebar.header("Parametry symulacji")
F = st.sidebar.number_input("Liczba punktów odbioru (F)", min_value=1, max_value=1000, value=10)
m = st.sidebar.number_input("Liczba robotów (m)", min_value=1, max_value=100, value=3)
N = st.sidebar.number_input("Pojemność systemu (N)", min_value=1, max_value=1000, value=20)
lam = st.sidebar.number_input("Intensywność generowania paczek λ (na dok)", min_value=0.01, max_value=100.0, value=0.5, step=0.1)

st.sidebar.subheader("Intensywność obsługi robotów μᵢ")
mus = []
for r in range(int(m)):
    mus.append(st.sidebar.number_input(
        f"Robot {r + 1}: μ{r + 1}",
        min_value=0.01, max_value=100.0,
        value=round(max(0.2, 1.0 - 0.2 * r), 2), step=0.1,
        key=f"mu_{r}",
    ))

rule = st.sidebar.radio("Przydział paczki do wolnego robota", [RULE_ORDER, RULE_FASTEST])

sim_time = st.sidebar.number_input("Czas symulacji [s]", min_value=1, max_value=100000, value=1000)
seed = st.sidebar.number_input("Ziarno generatora losowego", min_value=0, max_value=999999, value=42)

st.sidebar.divider()
run = st.sidebar.button("ROZPOCZNIJ SYMULACJĘ", type="primary", use_container_width=True)

if run:
    F, m, N, sim_time, seed = int(F), int(m), int(N), float(sim_time), int(seed)
    lam = float(lam)
    mus = [float(x) for x in mus]

    with st.spinner("Trwa symulacja procesu magazynowania..."):
        result = simulate(F, m, N, lam, mus, rule, sim_time, seed)

    st.success("Symulacja została zakończona!")

    # ---------------- Wyniki ----------------
    st.header("Wyniki symulacji")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Obsłużone paczki", result["completed"])
    c2.metric("Średni czas oczekiwania", f'{result["avg_wait"]:.2f} s')
    c3.metric("Średni czas w systemie", f'{result["avg_system"]:.2f} s')
    c4.metric("Średnia liczba obsłużonych paczek", f'{result["throughput"]:.3f} /s')

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("P₀ – brak zgłoszeń, roboty bez pracy", f'{result["p0"]:.4f}')
    c6.metric("Średnia liczba zajętych robotów", f'{result["avg_busy"]:.3f}')
    c7.metric("Średnia długość kolejki", f'{result["avg_queue"]:.2f}')
    c8.metric("Średnia liczba paczek w systemie", f'{result["avg_in_system"]:.2f}')

    c9, c10 = st.columns(2)
    c9.metric("Paczki w systemie na koniec", result["remaining"])
    c10.metric("Paczki w kolejce na koniec", result["remaining_queue"])

    st.subheader("Roboty")
    robots = pd.DataFrame({
        "μᵢ": mus,
        "Wykorzystanie": [f"{u:.2%}" for u in result["util"]],
        "Obsłużone paczki": result["completed_per_robot"],
    }, index=[f"Robot {r + 1}" for r in range(m)])
    st.dataframe(robots, use_container_width=True)

    st.divider()

    # ---------------- Przebieg symulacji ----------------
    second_grid = list(range(int(sim_time) + 1))

    df_q = pd.DataFrame(result["queue_history"], columns=["Czas", "Długość kolejki"]).drop_duplicates(subset=["Czas"], keep="last")
    df_s = pd.DataFrame(result["system_history"], columns=["Czas", "Liczba paczek w systemie"]).drop_duplicates(subset=["Czas"], keep="last")

    all_times_sys = sorted(set(second_grid).union(df_q["Czas"]).union(df_s["Czas"]))
    df_sys_combined = pd.DataFrame(index=all_times_sys)
    df_sys_combined = df_sys_combined.join(df_q.set_index("Czas")).join(df_s.set_index("Czas"))
    df_sys_combined = df_sys_combined.ffill().fillna(0)

    df_system_seconds = df_sys_combined.loc[second_grid]
    df_system_seconds.index.name = "Czas [s]"

    st.subheader("Przebieg symulacji magazynu (próbkowanie co 1s)")
    st.line_chart(df_system_seconds, x_label="Czas symulacji [s]", y_label="Liczba paczek", height=400)

    df_robots_seconds = pd.DataFrame(index=second_grid)
    df_robots_seconds.index.name = "Czas [s]"

    for r in range(m):
        r_df = pd.DataFrame(result["robot_history"][r], columns=["Czas", f"Robot {r+1}"]).drop_duplicates(subset=["Czas"], keep="last")
        all_r_times = sorted(set(second_grid).union(r_df["Czas"]))
        r_combined = pd.DataFrame(index=all_r_times).join(r_df.set_index("Czas")).ffill().fillna(0)
        df_robots_seconds[f"Robot {r+1}"] = r_combined.loc[second_grid, f"Robot {r+1}"].astype(int)

    st.subheader("Status poszczególnych robotów w czasie (co 1s)")
    st.caption("Wartość **1** oznacza stan **zajęty** (obsługa zgłoszenia), **0** oznacza stan **wolny**.")

    for r in range(m):
        col_name = f"Robot {r + 1}"
        st.markdown(f"##### {col_name} (μ = {mus[r]})")
        st.line_chart(df_robots_seconds[[col_name]], x_label="Czas symulacji [s]", y_label="Status (0/1)", height=180)

    with st.expander("Zobacz tabelę stanów robotów sekunda po sekundzie"):
        st.dataframe(df_robots_seconds, use_container_width=True)

    st.subheader("Rozkład czasów oczekiwania")
    if result["waiting_times"]:
        s_wait = pd.Series(result["waiting_times"])
        counts = pd.cut(s_wait, bins=15).value_counts().sort_index()
        counts.index = [f"{interval.left:.1f} – {interval.right:.1f} s" for interval in counts.index]
        st.bar_chart(pd.DataFrame({"Liczba paczek": counts}))
        st.caption(f"**Łączna liczba zarejestrowanych próbek w rozkładzie:** {len(s_wait)}")
    else:
        st.info("Brak zarejestrowanych czasów oczekiwania.")
