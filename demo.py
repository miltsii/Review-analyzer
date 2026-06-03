import tkinter as tk
from tkinter import filedialog, messagebox
import re
import json
import os
from collections import Counter
from datetime import datetime


# =========================
# DESIGN
# =========================

BG      = "#f4f6f8"
CARD    = "#ffffff"
PRIMARY = "#2e7d32"
ACCENT  = "#1976d2"
RED     = "#c62828"
ORANGE  = "#e65100"
GREEN   = "#2e7d32"

FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_TEXT  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)

HISTORY_FILE = "feedback_history.json"


# =========================
# WORDS
# =========================

positive_words = {
    "good", "great", "nice", "fast", "excellent", "love",
    "fresh", "tasty", "perfect", "friendly", "clean", "hot",
    "cozy", "lovely", "juicy", "amazing", "awesome", "delicious",
    "warm", "helpful", "polite", "quick", "happy", "satisfied"
}

negative_words = {
    "bad", "slow", "cold", "burnt", "late", "dirty",
    "wrong", "missing", "awful", "worst", "smelly",
    "rude", "nasty", "mean", "dark", "disgusting", "old",
    "stale", "wait", "horrible", "terrible", "unhappy",
    "disappointing", "poor", "mess", "broken", "incorrect"
}

FOOD_WORDS = {
    "burger","fries","food","taste","tasty","cold","hot","warm",
    "fresh","burnt","juicy","beer","drink","menu","meal","dish",
    "stale","delicious","disgusting","old","flavour","flavor"
}
SERVICE_WORDS = {
    "staff","service","waiter","waitress","slow","fast","friendly",
    "rude","nice","helpful","polite","late","wait","quick","ignored",
    "attentive","order"
}
CLEAN_WORDS = {
    "clean","dirty","smelly","mess","hygiene","toilet","bathroom",
    "floor","table","sticky","dusty","napkin"
}

NEGATIONS    = {"not","no","never","didn't","didnt","wasn't","wasnt","hardly","barely"}
INTENSIFIERS = {"very": 2.0, "really": 2.0, "extremely": 3.0, "absolutely": 3.0, "quite": 1.5}

# Korjauslista — prioriteetti (korkein ensin)
FIX_CHECKS = [
    ("Staff attitude",           ["rude","mean","nasty","ignored","impolite"]),
    ("Food temperature/quality", ["cold","burnt","stale","old","disgusting","raw"]),
    ("Cleanliness",              ["dirty","smelly","mess","sticky","dusty","hygiene"]),
    ("Service speed",            ["slow","late","wait","waited","waiting"]),
    ("Order accuracy",           ["missing","wrong","incorrect","forgot"]),
]


# =========================
# HISTORY
# =========================

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception:
        pass


# =========================
# ANALYSIS ENGINE
# =========================

def _run_analysis(txt):
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    if not lines:
        return None

    word_counter   = Counter()
    food_score     = 0
    service_score  = 0
    clean_score    = 0
    food_signal    = False
    service_signal = False
    clean_signal   = False
    negative_lines = []
    positive_lines = []

    for line in lines:
        words    = re.findall(r"\w+", line.lower())
        pos      = 0.0
        neg      = 0.0
        intensity = 1.0
        negation  = False
        line_food    = False
        line_service = False
        line_clean   = False

        for w in words:
            word_counter[w] += 1

            if w in INTENSIFIERS:
                intensity = INTENSIFIERS[w]
                continue
            if w in NEGATIONS:
                negation = True
                continue

            if w in FOOD_WORDS:    line_food    = True
            if w in SERVICE_WORDS: line_service = True
            if w in CLEAN_WORDS:   line_clean   = True

            # toistuvuuspaino: sana mainittu useasti = vakavampi
            repeat_weight = 1.0 + (word_counter[w] - 1) * 0.15

            if w in positive_words:
                val = intensity * repeat_weight
                if negation: val *= -1
                pos += val
                negation = False; intensity = 1.0

            elif w in negative_words:
                val = intensity * repeat_weight
                if negation: val *= -1
                neg += val
                negation = False; intensity = 1.0

        net = pos - neg

        if line_food:
            food_signal = True
            food_score += net
        if line_service:
            service_signal = True
            service_score += net
        if line_clean:
            clean_signal = True
            clean_score += net

        if net < 0:
            negative_lines.append((line, abs(net)))
        elif net > 0:
            positive_lines.append(line)

    # pisteytys
    def safe_score(s, has_signal):
        if not has_signal:
            return None
        return max(0.0, min(100.0, 50 + s * 12))

    food_s    = safe_score(food_score,    food_signal)
    service_s = safe_score(service_score, service_signal)
    clean_s   = safe_score(clean_score,   clean_signal)

    food_val    = food_s    if food_s    is not None else 50.0
    service_val = service_s if service_s is not None else 50.0
    clean_val   = clean_s   if clean_s   is not None else 50.0

    score = round(max(0, min(100, food_val * 0.45 + service_val * 0.45 + clean_val * 0.10)))
    mood  = "Positive" if score > 70 else "Negative" if score < 40 else "Neutral"

    issues = [
        f"{w} (×{c})"
        for w, c in word_counter.most_common(8)
        if w in negative_words
    ]

    candidates = []
    if food_s    is not None: candidates.append(("Food",        food_s))
    if service_s is not None: candidates.append(("Service",     service_s))
    if clean_s   is not None: candidates.append(("Cleanliness", clean_s))

    weakest = min(candidates, key=lambda x: x[1])[0] if candidates else "N/A"

    rec_map = {
        "Food":        "Improve food quality and consistency",
        "Service":     "Improve staff service and speed",
        "Cleanliness": "Improve cleanliness and hygiene",
        "N/A":         "Not enough data for recommendation",
    }

    scores_display = {}
    if food_s    is not None: scores_display["Food"]        = food_s
    if service_s is not None: scores_display["Service"]     = service_s
    if clean_s   is not None: scores_display["Cleanliness"] = clean_s

    # korjaukset prioriteettijärjestyksessä
    fixes = []
    for label, keywords in FIX_CHECKS:
        count = sum(word_counter[k] for k in keywords if k in word_counter)
        if count > 0:
            fixes.append((label, count))
    fixes.sort(key=lambda x: -x[1])

    # luottamusväli
    n = len(lines)
    confidence = "High" if n >= 8 else "Medium" if n >= 3 else "Low"

    negative_lines.sort(key=lambda x: -x[1])

    summary = f"Overall sentiment is {mood.lower()}."
    if weakest != "N/A":
        summary += f" Weakest area: {weakest}."

    return {
        "score":          score,
        "mood":           mood,
        "issues":         issues,
        "rec":            rec_map[weakest],
        "summary":        summary,
        "negative_lines": [l for l, _ in negative_lines],
        "positive_lines": positive_lines,
        "scores_display": scores_display,
        "fixes":          fixes,
        "confidence":     confidence,
        "n_lines":        n,
    }

def analyze_feedback(text, compare_text=None):
    result  = _run_analysis(text)
    compare = _run_analysis(compare_text) if compare_text and compare_text.strip() else None
    return result, compare


# =========================
# HELPERS
# =========================

def score_color(s):
    if s >= 65: return GREEN
    if s >= 40: return ORANGE
    return RED


# =========================
# APP
# =========================

class App:

    def __init__(self, root):
        root.title("Restaurant Feedback Dashboard")
        root.geometry("800x980")
        root.configure(bg=BG)

        self.history     = load_history()
        self.last_report = ""

        container = tk.Frame(root, bg=BG)
        container.pack(fill="both", expand=True)

        self.canvas   = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar     = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=BG)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        root.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self.build_ui()

    # ── card helper ───────────────────────────────

    def card(self, title=None):
        outer = tk.Frame(self.scroll_frame, bg=BG)
        outer.pack(fill="x", padx=15, pady=5)
        frame = tk.Frame(outer, bg=CARD, padx=16, pady=14,
                         highlightbackground="#9bba9d", highlightthickness=2)
        frame.pack(fill="x")
        if title:
            tk.Label(frame, text=title, bg=CARD, font=FONT_TITLE).pack(anchor="w", pady=(0, 6))
        return frame

    # ── score bar ─────────────────────────────────

    def make_score_bar(self, parent, label, value, max_w=480):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=f"{label:<14}", bg=CARD, font=FONT_SMALL,
                 width=14, anchor="w").pack(side="left")
        bar_bg = tk.Frame(row, bg="#e0e0e0", height=14, width=max_w)
        bar_bg.pack(side="left", padx=(4, 8))
        bar_bg.pack_propagate(False)
        fill_w = max(2, int(value / 100 * max_w))
        tk.Frame(bar_bg, bg=score_color(value), height=14, width=fill_w).place(x=0, y=0)
        tk.Label(row, text=f"{value:.0f}/100", bg=CARD,
                 font=FONT_SMALL, fg=score_color(value)).pack(side="left")

    # ── build UI ──────────────────────────────────

    def build_ui(self):

        # INPUT
        c1 = self.card("Customer Feedback")
        self.text = tk.Text(c1, height=7, font=FONT_TEXT, relief="solid", bd=1)
        self.text.pack(fill="x", pady=(0, 8))

        self.compare_var = tk.BooleanVar()
        comp_row = tk.Frame(c1, bg=CARD)
        comp_row.pack(anchor="w", pady=(0, 4))
        tk.Checkbutton(comp_row, text="Compare with previous period",
                       variable=self.compare_var, bg=CARD,
                       command=self.toggle_compare).pack(side="left")

        self.compare_frame = tk.Frame(c1, bg=CARD)
        tk.Label(self.compare_frame, text="Previous period feedback:",
                 bg=CARD, font=FONT_SMALL).pack(anchor="w")
        self.compare_text = tk.Text(self.compare_frame, height=5, font=FONT_TEXT,
                                    relief="solid", bd=1)
        self.compare_text.pack(fill="x", pady=(2, 4))

        btns = tk.Frame(c1, bg=CARD)
        btns.pack(anchor="w", pady=(4, 0))
        tk.Button(btns, text="Analyze",       bg=PRIMARY,   fg="white", relief="flat",
                  command=self.run,            padx=10).pack(side="left", padx=(0, 6))
        tk.Button(btns, text="Import CSV",    bg="#546e7a",  fg="white", relief="flat",
                  command=self.import_csv,     padx=10).pack(side="left", padx=(0, 6))
        tk.Button(btns, text="Export report", bg=ACCENT,    fg="white", relief="flat",
                  command=self.export,         padx=10).pack(side="left", padx=(0, 6))
        tk.Button(btns, text="Clear history", bg="#b71c1c", fg="white", relief="flat",
                  command=self.clear_history,  padx=10).pack(side="left")

        # CONFIDENCE
        c_conf = self.card("Analysis confidence")
        self.conf_label = tk.Label(c_conf, text="—", bg=CARD, font=FONT_TEXT)
        self.conf_label.pack(anchor="w")

        # RESULTS
        c2 = self.card("Results")
        self.output = tk.Label(c2, text="", bg=CARD, justify="left", font=FONT_TEXT)
        self.output.pack(anchor="w")

        # CATEGORY SCORES
        c3 = self.card("Category scores")
        self.cat_frame = tk.Frame(c3, bg=CARD)
        self.cat_frame.pack(fill="x")

        # COMPARISON
        c_cmp = self.card("Period comparison")
        self.compare_result = tk.Label(c_cmp, text="Enable comparison above to compare two periods.",
                                       bg=CARD, font=FONT_TEXT, justify="left")
        self.compare_result.pack(anchor="w")

        # MANAGER INSIGHT
        c4 = self.card("Manager insight")
        self.manager = tk.Label(c4, text="", bg=CARD, font=FONT_TEXT, justify="left")
        self.manager.pack(anchor="w")

        # WHAT TO FIX
        c5 = self.card("What to fix today  (sorted by urgency)")
        self.fix_frame = tk.Frame(c5, bg=CARD)
        self.fix_frame.pack(fill="x")

        # NEGATIVE / POSITIVE FEEDBACK
        c6 = self.card("Feedback detail")
        self.neg_box = tk.Text(c6, height=8, font=FONT_TEXT, relief="solid", bd=1)
        self.neg_box.tag_config("neg",  foreground=RED,    font=("Segoe UI", 10))
        self.neg_box.tag_config("pos",  foreground=GREEN,  font=("Segoe UI", 10))
        self.neg_box.tag_config("head", foreground="#666", font=("Segoe UI", 9, "italic"))
        self.neg_box.pack(fill="x")

        # TREND CHART
        c7 = self.card("Sentiment trend")
        self.chart = tk.Canvas(c7, width=720, height=250, bg="white", highlightthickness=0)
        self.chart.pack()
        leg = tk.Frame(c7, bg=CARD)
        leg.pack(anchor="w", pady=(4, 0))
        for color, label in [("#555","Overall"),(PRIMARY,"Food"),(ACCENT,"Service"),(ORANGE,"Cleanliness")]:
            tk.Frame(leg, bg=color, width=12, height=12).pack(side="left", padx=(4, 2))
            tk.Label(leg, text=label, bg=CARD, font=FONT_SMALL).pack(side="left", padx=(0, 10))

        # HISTORY TABLE
        c8 = self.card("Session history")
        self.history_box = tk.Text(c8, height=6, font=("Courier New", 9),
                                   relief="solid", bd=1, state="disabled")
        self.history_box.pack(fill="x")
        self._refresh_history_box()

    # ── toggle compare ────────────────────────────

    def toggle_compare(self):
        if self.compare_var.get():
            self.compare_frame.pack(fill="x", pady=(0, 6))
        else:
            self.compare_frame.pack_forget()

    # ── import CSV ────────────────────────────────

    def import_csv(self):
        file = filedialog.askopenfilename(filetypes=[("CSV/Text files", "*.csv *.txt")])
        if not file:
            return
        try:
            with open(file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, "\n".join(lines))
        except Exception as e:
            messagebox.showerror("Import error", str(e))

    # ── run ───────────────────────────────────────

    def run(self):
        txt = self.text.get("1.0", tk.END).strip()
        if not txt:
            messagebox.showwarning("Empty", "Please enter some feedback first.")
            return

        comp_txt = None
        if self.compare_var.get():
            comp_txt = self.compare_text.get("1.0", tk.END).strip() or None

        result, compare = analyze_feedback(txt, comp_txt)
        if result is None:
            return

        score          = result["score"]
        mood           = result["mood"]
        issues         = result["issues"]
        rec            = result["rec"]
        summary        = result["summary"]
        negatives      = result["negative_lines"]
        positives      = result["positive_lines"]
        scores_display = result["scores_display"]
        fixes          = result["fixes"]
        confidence     = result["confidence"]
        n_lines        = result["n_lines"]

        # luottamusväli
        conf_colors = {"High": GREEN, "Medium": ORANGE, "Low": RED}
        self.conf_label.config(
            text=f"Confidence: {confidence}  ({n_lines} feedback line{'s' if n_lines != 1 else ''})",
            fg=conf_colors[confidence]
        )

        # tulokset
        self.last_report = (
            f"Score: {score}/100\n"
            f"Mood: {mood}\n"
            f"Issues: {', '.join(issues) if issues else 'none'}\n"
            f"Recommendation: {rec}\n"
            f"Summary: {summary}\n"
        )
        self.output.config(text=self.last_report)

        # kategoriapisteet
        for w in self.cat_frame.winfo_children():
            w.destroy()
        if scores_display:
            for cat, val in scores_display.items():
                self.make_score_bar(self.cat_frame, cat, val)
        else:
            tk.Label(self.cat_frame, text="No category data", bg=CARD,
                     font=FONT_SMALL).pack(anchor="w")

        # vertailu
        if compare:
            diff  = result["score"] - compare["score"]
            sign  = "+" if diff >= 0 else ""
            lines = [
                f"This period:  {result['score']}/100  ({result['mood']})",
                f"Last period:  {compare['score']}/100  ({compare['mood']})",
                f"Change:       {sign}{diff} points",
                "",
            ]
            for cat in ["Food", "Service", "Cleanliness"]:
                a = result["scores_display"].get(cat)
                b = compare["scores_display"].get(cat)
                if a is not None and b is not None:
                    d = a - b
                    lines.append(f"  {cat:<14} {a:.0f}  vs  {b:.0f}  ({'+'if d>=0 else ''}{d:.0f})")
            self.compare_result.config(text="\n".join(lines))
        else:
            self.compare_result.config(
                text="Enable comparison above to compare two periods.")

        # manager insight
        if score < 40:
            self.manager.config(
                text="⚠  Experience is declining. Immediate action needed.", fg=RED)
        elif score < 60:
            self.manager.config(
                text="~  Mixed feedback. Several areas need attention.", fg=ORANGE)
        else:
            self.manager.config(
                text="✓  Performance is good. Keep it up!", fg=GREEN)

        # what to fix
        for w in self.fix_frame.winfo_children():
            w.destroy()
        if fixes:
            for rank, (label, count) in enumerate(fixes):
                color  = RED if rank == 0 else ORANGE if rank == 1 else "#888"
                bullet = "●" if rank == 0 else "●" if rank == 1 else "●"
                row = tk.Frame(self.fix_frame, bg=CARD)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=bullet, bg=CARD, fg=color,
                         font=("Segoe UI", 14)).pack(side="left", padx=(0, 6))
                tk.Label(row, text=f"{label}  (mentioned {count}×)",
                         bg=CARD, fg=color, font=FONT_TEXT).pack(side="left")
        else:
            tk.Label(self.fix_frame, text="✓  No urgent fixes",
                     bg=CARD, fg=GREEN, font=FONT_TEXT).pack(anchor="w")

        # feedback detail
        self.neg_box.config(state="normal")
        self.neg_box.delete("1.0", tk.END)
        if negatives:
            self.neg_box.insert(tk.END, "Negative  (most severe first):\n", "head")
            for line in negatives:
                self.neg_box.insert(tk.END, f"  ✗  {line}\n", "neg")
        if positives:
            self.neg_box.insert(tk.END, "\nPositive:\n", "head")
            for line in positives:
                self.neg_box.insert(tk.END, f"  ✓  {line}\n", "pos")
        if not negatives and not positives:
            self.neg_box.insert(tk.END, "No clear sentiment detected.", "head")
        self.neg_box.config(state="disabled")

        # tallenna historiaan
        entry = {
            "date":    datetime.now().strftime("%Y-%m-%d %H:%M"),
            "score":   score,
            "mood":    mood,
            "food":    scores_display.get("Food"),
            "service": scores_display.get("Service"),
            "clean":   scores_display.get("Cleanliness"),
        }
        self.history.append(entry)
        save_history(self.history)
        self._refresh_history_box()
        self.draw_chart()

    # ── export ────────────────────────────────────

    def export(self):
        if not self.last_report:
            messagebox.showwarning("Nothing to export", "Run an analysis first.")
            return
        file = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text file", "*.txt")])
        if file:
            with open(file, "w", encoding="utf-8") as f:
                f.write(self.last_report)
            messagebox.showinfo("Saved", "Report exported successfully.")

    # ── clear history ─────────────────────────────

    def clear_history(self):
        if messagebox.askyesno("Clear history", "Delete all saved history?"):
            self.history = []
            save_history(self.history)
            self._refresh_history_box()
            self.draw_chart()

    # ── history box ───────────────────────────────

    def _refresh_history_box(self):
        self.history_box.config(state="normal")
        self.history_box.delete("1.0", tk.END)
        if not self.history:
            self.history_box.insert(tk.END, "No history yet.")
        else:
            header = f"{'Date':<18}  {'Score':>5}  {'Mood':<9}  {'Food':>5}  {'Svc':>5}  {'Clean':>6}\n"
            self.history_box.insert(tk.END, header)
            self.history_box.insert(tk.END, "─" * 60 + "\n")
            for e in reversed(self.history[-20:]):
                food  = f"{e['food']:.0f}"    if e["food"]    is not None else "  —"
                svc   = f"{e['service']:.0f}" if e["service"] is not None else "  —"
                clean = f"{e['clean']:.0f}"   if e["clean"]   is not None else "   —"
                self.history_box.insert(
                    tk.END,
                    f"{e['date']:<18}  {e['score']:>5}  {e['mood']:<9}  {food:>5}  {svc:>5}  {clean:>6}\n"
                )
        self.history_box.config(state="disabled")

    # ── chart ─────────────────────────────────────

    def draw_chart(self):
        self.chart.delete("all")
        entries = self.history[-20:]
        if not entries:
            return

        W, H   = 720, 250
        pad_l  = 44
        pad_r  = 20
        pad_t  = 24
        pad_b  = 34
        plot_w = W - pad_l - pad_r
        plot_h = H - pad_t - pad_b

        # grid
        for i in range(6):
            val = i * 20
            y   = pad_t + plot_h - int(val / 100 * plot_h)
            self.chart.create_line(pad_l, y, W - pad_r, y, fill="#e8e8e8")
            self.chart.create_text(pad_l - 6, y, text=str(val),
                                   anchor="e", font=("Segoe UI", 8), fill="#aaa")

        n = len(entries)

        def xp(i):
            return pad_l + (int(i / (n - 1) * plot_w) if n > 1 else plot_w // 2)

        def yp(v):
            return pad_t + plot_h - int(v / 100 * plot_h)

        series = [
            ("score",   "#888888", 2),
            ("food",    PRIMARY,   2),
            ("service", ACCENT,    2),
            ("clean",   ORANGE,    2),
        ]

        for key, color, lw in series:
            pts = [(xp(i), yp(e[key])) for i, e in enumerate(entries)
                   if e.get(key) is not None]
            if len(pts) >= 2:
                for j in range(len(pts) - 1):
                    self.chart.create_line(
                        pts[j][0], pts[j][1], pts[j+1][0], pts[j+1][1],
                        fill=color, width=lw, smooth=True
                    )
            for px, py in pts:
                self.chart.create_oval(px-3, py-3, px+3, py+3,
                                       fill=color, outline="white", width=1)

        # X-labels
        for i, e in enumerate(entries):
            if n <= 10 or i % max(1, n // 8) == 0:
                self.chart.create_text(
                    xp(i), H - pad_b + 16,
                    text=e["date"][5:16],
                    font=("Segoe UI", 7), fill="#999"
                )

        self.chart.create_text(W // 2, 12, text="Sentiment trend over time",
                               font=("Segoe UI", 9), fill="#666")


# =========================
# RUN
# =========================

root = tk.Tk()
App(root)
root.mainloop()