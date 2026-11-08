import streamlit as st
import random
import heapq
import pandas as pd
from collections import deque

#symulator systemu kolejkowego zamkniętego (przykład magazynu)
#M/M/m/FIFO/N/F

# kanały obsługi - roboty w magazynie
# źródłą zdarzeń - doki/bramy magazynowe
# max. liczba zdarzeń - zdarzenia już obsługiwane + czekające w kolejce

def simulate(F, m, N, lam, mu, sim_time, seed):
    random.seed(seed)


    events = []
    event_counter = 0
    current_time = 0.0
    queue = deque()
    blocked = deque()
    in_system = 0
    busy_servers = {}

    completed = 0
    waiting_times = []
    system_times = []
    queue_history = [(0.0, 0)]
    system_history = [(0.0, 0)]
    busy_intervals = []

    robot_history = {r: [(0.0, 0)] for r in range(m)}

    def schedule(time, event_type, source, server=None):
        nonlocal event_counter
        event_counter += 1
        heapq.heappush(
            events,
            (time, event_counter, event_type, source, server)
        )

    def admit(source, arrival_time):
        nonlocal in_system
        in_system += 1
        queue.append((source, arrival_time))
        queue_history.append((current_time, len(queue)))
        system_history.append((current_time, in_system))

    def dispatch():
        while queue and len(busy_servers) < m:
            source, arrival_time = queue.popleft()
            server = next(
                s for s in range(m)
                if s not in busy_servers
            )

            wait = current_time - arrival_time
            waiting_times.append(wait)

            service_time = random.expovariate(mu)
            finish_time = current_time + service_time

            busy_servers[server] = (
                source, arrival_time, current_time
            )
            # Robot staje się zajęty (1)
            robot_history[server].append((current_time, 1))

            queue_history.append((current_time, len(queue)))

            schedule(
                finish_time,
                "departure",
                source,
                server
            )

    # Początkowe zgłoszenia ze wszystkich źródeł
    for source in range(F):
        arrival = random.expovariate(lam)
        schedule(arrival, "arrival", source)

    # Główna pętla symulacyjna
    while events:
        event = heapq.heappop(events)
        time, _, event_type, source, server = event

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
            old_source, arrival_time, start_time = busy_servers.pop(server)

            busy_intervals.append((start_time, time))
            system_times.append(time - arrival_time)
            in_system -= 1

            # Robot staje się wolny (0)
            robot_history[server].append((current_time, 0))

            # Źródło generuje kolejne zgłoszenie
            next_arrival = time + random.expovariate(lam)
            schedule(next_arrival, "arrival", old_source)

            if blocked:
                blocked_source, blocked_time = blocked.popleft()
                admit(blocked_source, blocked_time)

            system_history.append((time, in_system))
            dispatch()

    # Wykorzystanie robotów
    total_busy = 0.0
    for start, end in busy_intervals:
        total_busy += max(0.0, min(end, sim_time) - start)

    utilization = (total_busy / (m * sim_time) * 100) if sim_time > 0 else 0
    avg_wait = (sum(waiting_times) / len(waiting_times)) if waiting_times else 0
    avg_system = (sum(system_times) / len(system_times)) if system_times else 0

    avg_queue = (
        sum(
            queue_history[i][1] * (queue_history[i + 1][0] - queue_history[i][0])
            for i in range(len(queue_history) - 1)
        ) / sim_time
    ) if sim_time > 0 else 0

    return {
        "completed": completed,
        "avg_wait": avg_wait,
        "avg_system": avg_system,
        "avg_queue": avg_queue,
        "utilization": utilization,
        "queue_history": queue_history,
        "system_history": system_history,
        "robot_history": robot_history,
        "waiting_times": waiting_times,
        "system_times": system_times,
        "remaining": in_system,
        "remaining_queue": len(queue),
        "blocked": len(blocked) + len(queue)
    }


st.set_page_config(
    page_title="Symulator magazynu",
    layout="wide"
)

st.title("Symulator systemu kolejkowego magazynu")
st.markdown(
    "Model M/M/m/FIFO/N/F – symulacja procesu "
)

st.sidebar.header("Parametry symulacji")
F = st.sidebar.number_input("Liczba punktów odbioru (F)", min_value=1, max_value=1000, value=10)
m = st.sidebar.number_input("Liczba robotów (m)", min_value=1, max_value=100, value=3)
N = st.sidebar.number_input("Pojemność systemu (N)", min_value=1, max_value=1000, value=20)
lam = st.sidebar.number_input("Intensywność generowania paczek λ", min_value=0.01, max_value=100.0, value=0.5, step=0.1)
mu = st.sidebar.number_input("Intensywność obsługi paczek μ", min_value=0.01, max_value=100.0, value=1.0, step=0.1)
sim_time = st.sidebar.number_input("Czas symulacji [s]", min_value=1, max_value=100000, value=100)
seed = st.sidebar.number_input("Ziarno generatora losowego", min_value=0, max_value=999999, value=42)

st.sidebar.divider()
run = st.sidebar.button("ROZPOCZNIJ SYMULACJĘ", type="primary", use_container_width=True)

if run:
    if N < 1 or m < 1 or F < 1:
        st.error("Nieprawidłowe parametry.")
    else:
        with st.spinner("Trwa symulacja procesu magazynowania..."):
            result = simulate(
                int(F), int(m), int(N),
                float(lam), float(mu), float(sim_time), int(seed)
            )

        st.success("Symulacja została zakończona!")

        # Wskaźniki
        st.header("Wyniki symulacji")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Obsłużone paczki", result["completed"])
        c2.metric("Średni czas oczekiwania", f'{result["avg_wait"]:.2f} s')
        c3.metric("Średni czas w systemie", f'{result["avg_system"]:.2f} s')
        c4.metric("Wykorzystanie robotów", f'{result["utilization"]:.2f}%')

        c5, c6, c7 = st.columns(3)
        c5.metric("Średnia długość kolejki", f'{result["avg_queue"]:.2f}')
        c6.metric("Paczki w systemie na koniec", result["remaining"])
        c7.metric("Paczki w kolejce na koniec", result["remaining_queue"])

        st.divider()

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
        st.line_chart(
            df_system_seconds,
            x_label="Czas symulacji [s]",
            y_label="Liczba paczek",
            height=400
        )

        df_robots_seconds = pd.DataFrame(index=second_grid)
        df_robots_seconds.index.name = "Czas [s]"

        for r in range(int(m)):
            r_df = pd.DataFrame(result["robot_history"][r], columns=["Czas", f"Robot {r+1}"]).drop_duplicates(subset=["Czas"], keep="last")
            all_r_times = sorted(set(second_grid).union(r_df["Czas"]))
            r_combined = pd.DataFrame(index=all_r_times).join(r_df.set_index("Czas")).ffill().fillna(0)
            df_robots_seconds[f"Robot {r+1}"] = r_combined.loc[second_grid, f"Robot {r+1}"].astype(int)


        st.subheader("Status poszczególnych robotów w czasie (co 1s)")
        st.caption("Wartość **1** oznacza stan **zajęty** (obsługa zgłoszenia), **0** oznacza stan **wolny**.")

        for r in range(int(m)):
            col_name = f"Robot {r + 1}"
            df_single_robot = df_robots_seconds[[col_name]]
            
            st.markdown(f"##### {col_name}")
            st.line_chart(
                df_single_robot,
                x_label="Czas symulacji [s]",
                y_label="Status (0/1)",
                height=180
            )

        with st.expander("Zobacz tabelę stanów robotów sekunda po sekundzie"):
            st.dataframe(df_robots_seconds, use_container_width=True)


        st.subheader("Rozkład czasów oczekiwania")

        if result["waiting_times"]:
            total_samples = len(result["waiting_times"])

            s_wait = pd.Series(result["waiting_times"])
            bins = pd.cut(s_wait, bins=15)
            counts = bins.value_counts().sort_index()
            counts.index = [f"{interval.left:.1f} – {interval.right:.1f} s" for interval in counts.index]
            
            df_chart = pd.DataFrame({"Liczba paczek": counts})
            st.bar_chart(df_chart)

            # Suma próbek pod wykresem
            st.caption(f"**Łączna liczba zarejestrowanych próbek w rozkładzie:** {total_samples}")
        else:
            st.info("Brak zarejestrowanych czasów oczekiwania.")