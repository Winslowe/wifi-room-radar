# -*- coding: utf-8 -*-
import argparse
import csv
import math
import platform
import queue
import re
import statistics
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

import tkinter as tk
from tkinter import messagebox, ttk


DEFAULT_IP = "192.168.1.102"
PING_INTERVAL_MS = 650
PING_TIMEOUT_MS = 700
MIN_STABLE_VALUES = 12
GRAPH_SIZE = 80
ROOM_SCAN_COUNT = 50

BG = "#0b1220"
PANEL = "#111c2e"
PANEL_LIGHT = "#17243a"
TEXT = "#e8eef8"
MUTED = "#93a4bd"
GREEN = "#35d07f"
YELLOW = "#f4c95d"
ORANGE = "#ff9f43"
RED = "#ff5d73"
BLUE = "#54a8ff"
GRID = "#263751"


def percentile(values: List[Union[int, float]], ratio: float) -> float:
    """
    Belirli bir yüzdelik dilimdeki (percentile) değeri hesaplar.
    
    Args:
        values: Sayısal değerlerden oluşan liste.
        ratio: Hesaplanacak yüzdelik dilim (0.0 ile 1.0 arası).
        
    Returns:
        float: Belirtilen yüzdelik dilime karşılık gelen değer.
        
    Raises:
        ValueError: Eğer liste boşsa.
    """
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Ölçüm bulunamadı.")
    position = (len(ordered) - 1) * ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    part = position - lower
    return ordered[lower] * (1 - part) + ordered[upper] * part


def parse_ping_output(output: bytes) -> Optional[float]:
    """
    Ping komutunun çıktısındaki süreyi Windows dilinden bağımsız olarak bulur.
    
    Args:
        output: Ping komutunun terminalden dönen ham çıktısı (bytes).
        
    Returns:
        Süre (ms) olarak döner, bulamazsa None döner.
    """
    for line in output.splitlines():
        if b"ttl" not in line.lower():
            continue
        match = re.search(rb"([=<])\s*(\d+(?:[.,]\d+)?)\s*ms", line, re.IGNORECASE)
        if not match:
            continue
        value = float(match.group(2).replace(b",", b"."))
        return max(0.5, value / 2.0) if match.group(1) == b"<" else value
    return None


def ping_once(ip_address: str, timeout_ms: int = PING_TIMEOUT_MS) -> Optional[float]:
    """
    Belirtilen IP adresine tek bir ping isteği gönderir ve gecikme süresini ölçer.
    
    Args:
        ip_address: Ping atılacak hedefin IP adresi.
        timeout_ms: Yanıt için beklenecek maksimum süre (milisaniye).
        
    Returns:
        float: Ping süresi (ms). Eğer başarısız olursa None.
    """
    if platform.system() == "Windows":
        command = ["ping", "-n", "1", "-w", str(timeout_ms), ip_address]
    else:
        timeout_seconds = max(1, math.ceil(timeout_ms / 1000))
        command = ["ping", "-c", "1", "-W", str(timeout_seconds), ip_address]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=(timeout_ms / 1000) + 1.5,
            check=False,
        )
        return parse_ping_output(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def measure_ping(ip_address: str, repeat: int = 3) -> Optional[float]:
    """
    Tek bir rastgele sıçramanın sonucu bozmasını azaltmak için ardışık ölçümler
    yapar ve ortanca değeri alır.
    
    Args:
        ip_address: Ölçüm yapılacak IP adresi.
        repeat: Kaç defa ping atılacağı.
        
    Returns:
        float: Ortanca ping süresi. Yeterli ölçüm yoksa None.
    """
    values = []
    for index in range(repeat):
        value = ping_once(ip_address)
        if value is not None:
            values.append(value)
        if index + 1 < repeat:
            time.sleep(0.06)
    if len(values) < 2:
        return None
    return float(statistics.median(values))


@dataclass
class Baseline:
    """Temel ağ durumu analiz sonuçlarını barındırır."""
    usual: float
    spread: float
    warning_limit: float
    stable_values: List[float]
    ignored_count: int


def make_baseline(values: List[float]) -> Baseline:
    """
    Bir odanın temel (baseline) ağ durumunu hesaplar, aykırı değerleri filtreler.
    
    Args:
        values: Temel alınacak ping süreleri.
        
    Returns:
        Baseline: Hesaplanan temel ölçüm değerleri objesi.
    """
    if not values:
        raise ValueError("Temel ölçüm bulunamadı.")

    center = float(statistics.median(values))
    deviations = [abs(value - center) for value in values]
    mad = float(statistics.median(deviations))
    spread = max(1.0, mad * 1.4826)

    outlier_limit = center + max(6.0, spread * 4.0)
    stable = [value for value in values if value <= outlier_limit]
    if len(stable) < MIN_STABLE_VALUES:
        stable = list(values)

    usual = float(statistics.median(stable))
    stable_p90 = percentile(stable, 0.90)

    warning_limit = max(
        usual + 7.0,
        usual * 2.2,
        stable_p90 + 4.0,
    )
    return Baseline(
        usual=usual,
        spread=spread,
        warning_limit=warning_limit,
        stable_values=stable,
        ignored_count=len(values) - len(stable),
    )


@dataclass
class RoomResult:
    """Bir odada yapılan ölçümlerin özet sonucunu barındırır."""
    name: str
    values: List[Optional[float]]
    successful_count: int
    usual: float
    high_value: float
    maximum: float
    loss_rate: float
    typical_change: float
    spike_rate: float
    change_score: float
    score_uncertainty: float
    network_state: str


def calculate_room_numbers(values: List[Optional[float]]) -> Dict[str, float]:
    """
    Ölçüm değerlerinden istatistiksel puanları ve durumları hesaplar.
    
    Args:
        values: Gecikme ölçümlerinin listesi. Başarısız olanlar None olabilir.
        
    Returns:
        Hesaplanan metriklerin sözlüğü.
    """
    successful = [value for value in values if value is not None]
    if not successful:
        return {
            "successful_count": 0.0,
            "usual": 0.0,
            "high_value": 0.0,
            "maximum": 0.0,
            "loss_rate": 100.0,
            "typical_change": 0.0,
            "spike_rate": 0.0,
            "change_score": 100.0,
        }

    usual = float(statistics.median(successful))
    high_value = percentile(successful, 0.90)
    maximum = max(successful)
    loss_rate = 100.0 * (len(values) - len(successful)) / len(values)

    changes: List[float] = []
    previous: Optional[float] = None
    for value in values:
        if value is None:
            previous = None
            continue
        if previous is not None:
            changes.append(abs(value - previous))
        previous = value
    typical_change = float(statistics.median(changes)) if changes else 0.0

    deviations = [abs(value - usual) for value in successful]
    spread = max(1.0, statistics.median(deviations) * 1.4826)
    spike_limit = max(usual + 6.0, usual + 3.5 * spread, usual * 2.0)
    spike_count = sum(value > spike_limit for value in successful)
    spike_rate = 100.0 * spike_count / len(successful)

    tail_gap = max(0.0, high_value - usual)
    loss_part = min(40.0, loss_rate * 0.8)
    change_part = min(25.0, typical_change / max(3.0, usual) * 30.0)
    spike_part = min(20.0, spike_rate * 0.7)
    tail_part = min(15.0, tail_gap / max(5.0, usual) * 20.0)
    score = min(100.0, loss_part + change_part + spike_part + tail_part)

    return {
        "successful_count": float(len(successful)),
        "usual": usual,
        "high_value": high_value,
        "maximum": maximum,
        "loss_rate": loss_rate,
        "typical_change": typical_change,
        "spike_rate": spike_rate,
        "change_score": score,
    }


def analyze_room(name: str, values: List[Optional[float]]) -> RoomResult:
    """
    Belirli bir odaya ait verileri analiz ederek detaylı RoomResult üretir.
    
    Args:
        name: Odanın adı.
        values: Gecikme ölçümleri.
        
    Returns:
        RoomResult: Odanın analiz raporu.
    """
    numbers = calculate_room_numbers(values)
    block_scores = []
    for start in range(0, len(values), 10):
        block = values[start : start + 10]
        if len(block) == 10:
            block_scores.append(calculate_room_numbers(block)["change_score"])

    if len(block_scores) >= 2:
        block_p10 = percentile(block_scores, 0.10)
        block_p90 = percentile(block_scores, 0.90)
        score_uncertainty = block_p90 - block_p10
    else:
        score_uncertainty = 20.0

    usual = numbers["usual"]
    tail_gap = max(0.0, numbers["high_value"] - usual)
    tail_ratio = (
        tail_gap / max(3.0, usual)
        if numbers["successful_count"] > 0
        else float("inf")
    )
    if (
        numbers["loss_rate"] >= 10.0
        or numbers["spike_rate"] >= 25.0
        or tail_gap >= 20.0
        or tail_ratio >= 4.0
    ):
        network_state = "Çok dalgalı"
    elif (
        numbers["loss_rate"] >= 4.0
        or numbers["spike_rate"] >= 12.0
        or tail_gap >= 10.0
        or tail_ratio >= 2.0
    ):
        network_state = "Dalgalı"
    else:
        network_state = "Sakin"

    return RoomResult(
        name=name,
        values=list(values),
        successful_count=int(numbers["successful_count"]),
        usual=numbers["usual"],
        high_value=numbers["high_value"],
        maximum=numbers["maximum"],
        loss_rate=numbers["loss_rate"],
        typical_change=numbers["typical_change"],
        spike_rate=numbers["spike_rate"],
        change_score=numbers["change_score"],
        score_uncertainty=score_uncertainty,
        network_state=network_state,
    )


@dataclass
class RoomComparison:
    """Taranan odalar arasındaki karşılaştırma sonucunu barındırır."""
    likely_room: Optional[RoomResult]
    second_room: RoomResult
    difference: float
    confidence_text: str
    explanation: str
    is_conclusive: bool
    required_difference: float


def compare_rooms(room_results: List[RoomResult]) -> RoomComparison:
    """
    Birden fazla odanın sonuçlarını karşılaştırır ve potansiyel konum farkını bulur.
    
    Args:
        room_results: Taranan odaların analiz sonuçları listesi.
        
    Returns:
        RoomComparison: Karşılaştırma ve güven skoru özeti.
    """
    if len(room_results) < 2:
        raise ValueError("Karşılaştırma için en az 2 oda taranmalı.")

    ordered = sorted(room_results, key=lambda room: room.change_score, reverse=True)
    first, second = ordered[0], ordered[1]
    difference = first.change_score - second.change_score
    required_difference = max(
        20.0,
        first.score_uncertainty * 0.8,
        second.score_uncertainty * 0.8,
    )
    noisy_count = sum(room.network_state != "Sakin" for room in room_results)
    mostly_noisy = noisy_count >= math.ceil(len(room_results) * 2 / 3)
    if mostly_noisy:
        required_difference = max(required_difference, 25.0)

    is_conclusive = difference >= required_difference and not mostly_noisy
    if not is_conclusive:
        explanation = (
            f"Oda seçilmedi. En yüksek iki sonuç arasındaki fark {difference:.0f} puan, "
            f"güvenilir karar için gereken fark yaklaşık {required_difference:.0f} puan. "
            "Grafikteki ani yükselmeler aynı odada da oluşabilen Wi-Fi veya cihaz "
            "gecikmeleridir; oda değişimi kanıtı değildir."
        )
        if mostly_noisy:
            explanation += (
                f" Ayrıca {len(room_results)} odanın {noisy_count} tanesinde ağ "
                "belirgin biçimde dalgalıydı."
            )
        return RoomComparison(
            likely_room=None,
            second_room=second,
            difference=difference,
            confidence_text="Yetersiz",
            explanation=explanation,
            is_conclusive=False,
            required_difference=required_difference,
        )

    if difference < 20:
        confidence = "Orta"
    elif difference < 35:
        confidence = "İyi"
    else:
        confidence = "Daha güçlü"
    explanation = (
        f"{first.name} odasında diğer odalardan belirgin biçimde daha fazla ağ değişimi "
        "ölçüldü. Bu yalnızca bağlantı farkıdır; kesin kişi veya nesne konumu değildir."
    )
    return RoomComparison(
        likely_room=first,
        second_room=second,
        difference=difference,
        confidence_text=confidence,
        explanation=explanation,
        is_conclusive=True,
        required_difference=required_difference,
    )


class MetricCard(tk.Frame):
    """Küçük bir metrik veya değer gösteren kullanıcı arayüzü kartı."""
    def __init__(self, parent: tk.Widget, title: str, value: str = "--", accent: str = BLUE):
        super().__init__(parent, bg=PANEL_LIGHT, highlightthickness=1, highlightbackground=GRID)
        tk.Label(
            self,
            text=title,
            bg=PANEL_LIGHT,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=16, pady=(12, 2))
        self.value_label = tk.Label(
            self,
            text=value,
            bg=PANEL_LIGHT,
            fg=accent,
            font=("Segoe UI Semibold", 19),
        )
        self.value_label.pack(anchor="w", padx=16, pady=(0, 12))

    def set(self, value: str, color: Optional[str] = None) -> None:
        """Karttaki değeri ve isteğe bağlı olarak rengini günceller."""
        self.value_label.configure(text=value)
        if color:
            self.value_label.configure(fg=color)


class PingGraph(tk.Canvas):
    """Ping ölçümlerini canlı olarak gösteren grafik bileşeni."""
    def __init__(self, parent: tk.Widget):
        super().__init__(
            parent,
            bg=PANEL,
            height=250,
            highlightthickness=0,
            bd=0,
        )
        self.values: deque = deque(maxlen=GRAPH_SIZE)
        self.usual: float = 0.0
        self.limit: float = 0.0
        self.bind("<Configure>", lambda _event: self.redraw())

    def add(self, value: Optional[float], usual: float, limit: float) -> None:
        """Grafiğe yeni bir ping değeri ekler ve ekranı günceller."""
        self.values.append(value)
        self.usual = usual
        self.limit = limit
        self.redraw()

    def clear_graph(self) -> None:
        """Grafik verilerini temizler."""
        self.values.clear()
        self.redraw()

    def redraw(self) -> None:
        """Grafiği mevcut değerlerle baştan çizer."""
        self.delete("all")
        width = max(100, self.winfo_width())
        height = max(100, self.winfo_height())
        left, right, top, bottom = 48, 18, 18, 30
        plot_w = width - left - right
        plot_h = height - top - bottom

        numeric = [value for value in self.values if value is not None]
        maximum = max([30.0, self.limit * 1.5] + numeric)
        maximum = math.ceil(maximum / 10.0) * 10.0

        for index in range(5):
            y = top + plot_h * index / 4
            label_value = maximum * (1 - index / 4)
            self.create_line(left, y, width - right, y, fill=GRID)
            self.create_text(
                left - 8,
                y,
                text=f"{label_value:.0f}",
                fill=MUTED,
                anchor="e",
                font=("Segoe UI", 8),
            )

        def value_y(value):
            return top + plot_h * (1 - min(value, maximum) / maximum)

        if self.limit:
            y_limit = value_y(self.limit)
            self.create_line(
                left,
                y_limit,
                width - right,
                y_limit,
                fill=ORANGE,
                dash=(5, 4),
                width=2,
            )
            self.create_text(
                width - right,
                y_limit - 7,
                text="uyarı sınırı",
                fill=ORANGE,
                anchor="e",
                font=("Segoe UI", 8),
            )

        if self.usual:
            y_usual = value_y(self.usual)
            self.create_line(
                left,
                y_usual,
                width - right,
                y_usual,
                fill=GREEN,
                dash=(2, 4),
            )

        values = list(self.values)
        if values:
            step = plot_w / max(1, GRAPH_SIZE - 1)
            previous = None
            start_index = GRAPH_SIZE - len(values)
            for offset, value in enumerate(values):
                x = left + (start_index + offset) * step
                if value is None:
                    self.create_line(x - 3, top + 3, x + 3, top + 9, fill=RED, width=2)
                    self.create_line(x + 3, top + 3, x - 3, top + 9, fill=RED, width=2)
                    previous = None
                    continue
                y = value_y(value)
                color = RED if value > self.limit else BLUE
                if previous is not None:
                    self.create_line(*previous, x, y, fill=BLUE, width=2, smooth=True)
                self.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline=color)
                previous = (x, y)

        self.create_text(
            left,
            height - 10,
            text=(
                "Kırmızı nokta: o anda ping yükseldi. "
                "Tek başına oda değişimi anlamına gelmez."
            ),
            fill=MUTED,
            anchor="w",
            font=("Segoe UI", 9),
        )


class RadarApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Oda Karşılaştırma Ekranı")
        self.root.geometry("1040x840")
        self.root.minsize(900, 760)
        self.root.configure(bg=BG)

        self.room_scanning: bool = False
        self.waiting_for_ping: bool = False
        self.scan_token: int = 0
        self.current_room_name: str = ""
        self.current_values: List[Optional[float]] = []
        self.room_results: List[RoomResult] = []
        self.result_queue: queue.Queue = queue.Queue()
        self.log_path: Optional[Path] = None

        self.ip_var: tk.StringVar = tk.StringVar(value=DEFAULT_IP)
        self.room_name_var: tk.StringVar = tk.StringVar()
        self.progress_var: tk.DoubleVar = tk.DoubleVar(value=0)
        
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(150, self.room_entry.focus_set)

    def _add_hover_effect(self, widget: tk.Widget, normal_bg: str, hover_bg: str) -> None:
        """Bir widget'a fareyle üzerine gelme (hover) efekti ekler."""
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg))

    def build_ui(self) -> None:
        """Kullanıcı arayüzünü (UI) parça parça inşa eder."""
        self._build_styles()
        self._build_header()
        self._build_room_panel()
        self._build_status_panel()
        self._build_cards()
        self._build_center_panel()
        self._build_result_panel()

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Room.Horizontal.TProgressbar",
            troughcolor=PANEL_LIGHT,
            background=BLUE,
            bordercolor=PANEL_LIGHT,
            lightcolor=BLUE,
            darkcolor=BLUE,
        )
        style.configure(
            "Room.Treeview",
            background=PANEL,
            fieldbackground=PANEL,
            foreground=TEXT,
            rowheight=28,
            bordercolor=GRID,
        )
        style.configure(
            "Room.Treeview.Heading",
            background=PANEL_LIGHT,
            foreground=TEXT,
            relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        style.map("Room.Treeview", background=[("selected", "#204a70")])

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 10))

        title_area = tk.Frame(header, bg=BG)
        title_area.pack(side="left")
        tk.Label(
            title_area,
            text="ODA KARŞILAŞTIRMA",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 20),
        ).pack(anchor="w")
        tk.Label(
            title_area,
            text=(
                "Her odada 50 ölçüm yapar. Oda değiştirdiğini kendi başına anlayamaz; "
                "yalnızca senin yazdığın odaları karşılaştırır."
            ),
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        ip_area = tk.Frame(header, bg=BG)
        ip_area.pack(side="right")
        tk.Label(
            ip_area,
            text="ÖLÇÜLECEK CİHAZIN IP ADRESİ",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w")
        self.ip_entry = tk.Entry(
            ip_area,
            textvariable=self.ip_var,
            width=18,
            bg=PANEL_LIGHT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 11),
        )
        self.ip_entry.pack(ipady=7)

    def _build_room_panel(self) -> None:
        room_panel = tk.Frame(
            self.root,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=GRID,
        )
        room_panel.pack(fill="x", padx=24, pady=(0, 10))
        room_panel.grid_columnconfigure(0, weight=1)

        tk.Label(
            room_panel,
            text="1. Bulunduğun odanın adını yaz",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 11),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 5))

        input_row = tk.Frame(room_panel, bg=PANEL)
        input_row.grid(row=1, column=0, sticky="ew", padx=18)
        input_row.grid_columnconfigure(0, weight=1)
        
        self.room_entry = tk.Entry(
            input_row,
            textvariable=self.room_name_var,
            bg=PANEL_LIGHT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 12),
        )
        self.room_entry.grid(row=0, column=0, sticky="ew", ipady=9, padx=(0, 10))
        self.room_entry.bind("<Return>", lambda _event: self.start_room_scan())

        self.scan_button = tk.Button(
            input_row,
            text="BU ODAYI TARA",
            command=self.start_room_scan,
            bg=BLUE,
            activebackground="#3b91e8",
            fg="white",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=10,
            font=("Segoe UI Semibold", 9),
        )
        self.scan_button.grid(row=0, column=1, padx=(0, 8))
        self._add_hover_effect(self.scan_button, BLUE, "#3b91e8")

        self.cancel_button = tk.Button(
            input_row,
            text="DURDUR",
            command=self.cancel_scan,
            state="disabled",
            bg=RED,
            disabledforeground=MUTED,
            activebackground="#e84e64",
            fg="white",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=10,
            font=("Segoe UI Semibold", 9),
        )
        self.cancel_button.grid(row=0, column=2)
        self._add_hover_effect(self.cancel_button, RED, "#e84e64")

        self.progress = ttk.Progressbar(
            room_panel,
            variable=self.progress_var,
            maximum=ROOM_SCAN_COUNT,
            style="Room.Horizontal.TProgressbar",
        )
        self.progress.grid(row=2, column=0, sticky="ew", padx=18, pady=(12, 8))

        action_row = tk.Frame(room_panel, bg=PANEL)
        action_row.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        tk.Label(
            action_row,
            text=(
                "Her nokta 3 pingin ortancasıdır. Tarama sırasında cihazı sabit tut; "
                "indirme/video gibi ağ kullanımını durdur."
            ),
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left")

        self.reset_button = tk.Button(
            action_row,
            text="YENİDEN BAŞLA",
            command=self.reset_session,
            bg=PANEL_LIGHT,
            activebackground=GRID,
            fg=TEXT,
            activeforeground=TEXT,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=7,
            font=("Segoe UI Semibold", 9),
        )
        self.reset_button.pack(side="right")
        self._add_hover_effect(self.reset_button, PANEL_LIGHT, GRID)

        self.finish_button = tk.Button(
            action_row,
            text="ODALARI BİTİR",
            command=self.finish_rooms,
            state="disabled",
            bg=GREEN,
            disabledforeground=MUTED,
            activebackground="#29b96c",
            fg="#07130d",
            activeforeground="#07130d",
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=7,
            font=("Segoe UI Semibold", 9),
        )
        self.finish_button.pack(side="right", padx=(0, 8))
        self._add_hover_effect(self.finish_button, GREEN, "#29b96c")

    def _build_status_panel(self) -> None:
        status_panel = tk.Frame(
            self.root,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=GRID,
        )
        status_panel.pack(fill="x", padx=24, pady=(0, 10))
        
        self.status_dot = tk.Label(
            status_panel,
            text="●",
            bg=PANEL,
            fg=BLUE,
            font=("Segoe UI", 27),
        )
        self.status_dot.pack(side="left", padx=(18, 12), pady=12)
        
        status_text = tk.Frame(status_panel, bg=PANEL)
        status_text.pack(side="left", fill="x", expand=True, pady=11)
        self.status_label = tk.Label(
            status_text,
            text="ODA ADI BEKLENİYOR",
            bg=PANEL,
            fg=BLUE,
            font=("Segoe UI Semibold", 19),
        )
        self.status_label.pack(anchor="w")
        self.explanation_label = tk.Label(
            status_text,
            text="Örneğin “Oda 1”, “Salon” veya “Oda 4” yazıp taramayı başlat.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.explanation_label.pack(anchor="w", pady=(1, 0))
        self.clock_label = tk.Label(
            status_panel,
            text="--:--:--",
            bg=PANEL,
            fg=MUTED,
            font=("Consolas", 12),
        )
        self.clock_label.pack(side="right", padx=18)

    def _build_cards(self) -> None:
        cards = tk.Frame(self.root, bg=BG)
        cards.pack(fill="x", padx=24, pady=(0, 10))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1, uniform="cards")
            
        self.current_card = MetricCard(cards, "SON ÖLÇÜM", "-- ms", BLUE)
        self.usual_card = MetricCard(cards, "ODANIN ORTA DEĞERİ", "-- ms", GREEN)
        self.limit_card = MetricCard(cards, "YÜKSEK DEĞERLER", "-- ms", ORANGE)
        self.loss_card = MetricCard(cards, "CEVAP KAYBI", "0 / 50", RED)
        
        self.current_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.usual_card.grid(row=0, column=1, sticky="nsew", padx=5)
        self.limit_card.grid(row=0, column=2, sticky="nsew", padx=5)
        self.loss_card.grid(row=0, column=3, sticky="nsew", padx=(5, 0))

    def _build_center_panel(self) -> None:
        self.center = tk.Frame(self.root, bg=BG)
        self.center.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        self.center.grid_columnconfigure(0, weight=3)
        self.center.grid_columnconfigure(1, weight=2)
        self.center.grid_rowconfigure(0, weight=1)

        graph_panel = tk.Frame(
            self.center,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=GRID,
        )
        graph_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tk.Label(
            graph_panel,
            text="ŞU AN TARANAN ODA",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=14, pady=(10, 0))
        self.graph = PingGraph(graph_panel)
        self.graph.pack(fill="both", expand=True, padx=7, pady=(0, 6))

        table_panel = tk.Frame(
            self.center,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=GRID,
        )
        table_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        tk.Label(
            table_panel,
            text="TAMAMLANAN ODALAR",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=14, pady=(10, 7))

        columns = ("room", "usual", "loss", "state", "score")
        self.room_table = ttk.Treeview(
            table_panel,
            columns=columns,
            show="headings",
            style="Room.Treeview",
            height=7,
        )
        self.room_table.heading("room", text="Oda")
        self.room_table.heading("usual", text="Orta")
        self.room_table.heading("loss", text="Kayıp")
        self.room_table.heading("state", text="Ağ")
        self.room_table.heading("score", text="Değişim")
        self.room_table.column("room", width=95, anchor="w")
        self.room_table.column("usual", width=48, anchor="center")
        self.room_table.column("loss", width=48, anchor="center")
        self.room_table.column("state", width=75, anchor="center")
        self.room_table.column("score", width=55, anchor="center")
        self.room_table.tag_configure("likely", background="#352d17", foreground=YELLOW)
        self.room_table.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_result_panel(self) -> None:
        result_panel = tk.Frame(
            self.root,
            bg=PANEL_LIGHT,
            highlightthickness=1,
            highlightbackground=GRID,
        )
        result_panel.pack(fill="x", padx=24, pady=(0, 16))
        self.result_title = tk.Label(
            result_panel,
            text="SONUÇ İÇİN EN AZ 2 ODA TARA",
            bg=PANEL_LIGHT,
            fg=MUTED,
            font=("Segoe UI Semibold", 15),
        )
        self.result_title.pack(anchor="w", padx=16, pady=(12, 2))
        self.result_detail = tk.Label(
            result_panel,
            text=(
                "Önemli: Program kesin konum bulmaz; odalardaki bağlantı değişimini "
                "karşılaştırarak bir tahmin üretir. Değişim: 0 sakin, 100 çok değişken."
            ),
            bg=PANEL_LIGHT,
            fg=MUTED,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            wraplength=940,
        )
        self.result_detail.pack(anchor="w", padx=16, pady=(0, 12))
        result_panel.pack_configure(before=self.center)
    def set_status(self, status: str, explanation: str, color: str) -> None:
        """Durum çubuğunu ve saat bilgisini günceller."""
        self.status_label.configure(text=status, fg=color)
        self.status_dot.configure(fg=color)
        self.explanation_label.configure(text=explanation)
        self.clock_label.configure(text=datetime.now().strftime("%H:%M:%S"))

    def start_room_scan(self) -> None:
        """Oda ölçüm işlemini başlatır."""
        if self.room_scanning:
            return
        ip_address = self.ip_var.get().strip()
        room_name = " ".join(self.room_name_var.get().split())
        if not ip_address:
            messagebox.showwarning("IP adresi eksik", "Ölçülecek cihazın IP adresini yaz.")
            return
        if not room_name:
            messagebox.showwarning("Oda adı eksik", "Önce bulunduğun odanın adını yaz.")
            self.room_entry.focus_set()
            return
        if any(room.name.casefold() == room_name.casefold() for room in self.room_results):
            messagebox.showwarning(
                "Bu oda zaten tarandı",
                "Aynı odayı tekrar tarayacaksan adına “2. deneme” gibi bir ek yaz.",
            )
            return

        if self.log_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_path = (
                Path(__file__).resolve().parent / f"oda_taramasi_{timestamp}.csv"
            )

        self.scan_token += 1
        self.current_room_name = room_name
        self.current_values = []
        self.room_scanning = True
        self.waiting_for_ping = False
        self.progress_var.set(0)
        self.graph.clear_graph()
        self.current_card.set("-- ms", BLUE)
        self.usual_card.set("-- ms", GREEN)
        self.limit_card.set("-- ms", ORANGE)
        self.loss_card.set("0 / 50", GREEN)
        self.room_entry.configure(state="disabled")
        self.ip_entry.configure(state="disabled")
        self.scan_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.finish_button.configure(state="disabled")
        self.reset_button.configure(state="disabled")
        self.set_status(
            f"{room_name.upper()} TARANIYOR",
            f"0/{ROOM_SCAN_COUNT} ölçüm tamamlandı. Tarama bitene kadar aynı yerde bekle.",
            BLUE,
        )
        self.root.after(50, self.launch_ping)

    def launch_ping(self) -> None:
        """Arka planda bir ping işlemi başlatır."""
        if not self.room_scanning or self.waiting_for_ping:
            return
        self.waiting_for_ping = True
        token = self.scan_token
        ip_address = self.ip_var.get().strip()

        def worker() -> None:
            self.result_queue.put((token, measure_ping(ip_address)))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(35, lambda: self.check_result(token))

    def check_result(self, expected_token: int) -> None:
        """Ping sonucunun gelip gelmediğini kontrol eder."""
        if expected_token != self.scan_token or not self.room_scanning:
            return
        try:
            while True:
                token, value = self.result_queue.get_nowait()
                if token == expected_token:
                    break
        except queue.Empty:
            self.root.after(35, lambda: self.check_result(expected_token))
            return

        self.waiting_for_ping = False
        self.handle_room_value(value)
        if self.room_scanning:
            self.root.after(PING_INTERVAL_MS, self.launch_ping)

    def handle_room_value(self, value: Optional[float]) -> None:
        """Gelen yeni ölçüm değerini işler ve arayüzü günceller."""
        self.current_values.append(value)
        count = len(self.current_values)
        successful = [item for item in self.current_values if item is not None]
        lost = count - len(successful)
        self.progress_var.set(count)

        if value is None:
            self.current_card.set("CEVAP YOK", RED)
        else:
            self.current_card.set(f"{value:.0f} ms", BLUE)

        if successful:
            usual = float(statistics.median(successful))
            high = percentile(successful, 0.90)
            baseline = make_baseline(successful)
            self.usual_card.set(f"{usual:.0f} ms")
            self.limit_card.set(f"{high:.0f} ms")
            self.graph.add(value, usual, baseline.warning_limit)
        else:
            usual = 0.0
            self.graph.add(value, 0.0, 0.0)

        self.loss_card.set(
            f"{lost} / {ROOM_SCAN_COUNT}",
            GREEN if lost == 0 else (YELLOW if lost < 5 else RED),
        )
        self.set_status(
            f"{self.current_room_name.upper()} TARANIYOR",
            (
                f"{count}/{ROOM_SCAN_COUNT} ölçüm tamamlandı. "
                f"Şu ana kadar {lost} cevap kaybı var."
            ),
            BLUE,
        )

        if count >= ROOM_SCAN_COUNT:
            self.complete_room()

    def complete_room(self) -> None:
        """Bir odanın taraması bittiğinde sonuçları analiz eder ve kaydeder."""
        self.room_scanning = False
        self.waiting_for_ping = False
        result = analyze_room(self.current_room_name, self.current_values)
        self.room_results.append(result)
        self.save_results()
        self.refresh_room_table()

        self.room_entry.configure(state="normal")
        self.ip_entry.configure(state="disabled")
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.reset_button.configure(state="normal")
        if len(self.room_results) >= 2:
            self.finish_button.configure(state="normal")

        self.set_status(
            f"{result.name.upper()} TAMAMLANDI",
            (
                f"50 ölçüm bitti. Bu odadaki ağ durumu: {result.network_state}. "
                "Şimdi başka odaya geçip yeni oda adını yaz."
            ),
            GREEN,
        )
        self.room_name_var.set("")
        self.room_entry.focus_set()
        messagebox.showinfo(
            f"{result.name} tamamlandı",
            (
                f"{result.name} için 50 ölçüm tamamlandı.\n\n"
                f"Ağ durumu: {result.network_state}\n"
                f"Değişim puanı: {result.change_score:.0f}\n\n"
                "Şimdi başka odaya geç.\n"
                "Yeni odanın adını yazıp taramayı başlat.\n\n"
                "Tüm odalar bittiyse “Odaları bitir” düğmesine bas."
            ),
        )

    def cancel_scan(self) -> None:
        """Aktif tarama işlemini kullanıcı isteğiyle durdurur."""
        if not self.room_scanning:
            return
        if not messagebox.askyesno(
            "Taramayı durdur",
            "Bu odadaki eksik ölçümler kaydedilmeyecek. Durdurulsun mu?",
        ):
            return
        self.scan_token += 1
        self.room_scanning = False
        self.waiting_for_ping = False
        self.current_values = []
        self.progress_var.set(0)
        self.room_entry.configure(state="normal")
        self.ip_entry.configure(
            state="disabled" if self.room_results else "normal"
        )
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.reset_button.configure(state="normal")
        if len(self.room_results) >= 2:
            self.finish_button.configure(state="normal")
        self.set_status(
            "TARAMA DURDURULDU",
            "Oda adı duruyor. Hazır olduğunda yeniden başlatabilirsin.",
            YELLOW,
        )

    def finish_rooms(self) -> None:
        """Tüm taramalar bittiğinde sonuçları kıyaslar."""
        if self.room_scanning:
            messagebox.showwarning("Tarama sürüyor", "Önce mevcut oda taramasının bitmesini bekle.")
            return
        try:
            comparison = compare_rooms(self.room_results)
        except ValueError as error:
            messagebox.showwarning("Daha fazla oda gerekli", str(error))
            return

        likely_name = (
            comparison.likely_room.name if comparison.likely_room is not None else None
        )
        self.refresh_room_table(likely_name)
        if comparison.is_conclusive:
            title = f"EN FAZLA AĞ DEĞİŞİMİ: {likely_name.upper()}" if likely_name else "BİLİNMİYOR"
            detail = (
                f"Karşılaştırma gücü: {comparison.confidence_text}. "
                f"{comparison.explanation}"
            )
            color = YELLOW
        else:
            title = "KONUM BELİRLENEMEDİ"
            detail = comparison.explanation
            color = ORANGE
        self.result_title.configure(text=title, fg=color)
        self.result_detail.configure(text=detail, fg=TEXT)
        self.set_status(title, comparison.explanation, color)
        self.save_results()
        messagebox.showinfo(
            "Oda karşılaştırması tamamlandı",
            f"{title}\n\n{comparison.explanation}",
        )

    def refresh_room_table(self, likely_name: Optional[str] = None) -> None:
        """Tabloyu tarama sonuçları ile günceller."""
        for item in self.room_table.get_children():
            self.room_table.delete(item)
        ordered = sorted(
            self.room_results,
            key=lambda room: room.change_score,
            reverse=True,
        )
        for room in ordered:
            tags = ("likely",) if room.name == likely_name else ()
            self.room_table.insert(
                "",
                "end",
                values=(
                    room.name,
                    f"{room.usual:.0f} ms",
                    f"{room.loss_rate:.0f}%",
                    room.network_state,
                    f"{room.change_score:.0f}",
                ),
                tags=tags,
            )

    def save_results(self) -> None:
        """Sonuçları CSV dosyasına kaydeder ve hata olursa yönetir."""
        if self.log_path is None:
            return
        try:
            with open(self.log_path, "w", newline="", encoding="utf-8-sig") as log_file:
                writer = csv.writer(log_file)
                writer.writerow(
                    [
                        "Oda",
                        "Ölçüm sırası",
                        "Yanıt süresi (ms)",
                        "Odanın orta değeri (ms)",
                        "Yüksek değerler (ms)",
                        "Cevap kaybı (%)",
                        "Değişim puanı",
                        "Puan oynama payı",
                        "Ağ durumu",
                    ]
                )
                for room in self.room_results:
                    for index, value in enumerate(room.values, start=1):
                        writer.writerow(
                            [
                                room.name,
                                index,
                                "" if value is None else f"{value:.1f}",
                                f"{room.usual:.1f}",
                                f"{room.high_value:.1f}",
                                f"{room.loss_rate:.1f}",
                                f"{room.change_score:.1f}",
                                f"{room.score_uncertainty:.1f}",
                                room.network_state,
                            ]
                        )
        except OSError as e:
            messagebox.showerror("Kayıt Hatası", f"Sonuçlar kaydedilemedi:\n{e}")

    def reset_session(self) -> None:
        """Tüm oturum verilerini temizler ve başlangıç durumuna döner."""
        if self.room_scanning and not messagebox.askyesno(
            "Yeniden başla",
            "Devam eden tarama ve tamamlanan oda sonuçları silinsin mi?",
        ):
            return
        self.scan_token += 1
        self.room_scanning = False
        self.waiting_for_ping = False
        self.current_room_name = ""
        self.current_values = []
        self.room_results = []
        self.log_path = None
        self.progress_var.set(0)
        self.graph.clear_graph()
        self.refresh_room_table()
        self.room_name_var.set("")
        self.room_entry.configure(state="normal")
        self.ip_entry.configure(state="normal")
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.finish_button.configure(state="disabled")
        self.reset_button.configure(state="normal")
        self.current_card.set("-- ms", BLUE)
        self.usual_card.set("-- ms", GREEN)
        self.limit_card.set("-- ms", ORANGE)
        self.loss_card.set("0 / 50", GREEN)
        self.result_title.configure(text="SONUÇ İÇİN EN AZ 2 ODA TARA", fg=MUTED)
        self.result_detail.configure(
            text=(
                "Önemli: Program kesin konum bulmaz; odalardaki bağlantı değişimini "
                "karşılaştırarak bir tahmin üretir. Değişim: 0 sakin, 100 çok değişken."
            ),
            fg=MUTED,
        )
        self.set_status(
            "ODA ADI BEKLENİYOR",
            "Örneğin “Oda 1”, “Salon” veya “Oda 4” yazıp taramayı başlat.",
            BLUE,
        )
        self.room_entry.focus_set()

    def close(self) -> None:
        """Pencereyi kapatır ve işlemi sonlandırır."""
        self.scan_token += 1
        self.room_scanning = False
        self.root.destroy()

def run_self_test() -> int:
    """Karar sistemini UI olmadan test eder."""
    assert parse_ping_output(b"Reply from host: time=5ms TTL=64") == 5.0
    assert parse_ping_output(b"Reply from host: time<1ms TTL=64") == 0.5
    assert parse_ping_output(b"Request timed out.") is None

    original_ping_once = globals()["ping_once"]
    test_values = iter([3.0, 80.0, 4.0])
    globals()["ping_once"] = lambda _ip: next(test_values)
    try:
        assert measure_ping("test") == 4.0
    finally:
        globals()["ping_once"] = original_ping_once

    calibration = [3, 4, 3, 2, 3, 4, 3, 3, 2, 4, 3, 3, 4, 2, 3]
    outlier_baseline = make_baseline(calibration + [42])
    assert outlier_baseline.ignored_count == 1
    assert outlier_baseline.warning_limit <= 10

    quiet_room = analyze_room("Oda 1", [3, 4, 3, 3, 4] * 10)
    active_values: List[Optional[float]] = [3, 4, 18, None, 5, 22, 3, None, 25, 4] * 5
    active_room = analyze_room("Oda 2", active_values)
    comparison = compare_rooms([quiet_room, active_room])
    assert quiet_room.successful_count == ROOM_SCAN_COUNT
    assert active_room.successful_count == 40
    assert active_room.change_score > quiet_room.change_score
    assert comparison.likely_room is not None and comparison.likely_room.name == "Oda 2"
    assert len(quiet_room.values) == ROOM_SCAN_COUNT

    noisy_a = analyze_room("Aynı yer 1", [3, 31, 3, 28, 4, 3, 30, 3, 4, 25] * 5)
    noisy_b = analyze_room("Aynı yer 2", [4, 29, 3, 27, 4, 3, 32, 3, 4, 24] * 5)
    noisy_comparison = compare_rooms([noisy_a, noisy_b])
    assert noisy_a.network_state == "Çok dalgalı"
    assert not noisy_comparison.is_conclusive
    assert noisy_comparison.likely_room is None

    print("Tüm testler başarılı.")
    print("• Kalibrasyondaki tek sıçrama ayıklandı.")
    print("• 50 ölçümlük iki oda doğru karşılaştırıldı.")
    print("• Cevap kaybı ve tekrarlayan sıçramalar puana katıldı.")
    print("• Aynı yerdeki ağ sıçramaları oda değişimi sayılmadı.")
    return 0


def parse_args() -> argparse.Namespace:
    """Komut satırı argümanlarını ayrıştırır."""
    parser = argparse.ArgumentParser(description="Anlaşılır bağlantı takip ekranı")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Pencereyi açmadan karar sistemini test et",
    )
    return parser.parse_args()


def main() -> int:
    """Ana program akışı."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if args.test:
        return run_self_test()

    if platform.system() == "Windows":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

    root = tk.Tk()
    RadarApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
