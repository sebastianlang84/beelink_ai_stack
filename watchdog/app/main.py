import argparse
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import docker


HOST_PROC = Path("/host/proc")
HOST_SYS = Path("/host/sys")
HOST_ROOT = Path("/host")


def _env_int(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_float(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def read_cpu_times():
    stat_path = HOST_PROC / "stat"
    with stat_path.open("r", encoding="utf-8") as f:
        line = f.readline().strip()
    parts = line.split()
    if parts[0] != "cpu":
        return None
    values = [int(p) for p in parts[1:]]
    idle = values[3] + values[4] if len(values) > 4 else values[3]
    total = sum(values)
    return total, idle


def read_loadavg():
    try:
        with (HOST_PROC / "loadavg").open("r", encoding="utf-8") as f:
            parts = f.read().strip().split()
        return {
            "load1": float(parts[0]),
            "load5": float(parts[1]),
            "load15": float(parts[2]),
        }
    except Exception:
        return None


def read_temperatures():
    temps = []
    thermal_dir = HOST_SYS / "class" / "thermal"
    if thermal_dir.exists():
        for path in thermal_dir.glob("thermal_zone*/temp"):
            try:
                value = int(path.read_text().strip())
                temps.append(value / 1000.0)
            except Exception:
                continue
    hwmon_dir = HOST_SYS / "class" / "hwmon"
    if hwmon_dir.exists():
        for path in hwmon_dir.glob("hwmon*/temp*_input"):
            try:
                value = int(path.read_text().strip())
                temps.append(value / 1000.0)
            except Exception:
                continue
    if not temps:
        return None
    return {"max_c": max(temps), "min_c": min(temps), "count": len(temps)}


def read_disk_usage():
    try:
        usage = shutil.disk_usage(HOST_ROOT)
        used_pct = (usage.used / usage.total) * 100.0 if usage.total else 0.0
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_pct": round(used_pct, 2),
        }
    except Exception:
        return None


def iter_pids():
    for entry in HOST_PROC.iterdir():
        if entry.is_dir() and entry.name.isdigit():
            yield entry.name


def read_proc_times():
    proc_times = {}
    for pid in iter_pids():
        try:
            stat_path = HOST_PROC / pid / "stat"
            stat_data = stat_path.read_text().split()
            utime = int(stat_data[13])
            stime = int(stat_data[14])
            proc_times[int(pid)] = utime + stime
        except Exception:
            continue
    return proc_times


def read_proc_cmdline(pid):
    try:
        data = (HOST_PROC / str(pid) / "cmdline").read_bytes()
        cmd = data.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
        return cmd or f"[pid:{pid}]"
    except Exception:
        return f"[pid:{pid}]"


def read_proc_rss_kb(pid):
    try:
        statm = (HOST_PROC / str(pid) / "statm").read_text().split()
        rss_pages = int(statm[1])
        page_size = os.sysconf("SC_PAGE_SIZE") // 1024
        return rss_pages * page_size
    except Exception:
        return None


def top_processes(prev_proc_times, prev_total, total):
    if prev_proc_times is None or prev_total is None or total is None:
        return []
    total_delta = max(total - prev_total, 1)
    proc_times = read_proc_times()
    rows = []
    for pid, current in proc_times.items():
        prev = prev_proc_times.get(pid, None)
        if prev is None:
            continue
        delta = current - prev
        if delta <= 0:
            continue
        cpu_pct = (delta / total_delta) * 100.0
        rows.append(
            {
                "pid": pid,
                "cpu_pct": round(cpu_pct, 2),
                "rss_kb": read_proc_rss_kb(pid),
                "cmd": read_proc_cmdline(pid),
            }
        )
    rows.sort(key=lambda r: (r["cpu_pct"], r["rss_kb"] or 0), reverse=True)
    return rows[:5]


def docker_client():
    try:
        return docker.DockerClient(base_url="unix://var/run/docker.sock")
    except Exception:
        return None


def docker_counts(client):
    if client is None:
        return None
    try:
        containers = client.containers.list(all=True)
        running = sum(1 for c in containers if c.status == "running")
        exited = sum(1 for c in containers if c.status in {"exited", "dead"})
        return {"running": running, "exited": exited, "total": len(containers)}
    except Exception:
        return None


def docker_hygiene(client):
    if client is None:
        return None
    try:
        dangling_images = client.images.list(filters={"dangling": True})
        dangling_size = sum(img.attrs.get("Size", 0) for img in dangling_images)
        dangling_volumes = client.volumes.list(filters={"dangling": True})
        dangling_networks = client.networks.list(filters={"dangling": True})
        df = client.df()
        build_cache = df.get("BuildCache", [])
        build_cache_size = sum(item.get("Size", 0) for item in build_cache)
        return {
            "dangling_images_count": len(dangling_images),
            "dangling_images_bytes": dangling_size,
            "dangling_volumes_count": len(dangling_volumes),
            "dangling_networks_count": len(dangling_networks),
            "build_cache_bytes": build_cache_size,
        }
    except Exception:
        return None


def docker_container_stats(client, names):
    if client is None:
        return []
    results = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        try:
            container = client.containers.get(name)
            stats = container.stats(stream=False)
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            cpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) or 1
            cpu_pct = (cpu_delta / system_delta) * cpu_count * 100.0 if system_delta > 0 else 0.0
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 0)
            results.append(
                {
                    "name": name,
                    "cpu_pct": round(cpu_pct, 2),
                    "mem_usage_bytes": mem_usage,
                    "mem_limit_bytes": mem_limit,
                }
            )
        except Exception:
            results.append({"name": name, "error": "stat_failed"})
    return results


def docker_stop_containers(client, names):
    if client is None:
        return []
    results = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        try:
            container = client.containers.get(name)
            container.stop(timeout=10)
            results.append({"name": name, "stopped": True})
        except Exception as exc:
            results.append({"name": name, "stopped": False, "error": str(exc)})
    return results


def write_line(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def format_once_output(sample, top_procs, container_stats, hygiene):
    lines = []
    lines.append(f"ts: {sample.get('ts')}")
    lines.append(f"cpu_pct: {sample.get('cpu_pct')}")
    if sample.get("loadavg"):
        la = sample["loadavg"]
        lines.append(f"loadavg: {la['load1']} {la['load5']} {la['load15']}")
    if sample.get("temperature"):
        temp = sample["temperature"]
        lines.append(
            f"temperature_c: min={temp['min_c']} max={temp['max_c']} sensors={temp['count']}"
        )
    if sample.get("disk"):
        disk = sample["disk"]
        lines.append(
            f"disk: used_pct={disk['used_pct']} used={disk['used_bytes']} free={disk['free_bytes']}"
        )
    if sample.get("docker"):
        d = sample["docker"]
        lines.append(f"docker: running={d['running']} exited={d['exited']} total={d['total']}")

    lines.append("top_processes:")
    if top_procs:
        for row in top_procs:
            lines.append(
                f"  pid={row['pid']} cpu_pct={row['cpu_pct']} rss_kb={row['rss_kb']} cmd={row['cmd']}"
            )
    else:
        lines.append("  (no data)")

    lines.append("container_stats:")
    if container_stats:
        for row in container_stats:
            if "error" in row:
                lines.append(f"  name={row['name']} error={row['error']}")
            else:
                lines.append(
                    f"  name={row['name']} cpu_pct={row['cpu_pct']} mem={row['mem_usage_bytes']}/{row['mem_limit_bytes']}"
                )
    else:
        lines.append("  (no data)")

    if hygiene:
        lines.append("docker_hygiene:")
        lines.append(
            "  "
            + " ".join(
                [
                    f"dangling_images={hygiene.get('dangling_images_count')}",
                    f"dangling_volumes={hygiene.get('dangling_volumes_count')}",
                    f"dangling_networks={hygiene.get('dangling_networks_count')}",
                    f"build_cache_bytes={hygiene.get('build_cache_bytes')}",
                ]
            )
        )

    return "\n".join(lines)


def run_once(container_names):
    client = docker_client()
    prev_total_idle = read_cpu_times()
    prev_total, prev_idle = (prev_total_idle or (None, None))
    prev_proc_times = read_proc_times()
    time.sleep(0.5)
    total_idle = read_cpu_times()
    total, idle = (total_idle or (None, None))
    cpu_pct = None
    if total is not None and idle is not None and prev_total is not None and prev_idle is not None:
        total_delta = max(total - prev_total, 1)
        idle_delta = max(idle - prev_idle, 0)
        cpu_pct = round((1.0 - (idle_delta / total_delta)) * 100.0, 2)

    sample = {
        "ts": now_iso(),
        "type": "once",
        "cpu_pct": cpu_pct,
        "loadavg": read_loadavg(),
        "temperature": read_temperatures(),
        "disk": read_disk_usage(),
        "docker": docker_counts(client),
    }
    top_procs = top_processes(prev_proc_times, prev_total, total)
    container_stats = docker_container_stats(client, container_names)
    hygiene = docker_hygiene(client)
    print(format_once_output(sample, top_procs, container_stats, hygiene))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="print one sample to stdout")
    args = parser.parse_args()

    interval_sec = _env_int("WATCHDOG_INTERVAL_SEC", 900)
    burst_sec = _env_int("WATCHDOG_BURST_SEC", 20)
    burst_interval_sec = _env_int("WATCHDOG_BURST_INTERVAL_SEC", 2)
    hygiene_interval_sec = _env_int("WATCHDOG_HYGIENE_INTERVAL_SEC", 21600)
    cpu_threshold = _env_float("WATCHDOG_CPU_THRESHOLD_PCT", 90)
    temp_threshold = _env_float("WATCHDOG_TEMP_THRESHOLD_C", 85)
    disk_threshold = _env_float("WATCHDOG_DISK_THRESHOLD_PCT", 90)
    temp_stop_threshold = _env_float("WATCHDOG_TEMP_STOP_THRESHOLD_C", 60)
    temp_stop_consec = _env_int("WATCHDOG_TEMP_STOP_CONSEC", 2)
    log_path = os.getenv("WATCHDOG_LOG_PATH", "/data/watchdog.log.jsonl")
    alert_path = os.getenv("WATCHDOG_ALERT_PATH", "/data/watchdog.alert.jsonl")
    container_names = os.getenv("WATCHDOG_CONTAINER_NAMES", "owui,tm,context6,qdrant")
    container_names = [name.strip() for name in container_names.split(",") if name.strip()]
    temp_stop_container_names = os.getenv("WATCHDOG_TEMP_STOP_CONTAINER_NAMES", "owui")
    temp_stop_container_names = [
        name.strip() for name in temp_stop_container_names.split(",") if name.strip()
    ]

    if args.once:
        run_once(container_names)
        return

    client = docker_client()

    last_total = None
    last_idle = None
    last_proc_times = None
    last_disk_used = None
    last_hygiene = 0
    temp_consec = 0

    while True:
        total_idle = read_cpu_times()
        total, idle = (total_idle or (None, None))
        prev_total = last_total
        prev_idle = last_idle
        cpu_pct = None
        if total is not None and idle is not None and prev_total is not None and prev_idle is not None:
            total_delta = max(total - prev_total, 1)
            idle_delta = max(idle - prev_idle, 0)
            cpu_pct = round((1.0 - (idle_delta / total_delta)) * 100.0, 2)
        last_total = total
        last_idle = idle

        loadavg = read_loadavg()
        temp = read_temperatures()
        disk = read_disk_usage()

        disk_delta = None
        if disk and last_disk_used is not None:
            disk_delta = disk["used_bytes"] - last_disk_used
        if disk:
            last_disk_used = disk["used_bytes"]

        docker_stats = docker_counts(client)

        payload = {
            "ts": now_iso(),
            "type": "sample",
            "cpu_pct": cpu_pct,
            "loadavg": loadavg,
            "temperature": temp,
            "disk": disk,
            "disk_used_delta_bytes": disk_delta,
            "docker": docker_stats,
        }
        write_line(log_path, payload)

        trigger = False
        reasons = []
        if cpu_pct is not None and cpu_pct >= cpu_threshold:
            trigger = True
            reasons.append(f"cpu_pct>={cpu_threshold}")
        if temp and temp["max_c"] >= temp_threshold:
            trigger = True
            reasons.append(f"temp_max>={temp_threshold}")
        if disk and disk["used_pct"] >= disk_threshold:
            trigger = True
            reasons.append(f"disk_used_pct>={disk_threshold}")

        if trigger:
            burst_end = time.time() + burst_sec
            while time.time() < burst_end:
                burst_total_idle = read_cpu_times()
                burst_total, _ = (burst_total_idle or (None, None))
                top_procs = top_processes(last_proc_times, prev_total, burst_total)
                container_stats = docker_container_stats(client, container_names)
                alert_payload = {
                    "ts": now_iso(),
                    "type": "burst",
                    "reasons": reasons,
                    "top_processes": top_procs,
                    "container_stats": container_stats,
                }
                write_line(alert_path, alert_payload)
                time.sleep(burst_interval_sec)

        if temp and temp_stop_consec > 0:
            if temp["max_c"] >= temp_stop_threshold:
                temp_consec += 1
            else:
                temp_consec = 0
            if temp_consec >= temp_stop_consec and temp_stop_container_names:
                stop_results = docker_stop_containers(client, temp_stop_container_names)
                stop_payload = {
                    "ts": now_iso(),
                    "type": "action",
                    "action": "stop_containers_temp_threshold",
                    "temp_max_c": temp["max_c"],
                    "threshold_c": temp_stop_threshold,
                    "consecutive": temp_consec,
                    "containers": stop_results,
                }
                write_line(alert_path, stop_payload)
                temp_consec = 0

        now_ts = time.time()
        if hygiene_interval_sec > 0 and now_ts - last_hygiene >= hygiene_interval_sec:
            hygiene_payload = {
                "ts": now_iso(),
                "type": "hygiene",
                "docker_hygiene": docker_hygiene(client),
            }
            write_line(log_path, hygiene_payload)
            last_hygiene = now_ts

        last_proc_times = read_proc_times()
        time.sleep(interval_sec)


if __name__ == "__main__":
    main()
