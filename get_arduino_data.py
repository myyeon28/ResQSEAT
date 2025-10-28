# -*- coding: utf-8 -*-
"""Untitled4.ipynb

import os, sys, json, time, glob, threading
from datetime import datetime
from pathlib import Path
import serial
from typing import Dict, Any, Optional

# --- Settings ---
STATIC_PORTS = [
    "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_B0012UVW-if00-port0",
    "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_B0012SAU-if00-port0",
]
BAUD = 115200
LOG_DIR = Path("/home/pi/weight_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

PORT_ALIAS = {
    "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_B0012UVW-if00-port0": "Arduino A",
    "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_B0012SAU-if00-port0": "Arduino B",
}
CAL_STORE_PATH = Path("/home/pi/cal_store.json")

# --- Global variables and locks ---
g_latest_seat_data: Dict[str, Dict[str, Any]] = {}
g_data_lock = threading.Lock()

# --- Utils ---
def load_cal_store():
    if CAL_STORE_PATH.exists():
        try: return json.loads(CAL_STORE_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    return {}

def save_cal_store(store: dict):
    tmp = CAL_STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CAL_STORE_PATH)

def now_utc():
    return datetime.utcnow().isoformat() + "Z"

def open_serial(port):
    """Opens the serial port. (Retries every 1s until connected)"""
    while True:
        try:
            # Increase timeout slightly for command sending robustness
            return serial.Serial(port, BAUD, timeout=2)
        except serial.SerialException as e:
            # If port is busy (e.g., reader thread has it), wait and retry
            if "Resource busy" in str(e):
                # print(f"Port {port} busy, retrying...") # Optional debug print
                time.sleep(0.5)
            else:
                # print(f"Error opening {port}: {e}, retrying...") # Optional debug print
                time.sleep(1)
        except Exception as e:
            # print(f"Unexpected error opening {port}: {e}, retrying...") # Optional debug print
            time.sleep(1)


# --- Reader Thread ---
def reader(port):
    """
    Runs as a background thread, continuously receiving data from Arduino
    and updating the g_latest_seat_data global variable.
    """
    alias = PORT_ALIAS.get(port, Path(port).name)
    log_path = LOG_DIR / (port.replace("/", "_") + ".ndjson")
    # Initialize ser outside the loop
    ser = None
    while ser is None: # Keep trying until port opens
        try:
            ser = serial.Serial(port, BAUD, timeout=1)
            print(f"[{alias}] Serial port opened successfully.")
        except serial.SerialException as e:
             print(f"[{alias}] Failed to open serial port: {e}. Retrying in 2s...")
             time.sleep(2)
        except Exception as e:
            print(f"[{alias}] Unexpected error opening serial port: {e}. Retrying in 2s...")
            time.sleep(2)


    # Auto-reapply 'set_cal'
    try:
        store = load_cal_store()
        cal_data = store.get(alias)
        if cal_data and "cal" in cal_data:
            cal_val = cal_data["cal"]
            cmd = {"cmd": "set_cal", "value": cal_val}
            ser.write((json.dumps(cmd) + "\n").encode("utf-8"))
            ser.flush()
    except Exception as e:
        print(f"[{alias}] Error reapplying set_cal: {e}") # Show error

    last_print = 0
    with open(log_path, "a") as fout:
        while True:
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line: continue
                try: data = json.loads(line)
                except Exception: continue

                data["_recv_ts"] = now_utc()
                data["_alias"] = alias
                data["_port"] = port

                seats_data_in_json = data.get("seats", [])
                if seats_data_in_json:
                    with g_data_lock:
                        for s in seats_data_in_json:
                            seat_name = s.get("name")
                            if seat_name:
                                g_latest_seat_data[seat_name] = {
                                    "Weight": float(s.get("Weight", 0.0)),
                                    "mpu_g": float(s.get("mpu_g", 0.0)),
                                    "_recv_ts_utc": data.get("_recv_ts")
                                }

                fout.write(json.dumps(data) + "\n")
                fout.flush()

            except serial.SerialException as e:
                print(f"[{alias}] Serial error: {e}. Reopening port...") # Show error
                try: ser.close()
                except: pass
                ser = None
                while ser is None: # Keep trying until port reopens
                    try:
                        ser = serial.Serial(port, BAUD, timeout=1)
                        print(f"[{alias}] Serial port reopened successfully.")
                        # Reapply 'set_cal' on reconnect
                        try:
                            store = load_cal_store()
                            cal_data = store.get(alias)
                            if cal_data and "cal" in cal_data:
                                cal_val = cal_data["cal"]
                                cmd = {"cmd": "set_cal", "value": cal_val}
                                ser.write((json.dumps(cmd) + "\n").encode("utf-8"))
                                ser.flush()
                        except Exception as e2:
                             print(f"[{alias}] Error reapplying set_cal after reconnect: {e2}") # Show error
                    except serial.SerialException as e_reopen:
                         print(f"[{alias}] Failed to reopen serial port: {e_reopen}. Retrying in 2s...")
                         time.sleep(2)
                    except Exception as e_reopen:
                         print(f"[{alias}] Unexpected error reopening serial port: {e_reopen}. Retrying in 2s...")
                         time.sleep(2)

            except Exception as e:
                print(f"[{alias}] Unexpected error in reader loop: {e}") # Show error
                time.sleep(0.2)

# --- Command Sending ---
def send_cmd(port, obj):
    """Sends a JSON command to a specific port."""
    s = None
    try:
        # Use open_serial which handles retries and busy ports
        s = open_serial(port)
        if s and s.is_open:
            s.write((json.dumps(obj) + "\n").encode("utf-8"))
            s.flush()
            print(f"Command {obj} sent to {port}") # Confirmation
            s.close() # Close immediately after sending
            return True
        else:
            print(f"Failed to open port {port} to send command.")
            return False
    except Exception as e:
        print(f"ERROR sending command {obj} to {PORT_ALIAS.get(port, port)}: {e}")
        if s and s.is_open:
            s.close()
        return False


def send_tare_command_to_all():
    """Sends the 'tare' command to all connected Arduinos."""
    print("[get_arduino_data] Sending 'tare' command to all Arduinos...")
    tare_cmd = {"cmd": "tare"}
    success_count = 0
    total_ports = len(STATIC_PORTS)

    for port in STATIC_PORTS:
        if send_cmd(port, tare_cmd):
            success_count += 1
        # Add a small delay between commands if needed
        time.sleep(0.2)

    if success_count == total_ports:
        print("[get_arduino_data] Tare command sent successfully to all Arduinos.")
        # Add a longer delay for Arduinos to process the tare
        time.sleep(2.0)
        print("[get_arduino_data] Assumed tare complete.")
    elif success_count > 0:
        print(f"[get_arduino_data] WARNING: Tare command sent to {success_count}/{total_ports} Arduinos.")
        time.sleep(2.0)
    else:
        print("[get_arduino_data] CRITICAL: Failed to send tare command to any Arduino.")

# --- Public Functions ---
def start_reader_threads():
    print("[get_arduino_data] Starting reader threads...")
    threads = []
    for p in STATIC_PORTS:
        t = threading.Thread(target=reader, args=(p,), daemon=True)
        t.start()
        threads.append(t)
    if not threads:
        print("[get_arduino_data] WARNING: No ports defined.")
    # Add a small delay to allow threads to start and potentially open ports
    time.sleep(1.0)
    return threads

def get_latest_seat_data() -> Dict[str, Dict[str, Any]]:
    with g_data_lock:
        return g_latest_seat_data.copy()

# --- Main (for CLI tool) ---
def main():
    if len(sys.argv) == 4 and sys.argv[1] == "set_cal":
        try:
            alias = sys.argv[2]
            cal_val = float(sys.argv[3])
            port_to_use = None
            for p, a in PORT_ALIAS.items():
                if a == alias:
                    port_to_use = p
                    break
            if not port_to_use:
                print(f"Error: Alias '{alias}' not found.")
                return
            if send_cmd(port_to_use, {"cmd": "set_cal", "value": cal_val}):
                store = load_cal_store()
                store.setdefault(alias, {})["cal"] = cal_val
                store[alias]["updated_at"] = int(time.time())
                save_cal_store(store)
                print(f"Successfully set_cal {cal_val} for {alias} and saved.")
            else:
                 print(f"Failed to send set_cal command for {alias}.")
        except Exception as e:
            print(f"Error processing set_cal: {e}")
        return
    elif len(sys.argv) > 1:
        print(f"Unknown command: {' '.join(sys.argv[1:])}")
        return

    # === "Service Mode" ===
    print("[get_arduino_data] Running in Service Mode (for testing reader threads).")
    start_reader_threads()
    print("Reading... (Ctrl+C to stop)")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nBye!")
        pass

if __name__ == "__main__":
    main()
