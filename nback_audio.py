# -*- coding: utf-8 -*-
"""
N-back auditivo para EEG - version sin PsychoPy.

Requisitos:
- Python 3
- Tkinter (normalmente incluido con Python en Windows)
- Windows para reproduccion automatica con winsound y generacion offline de WAV.

Modos:
- Pasivo
- 0-back
- 2-back

Salidas:
- CSV por ensayo
- CSV resumen con hits, misses, false alarms, correct rejections,
  sensibilidad, especificidad, balanced accuracy, RT medio/mediano y esfuerzo 1-7.
"""

from __future__ import annotations

import csv
import math
import os
import random
import statistics
import subprocess
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

try:
    import winsound
except ImportError:
    winsound = None

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "nback_audio_es"
RESULTS_DIR = BASE_DIR / "nback_results"
DIGITS = list(range(1, 10))
WORDS = {1:"uno",2:"dos",3:"tres",4:"cuatro",5:"cinco",6:"seis",7:"siete",8:"ocho",9:"nueve"}


def safe_name(text: str) -> str:
    text = text.strip() or "anon"
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)


def pct(x):
    if x is None:
        return "N/A"
    try:
        if math.isnan(x):
            return "N/A"
    except TypeError:
        pass
    return f"{100*x:.1f}%"


def ps_escape(text: str) -> str:
    return text.replace("'", "''")


def generate_audio_windows():
    if os.name != "nt":
        raise RuntimeError("La generacion automatica de audio esta implementada para Windows.")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    commands = [
        "Add-Type -AssemblyName System.Speech",
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "$s.Volume = 100",
        "$s.Rate = -1",
        "try { $culture = [System.Globalization.CultureInfo]::GetCultureInfo('es-ES'); "
        "$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, "
        "[System.Speech.Synthesis.VoiceAge]::NotSet, 0, $culture) } catch {}",
    ]
    for d, word in WORDS.items():
        p = ps_escape(str((AUDIO_DIR / f"{d}.wav").resolve()))
        w = ps_escape(word)
        commands += [
            f"$s.SetOutputToWaveFile('{p}')",
            f"$s.Speak('{w}')",
            "$s.SetOutputToDefaultAudioDevice()",
        ]
    commands.append("$s.Dispose()")
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "; ".join(commands)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("No se pudo generar el audio.\n\n" + proc.stderr)


def ensure_audio():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    missing = [d for d in DIGITS if not (AUDIO_DIR / f"{d}.wav").exists()]
    if missing:
        if os.name == "nt":
            generate_audio_windows()
        else:
            raise RuntimeError(
                f"Faltan WAV en {AUDIO_DIR}. Coloca 1.wav, 2.wav, ..., 9.wav."
            )


def play_digit(digit: int):
    if winsound is None:
        raise RuntimeError("winsound no esta disponible. Esta version esta pensada para Windows.")
    winsound.PlaySound(
        str(AUDIO_DIR / f"{digit}.wav"),
        winsound.SND_FILENAME | winsound.SND_ASYNC,
    )


def choose_targets(eligible, proportion, rng):
    eligible = list(eligible)
    if len(eligible) < 2:
        raise ValueError("El test es demasiado corto.")
    n = int(round(proportion * len(eligible)))
    n = max(1, min(n, len(eligible)-1))
    return set(rng.sample(eligible, n))


def make_sequence(mode, n_trials, target_prop, target_digit, rng):
    if mode == "Pasivo":
        seq = [rng.choice(DIGITS) for _ in range(n_trials)]
        return seq, [False]*n_trials, [False]*n_trials

    if mode == "0-back":
        targets = choose_targets(range(n_trials), target_prop, rng)
        others = [d for d in DIGITS if d != target_digit]
        seq, flags = [], []
        for i in range(n_trials):
            is_t = i in targets
            flags.append(is_t)
            seq.append(target_digit if is_t else rng.choice(others))
        return seq, flags, [True]*n_trials

    if mode == "2-back":
        if n_trials < 6:
            raise ValueError("2-back requiere mas ensayos. Aumenta la duracion o reduce el SOA.")
        targets = choose_targets(range(2, n_trials), target_prop, rng)
        seq = [rng.choice(DIGITS), rng.choice(DIGITS)]
        flags = [False, False]
        evals = [False, False]
        for i in range(2, n_trials):
            is_t = i in targets
            if is_t:
                digit = seq[i-2]
            else:
                digit = rng.choice([d for d in DIGITS if d != seq[i-2]])
            seq.append(digit)
            flags.append(is_t)
            evals.append(True)
        return seq, flags, evals

    raise ValueError("Modo desconocido")


def metrics(rows, mode):
    if mode == "Pasivo":
        return {
            "hits":None, "misses":None, "false_alarms":None, "correct_rejections":None,
            "sensitivity":None, "specificity":None, "balanced_accuracy":None,
            "mean_hit_rt_ms":None, "median_hit_rt_ms":None,
            "n_evaluable_trials":0,
            "total_space_responses":sum(int(r["responded"]) for r in rows),
        }

    ev = [r for r in rows if r["evaluable"]]
    h = sum(r["outcome"] == "HIT" for r in ev)
    m = sum(r["outcome"] == "MISS" for r in ev)
    fa = sum(r["outcome"] == "FALSE_ALARM" for r in ev)
    cr = sum(r["outcome"] == "CORRECT_REJECTION" for r in ev)
    sens = h/(h+m) if (h+m) else float("nan")
    spec = cr/(cr+fa) if (cr+fa) else float("nan")
    ba = (sens+spec)/2 if not math.isnan(sens) and not math.isnan(spec) else float("nan")
    rts = [float(r["rt_ms"]) for r in ev if r["outcome"] == "HIT" and r["rt_ms"] != ""]
    return {
        "hits":h, "misses":m, "false_alarms":fa, "correct_rejections":cr,
        "sensitivity":sens, "specificity":spec, "balanced_accuracy":ba,
        "mean_hit_rt_ms":statistics.mean(rts) if rts else None,
        "median_hit_rt_ms":statistics.median(rts) if rts else None,
        "n_evaluable_trials":len(ev),
        "total_space_responses":sum(int(r["responded"]) for r in rows),
    }


def save_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


class ConfigDialog:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("N-back auditivo - configuracion")
        self.root.resizable(False, False)
        self.result = None

        f = ttk.Frame(self.root, padding=18)
        f.grid(row=0, column=0)

        self.vars = {
            "participant": tk.StringVar(value=""),
            "mode": tk.StringVar(value="0-back"),
            "duration": tk.StringVar(value="45"),
            "soa": tk.StringVar(value="1.8"),
            "response": tk.StringVar(value="1.2"),
            "target_prop": tk.StringVar(value="0.25"),
            "target_digit": tk.StringVar(value="8"),
            "seed": tk.StringVar(value=""),
            "fullscreen": tk.BooleanVar(value=True),
        }

        row = 0
        ttk.Label(f, text="Modo").grid(row=row, column=0, sticky="w", padx=(0,15), pady=5)
        ttk.Combobox(f, textvariable=self.vars["mode"], values=["Pasivo","0-back","2-back"], state="readonly", width=24).grid(row=row, column=1, pady=5)
        row += 1

        items = [
            ("ID participante", "participant"),
            ("Duracion del test (s)", "duration"),
            ("SOA - inicio a inicio (s)", "soa"),
            ("Ventana de respuesta (s)", "response"),
            ("Proporcion de targets", "target_prop"),
            ("Digito target para 0-back", "target_digit"),
            ("Semilla aleatoria (opcional)", "seed"),
        ]
        for label, key in items:
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=(0,15), pady=5)
            ttk.Entry(f, textvariable=self.vars[key], width=27).grid(row=row, column=1, pady=5)
            row += 1

        ttk.Checkbutton(f, text="Pantalla completa", variable=self.vars["fullscreen"]).grid(row=row, column=0, columnspan=2, sticky="w", pady=(8,4))
        row += 1
        ttk.Label(f, text="Recomendado: 45 s | SOA 1.8 s | ventana 1.2 s | targets 0.25").grid(row=row, column=0, columnspan=2, sticky="w", pady=(8,12))
        row += 1

        bf = ttk.Frame(f)
        bf.grid(row=row, column=0, columnspan=2, sticky="e")
        ttk.Button(bf, text="Cancelar", command=self.cancel).pack(side="right", padx=(6,0))
        ttk.Button(bf, text="Iniciar", command=self.start).pack(side="right")
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)

    def start(self):
        try:
            duration = float(self.vars["duration"].get())
            soa = float(self.vars["soa"].get())
            response = float(self.vars["response"].get())
            target_prop = float(self.vars["target_prop"].get())
            target_digit = int(self.vars["target_digit"].get())
            seed_text = self.vars["seed"].get().strip()
            seed = int(seed_text) if seed_text else random.SystemRandom().randint(0, 2**31-1)

            if duration <= 0 or soa <= 0:
                raise ValueError("Duracion y SOA deben ser mayores que 0.")
            if response <= 0 or response > soa:
                raise ValueError("La ventana de respuesta debe ser > 0 y <= SOA.")
            if not 0 < target_prop < 1:
                raise ValueError("La proporcion de targets debe estar entre 0 y 1.")
            if target_digit not in DIGITS:
                raise ValueError("El digito target debe estar entre 1 y 9.")
            if int(duration // soa) < 4:
                raise ValueError("La configuracion genera muy pocos estimulos.")

            self.result = {
                "participant": safe_name(self.vars["participant"].get()),
                "mode": self.vars["mode"].get(),
                "duration_s": duration,
                "soa_s": soa,
                "response_window_s": response,
                "target_proportion": target_prop,
                "target_digit": target_digit,
                "seed": seed,
                "fullscreen": bool(self.vars["fullscreen"].get()),
            }
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Parametros invalidos", str(e))

    def cancel(self):
        self.result = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.result


class Experiment:
    def __init__(self, cfg, seq, flags, evals):
        self.cfg, self.seq, self.flags, self.evals = cfg, seq, flags, evals
        self.root = tk.Tk()
        self.root.title("N-back auditivo")
        self.root.configure(bg="black")
        if cfg["fullscreen"]:
            self.root.attributes("-fullscreen", True)
        else:
            self.root.geometry("1000x700")

        self.label = tk.Label(self.root, fg="white", bg="black", font=("Arial",24), justify="center")
        self.label.pack(expand=True, fill="both", padx=40, pady=40)

        self.root.bind("<Escape>", self.abort)
        self.root.bind("<Return>", self.enter)
        self.root.bind("<KP_Enter>", self.enter)
        self.root.bind("<space>", self.space)
        self.root.bind("<KeyRelease-space>", self.space_release)

        self.rows = []
        self.state = "instructions"
        self.trial = -1
        self.trial_start = None
        self.onset = None
        self.t0 = None
        self.first_rt = None
        self.extra_presses = 0
        self.space_down = False
        self.effort = None
        self.aborted = False
        self.show_instructions()

    def show_instructions(self):
        common = "Mantén la cabeza quieta y fija la mirada en la cruz (+).\n\nEscucha los números sin mover labios ni mandíbula.\n\n"
        if self.cfg["mode"] == "Pasivo":
            task = "TAREA: ESCUCHA PASIVA\n\nEscucha los números y NO presiones ESPACIO."
        elif self.cfg["mode"] == "0-back":
            task = f"TAREA: 0-BACK\n\nPresiona ESPACIO cada vez que escuches el número {self.cfg['target_digit']}."
        else:
            task = "TAREA: 2-BACK\n\nPresiona ESPACIO cuando el número actual sea igual al escuchado DOS posiciones antes."
        self.label.config(text=common + task + "\n\nPresiona ENTER para comenzar.", font=("Arial",24))

    def enter(self, event=None):
        if self.state == "instructions":
            self.state = "running"
            self.label.config(text="+", font=("Arial",72))
            self.root.after(1000, self.start_first)
        elif self.state == "done":
            self.root.destroy()

    def abort(self, event=None):
        self.aborted = True
        self.root.destroy()

    def space(self, event=None):
        if self.space_down:
            return
        self.space_down = True
        if self.state != "running" or self.onset is None:
            return
        rt = time.perf_counter() - self.onset
        if 0 <= rt <= self.cfg["response_window_s"]:
            if self.first_rt is None:
                self.first_rt = rt
            else:
                self.extra_presses += 1

    def space_release(self, event=None):
        self.space_down = False

    def start_first(self):
        self.t0 = time.perf_counter()
        self.trial = 0
        self.start_trial()

    def start_trial(self):
        if self.trial >= len(self.seq):
            self.ask_effort()
            return

        self.first_rt = None
        self.extra_presses = 0
        self.trial_start = time.perf_counter()
        self.label.config(text="+", font=("Arial",72))
        self.root.update_idletasks()
        self.onset = time.perf_counter()
        play_digit(self.seq[self.trial])
        self.root.after(int(self.cfg["response_window_s"]*1000), self.close_trial)

    def close_trial(self):
        digit = self.seq[self.trial]
        is_target = bool(self.flags[self.trial])
        evaluable = bool(self.evals[self.trial])
        responded = self.first_rt is not None

        if not evaluable:
            outcome = "NOT_EVALUATED"
        elif is_target and responded:
            outcome = "HIT"
        elif is_target and not responded:
            outcome = "MISS"
        elif (not is_target) and responded:
            outcome = "FALSE_ALARM"
        else:
            outcome = "CORRECT_REJECTION"

        self.rows.append({
            "participant": self.cfg["participant"],
            "mode": self.cfg["mode"],
            "trial": self.trial+1,
            "digit": digit,
            "is_target": int(is_target),
            "evaluable": int(evaluable),
            "stimulus_onset_s": round(self.onset-self.t0, 6),
            "responded": int(responded),
            "rt_ms": "" if self.first_rt is None else round(self.first_rt*1000, 2),
            "extra_space_presses": self.extra_presses,
            "outcome": outcome,
        })

        elapsed = time.perf_counter() - self.trial_start
        wait_s = max(0, self.cfg["soa_s"] - elapsed)
        self.trial += 1
        self.onset = None
        self.root.after(int(wait_s*1000), self.start_trial)

    def ask_effort(self):
        self.state = "effort"
        self.onset = None
        self.label.config(
            text="¿Cuánto esfuerzo mental requirió esta tarea?\n\n1 = muy bajo        7 = muy alto\n\nPulsa una tecla del 1 al 7.",
            font=("Arial",28),
        )
        for n in range(1,8):
            self.root.bind(str(n), self.set_effort)

    def set_effort(self, event):
        if self.state != "effort":
            return
        self.effort = int(event.char)
        for n in range(1,8):
            self.root.unbind(str(n))
        self.show_results()

    def show_results(self):
        m = metrics(self.rows, self.cfg["mode"])
        if self.cfg["mode"] == "Pasivo":
            text = (
                "TEST FINALIZADO\n\n"
                f"Modo: {self.cfg['mode']}\n"
                f"Estímulos: {len(self.rows)}\n"
                f"Pulsaciones ESPACIO: {m['total_space_responses']}\n"
                f"Esfuerzo mental: {self.effort}/7\n\n"
                "Balanced accuracy: N/A\n\nPresiona ENTER para salir."
            )
        else:
            rt = "N/A" if m["median_hit_rt_ms"] is None else f"{m['median_hit_rt_ms']:.0f} ms"
            text = (
                "TEST FINALIZADO\n\n"
                f"Modo: {self.cfg['mode']}\n"
                f"Hits: {m['hits']}\nMisses: {m['misses']}\n"
                f"False alarms: {m['false_alarms']}\nCorrect rejections: {m['correct_rejections']}\n\n"
                f"Sensibilidad: {pct(m['sensitivity'])}\n"
                f"Especificidad: {pct(m['specificity'])}\n"
                f"Balanced accuracy: {pct(m['balanced_accuracy'])}\n"
                f"RT mediano (hits): {rt}\n"
                f"Esfuerzo mental: {self.effort}/7\n\n"
                "Presiona ENTER para salir."
            )
        self.state = "done"
        self.label.config(text=text, font=("Arial",25))

    def run(self):
        self.root.mainloop()
        return self.rows, self.effort, self.aborted


def main():
    try:
        ensure_audio()
    except Exception as e:
        r = tk.Tk(); r.withdraw(); messagebox.showerror("Error de audio", str(e)); r.destroy(); return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = ConfigDialog().run()
    if cfg is None:
        return

    n_trials = int(cfg["duration_s"] // cfg["soa_s"])
    rng = random.Random(cfg["seed"])
    try:
        seq, flags, evals = make_sequence(
            cfg["mode"], n_trials, cfg["target_proportion"], cfg["target_digit"], rng
        )
    except Exception as e:
        r = tk.Tk(); r.withdraw(); messagebox.showerror("Error", str(e)); r.destroy(); return

    rows, effort, aborted = Experiment(cfg, seq, flags, evals).run()
    if not rows:
        return

    m = metrics(rows, cfg["mode"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode_file = cfg["mode"].replace("-", "").replace(" ", "_")
    stem = f"{stamp}_{cfg['participant']}_{mode_file}"
    trials_path = RESULTS_DIR / f"{stem}_trials.csv"
    summary_path = RESULTS_DIR / f"{stem}_summary.csv"

    trial_fields = [
        "participant","mode","trial","digit","is_target","evaluable",
        "stimulus_onset_s","responded","rt_ms","extra_space_presses","outcome"
    ]
    save_csv(trials_path, rows, trial_fields)

    summary = {
        "participant":cfg["participant"],
        "mode":cfg["mode"],
        "timestamp":stamp,
        "aborted":int(aborted),
        "seed":cfg["seed"],
        "requested_duration_s":cfg["duration_s"],
        "soa_s":cfg["soa_s"],
        "response_window_s":cfg["response_window_s"],
        "target_proportion_requested":cfg["target_proportion"],
        "target_digit_0back":cfg["target_digit"] if cfg["mode"] == "0-back" else "",
        "n_stimuli_planned":n_trials,
        "n_stimuli_completed":len(rows),
        "n_evaluable_trials":m["n_evaluable_trials"],
        "hits":"" if m["hits"] is None else m["hits"],
        "misses":"" if m["misses"] is None else m["misses"],
        "false_alarms":"" if m["false_alarms"] is None else m["false_alarms"],
        "correct_rejections":"" if m["correct_rejections"] is None else m["correct_rejections"],
        "sensitivity":"" if m["sensitivity"] is None else m["sensitivity"],
        "specificity":"" if m["specificity"] is None else m["specificity"],
        "balanced_accuracy":"" if m["balanced_accuracy"] is None else m["balanced_accuracy"],
        "mean_hit_rt_ms":"" if m["mean_hit_rt_ms"] is None else round(m["mean_hit_rt_ms"],2),
        "median_hit_rt_ms":"" if m["median_hit_rt_ms"] is None else round(m["median_hit_rt_ms"],2),
        "total_space_responses":m["total_space_responses"],
        "mental_effort_1_to_7":"" if effort is None else effort,
    }
    save_csv(summary_path, [summary], list(summary.keys()))

    print("Archivos guardados:")
    print(trials_path)
    print(summary_path)


if __name__ == "__main__":
    main()
