from __future__ import annotations

import threading
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .abbreviations import ABBREVIATIONS, AbbreviationEntry
from .core import ConversionError, SmilesRecord, convert_files, smiles_to_record, validate_replacement_fragment, write_csv
from .ocsr import OCSRError


APP_NAME = "Dye2SMILES"


SMILES_GUIDE = """SMILES 是一种把分子结构写成一行文本的方法。Dye2SMILES 输出的是 RDKit canonical SMILES，但图片识别结果仍建议人工检查。

常见符号

C / N / O / S / P / F / Cl / Br / I
  大写通常表示脂肪族原子，例如 C 是普通碳，N 是普通氮。

c / n / o / s
  小写通常表示芳香体系里的原子，例如苯环常写成 c1ccccc1。

=
  双键。例如 C=O 是羰基，C=C 是碳碳双键。

#
  三键。例如 C#N 是腈基。

( )
  分支。括号里的部分是从前一个原子长出来的支链。

[ ]
  明确写原子、电荷、同位素或特殊价态。例如 [N+] 是带正电的氮，[Br-] 是溴负离子。

.
  分开的组分或盐。例如 [N+].[Br-] 表示阳离子和溴负离子不是共价键连接。

/ 和 \\
  双键几何构型标记，用来描述 E/Z 或顺反信息。图片识别时这类符号最容易出错，建议重点核对。

数字 1、2、3...
  环闭合标记。比如 c1ccccc1 表示一个六元芳香环。

*
  未知原子或连接点，不是完整结构。通常来自图片里的缩写基团，例如 DMPE、PEG 等没有展开。

快速检查建议

1. 如果看到 *，说明还有未知/缩写基团，没有得到完整 SMILES。
2. 如果看到 .，说明结果包含盐、反离子或多个分子片段，需要确认是不是原图想表达的。
3. 如果有 [N+]、[O-]、[Br-]，重点检查电荷和反离子是否正确。
4. 如果分子有双键立体化学，重点检查 / 和 \\ 是否和原图方向一致。
"""


PALETTES = {
    "light": {
        "app_bg": "#f5f7fb",
        "header_bg": "#eef3fb",
        "surface": "#ffffff",
        "surface_alt": "#f8fafc",
        "surface_header": "#edf2f7",
        "border": "#d8e0ea",
        "text": "#172033",
        "muted": "#5c667a",
        "subtle": "#6b7280",
        "chip_bg": "#dfe8f5",
        "chip_text": "#26364f",
        "primary": "#2457d6",
        "primary_active": "#1f49b6",
        "primary_pressed": "#1a3f9e",
        "primary_disabled": "#9eb2e5",
        "secondary_active": "#eef3fb",
        "secondary_pressed": "#e2e8f0",
        "secondary_disabled": "#f1f5f9",
        "secondary_disabled_text": "#94a3b8",
        "selection_bg": "#dbeafe",
        "selection_text": "#102a56",
        "error_bg": "#fff1f2",
        "error_text": "#9f1239",
        "warning_bg": "#fff7ed",
        "warning_text": "#9a3412",
        "scrollbar": "#dce5f0",
    },
    "dark": {
        "app_bg": "#111827",
        "header_bg": "#172033",
        "surface": "#0f172a",
        "surface_alt": "#162036",
        "surface_header": "#1e293b",
        "border": "#334155",
        "text": "#e5edf7",
        "muted": "#a7b0c0",
        "subtle": "#8f9aad",
        "chip_bg": "#24324a",
        "chip_text": "#dbeafe",
        "primary": "#5b8cff",
        "primary_active": "#78a3ff",
        "primary_pressed": "#3f6fe0",
        "primary_disabled": "#334c83",
        "secondary_active": "#1e293b",
        "secondary_pressed": "#26364f",
        "secondary_disabled": "#172033",
        "secondary_disabled_text": "#6b7280",
        "selection_bg": "#1d4ed8",
        "selection_text": "#eff6ff",
        "error_bg": "#3a1820",
        "error_text": "#fecdd3",
        "warning_bg": "#33220f",
        "warning_text": "#fed7aa",
        "scrollbar": "#475569",
    },
}


def system_prefers_dark_mode() -> bool:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _value_type = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except OSError:
            return False

    try:
        completed = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and completed.stdout.strip().lower() == "dark"


class LCSmilesApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1080x680")
        self.minsize(900, 540)
        self.dark_mode = system_prefers_dark_mode()
        self.palette = PALETTES["dark" if self.dark_mode else "light"]
        self.configure(bg=self.palette["app_bg"])
        self.records: list[SmilesRecord] = []
        self.selected_paths: list[Path] = []
        self.selected_abbreviation: AbbreviationEntry | None = None
        self.active_replacement_smiles: str | None = None
        self.active_replacement_label: str | None = None
        self.status_var = tk.StringVar(value="请选择文件开始转换")
        self.selection_var = tk.StringVar(value="未选择文件")

        self._configure_styles()
        self._build_ui()
        self._watch_system_theme()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        palette = self.palette
        self.configure(bg=palette["app_bg"])

        style.configure("App.TFrame", background=palette["app_bg"])
        style.configure("Header.TFrame", background=palette["header_bg"])
        style.configure("Toolbar.TFrame", background=palette["app_bg"])
        style.configure("TableWrap.TFrame", background=palette["border"], borderwidth=1, relief="solid")
        style.configure("Footer.TFrame", background=palette["app_bg"])

        style.configure(
            "Title.TLabel",
            background=palette["header_bg"],
            foreground=palette["text"],
            font=("Helvetica", 25, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=palette["header_bg"],
            foreground=palette["muted"],
            font=("Helvetica", 12),
        )
        style.configure(
            "Selection.TLabel",
            background=palette["chip_bg"],
            foreground=palette["chip_text"],
            padding=(12, 7),
            font=("Helvetica", 11, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=palette["app_bg"],
            foreground=palette["muted"],
            font=("Helvetica", 11),
        )
        style.configure(
            "Footer.TLabel",
            background=palette["app_bg"],
            foreground=palette["subtle"],
            font=("Helvetica", 10),
        )

        style.configure(
            "Primary.TButton",
            background=palette["primary"],
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(16, 9),
            font=("Helvetica", 11, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", palette["primary_active"]),
                ("pressed", palette["primary_pressed"]),
                ("disabled", palette["primary_disabled"]),
            ],
            foreground=[("disabled", "#edf2ff")],
        )
        style.configure(
            "Secondary.TButton",
            background=palette["surface"],
            foreground=palette["chip_text"],
            bordercolor=palette["border"],
            lightcolor=palette["surface"],
            darkcolor=palette["border"],
            borderwidth=1,
            focusthickness=0,
            padding=(14, 9),
            font=("Helvetica", 11),
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("active", palette["secondary_active"]),
                ("pressed", palette["secondary_pressed"]),
                ("disabled", palette["secondary_disabled"]),
            ],
            foreground=[("disabled", palette["secondary_disabled_text"])],
        )

        style.configure(
            "Treeview",
            background=palette["surface"],
            fieldbackground=palette["surface"],
            foreground=palette["text"],
            rowheight=34,
            borderwidth=0,
            font=("Helvetica", 11),
        )
        style.configure(
            "Treeview.Heading",
            background=palette["surface_header"],
            foreground=palette["text"],
            relief="flat",
            padding=(8, 9),
            font=("Helvetica", 11, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", palette["selection_bg"])],
            foreground=[("selected", palette["selection_text"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=palette["scrollbar"],
            troughcolor=palette["surface_alt"],
            bordercolor=palette["border"],
            arrowcolor=palette["muted"],
            darkcolor=palette["scrollbar"],
            lightcolor=palette["surface_header"],
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=palette["scrollbar"],
            troughcolor=palette["surface_alt"],
            bordercolor=palette["border"],
            arrowcolor=palette["muted"],
            darkcolor=palette["scrollbar"],
            lightcolor=palette["surface_header"],
        )
        style.configure(
            "Horizontal.TProgressbar",
            background=palette["primary"],
            troughcolor=palette["chip_bg"],
            bordercolor=palette["chip_bg"],
            lightcolor=palette["primary"],
            darkcolor=palette["primary"],
        )

        if hasattr(self, "table"):
            self._configure_table_tags()

    def _watch_system_theme(self) -> None:
        dark_mode = system_prefers_dark_mode()
        if dark_mode != self.dark_mode:
            self.dark_mode = dark_mode
            self.palette = PALETTES["dark" if dark_mode else "light"]
            self._configure_styles()
        self.after(2000, self._watch_system_theme)

    def _configure_table_tags(self) -> None:
        palette = self.palette
        self.table.tag_configure("odd", background=palette["surface"])
        self.table.tag_configure("even", background=palette["surface_alt"])
        self.table.tag_configure("error", background=palette["error_bg"], foreground=palette["error_text"])
        self.table.tag_configure("warning", background=palette["warning_bg"], foreground=palette["warning_text"])

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, padding=(24, 22, 24, 18), style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="本地分子结构转 RDKit canonical SMILES，支持 ChemDraw、Mol/SDF、截图和 PDF",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Label(header, textvariable=self.selection_var, style="Selection.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(18, 0)
        )

        toolbar = ttk.Frame(self, padding=(24, 16, 24, 14), style="Toolbar.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(7, weight=1)

        self.choose_button = ttk.Button(
            toolbar, text="添加文件", command=self.choose_files, style="Secondary.TButton"
        )
        self.convert_button = ttk.Button(
            toolbar, text="开始转换", command=self.convert_selected, style="Primary.TButton"
        )
        self.export_button = ttk.Button(toolbar, text="导出 CSV", command=self.export_csv, style="Secondary.TButton")
        self.copy_button = ttk.Button(toolbar, text="复制 SMILES", command=self.copy_smiles, style="Secondary.TButton")
        self.abbrev_button = ttk.Button(
            toolbar, text="缩写基团", command=self.show_abbreviation_dictionary, style="Secondary.TButton"
        )
        self.apply_abbrev_button = ttk.Button(
            toolbar, text="替换 *", command=self.apply_selected_abbreviation_to_results, style="Secondary.TButton"
        )

        self.choose_button.grid(row=0, column=0, padx=(0, 10))
        self.convert_button.grid(row=0, column=1, padx=(0, 10))
        ttk.Separator(toolbar, orient="vertical").grid(row=0, column=2, sticky="ns", padx=(2, 12))
        self.export_button.grid(row=0, column=3, padx=(0, 10))
        self.copy_button.grid(row=0, column=4, padx=(0, 10))
        self.abbrev_button.grid(row=0, column=5, padx=(0, 10))
        self.apply_abbrev_button.grid(row=0, column=6, padx=(0, 16))
        ttk.Label(toolbar, textvariable=self.status_var, anchor="e", style="Status.TLabel").grid(
            row=0, column=7, sticky="ew"
        )

        columns = ("smiles", "source", "index", "type", "status", "message")
        table_wrap = ttk.Frame(self, padding=1, style="TableWrap.TFrame")
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 0))
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)

        self.table = ttk.Treeview(table_wrap, columns=columns, show="headings", selectmode="extended")
        self.table.heading("smiles", text="RDKit SMILES")
        self.table.heading("source", text="来源文件")
        self.table.heading("index", text="序号")
        self.table.heading("type", text="类型")
        self.table.heading("status", text="状态")
        self.table.heading("message", text="信息")

        self.table.column("smiles", width=520, minwidth=320, stretch=False)
        self.table.column("source", width=270, minwidth=180, stretch=False)
        self.table.column("index", width=60, anchor="center", stretch=False)
        self.table.column("type", width=80, anchor="center", stretch=False)
        self.table.column("status", width=80, anchor="center", stretch=False)
        self.table.column("message", width=420, minwidth=220, stretch=False)

        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self._configure_table_tags()

        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.table.bind("<MouseWheel>", self._scroll_table_vertically)
        self.table.bind("<Shift-MouseWheel>", self._scroll_table_horizontally)
        self.table.bind("<Button-4>", self._scroll_table_vertically)
        self.table.bind("<Button-5>", self._scroll_table_vertically)

        footer = ttk.Frame(self, padding=(24, 12), style="Footer.TFrame")
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer,
            text="图片识别结果均需检查，尤其是手性楔线和双键顺反。macOS 打包版已内置 RDKit 和 OSRA。",
            style="Footer.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.guide_button = ttk.Button(
            footer, text="SMILES 符号说明", command=self.show_smiles_guide, style="Secondary.TButton"
        )
        self.guide_button.grid(row=0, column=1, sticky="e", padx=(12, 12))
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=170)
        self.progress.grid(row=0, column=2, sticky="e")
        self.progress.grid_remove()

    def show_abbreviation_dictionary(self) -> None:
        palette = self.palette
        window = tk.Toplevel(self)
        window.title("缩写基团字典")
        window.geometry("860x560")
        window.minsize(720, 460)
        window.configure(bg=palette["app_bg"])
        window.transient(self)

        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        window.rowconfigure(2, weight=1)

        ttk.Label(
            window,
            text="缩写基团字典",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 4))
        ttk.Label(
            window,
            text="同一个缩写可能代表不同结构；请结合原文、试剂名称或供应商信息选择。",
            style="Status.TLabel",
        ).grid(row=0, column=0, sticky="e", padx=18, pady=(16, 4))

        list_frame = ttk.Frame(window, padding=1, style="TableWrap.TFrame")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(10, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("abbr", "name", "category", "replaceable")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse", height=8)
        tree.heading("abbr", text="缩写")
        tree.heading("name", text="可能含义")
        tree.heading("category", text="类别")
        tree.heading("replaceable", text="自动替换")
        tree.column("abbr", width=90, anchor="center")
        tree.column("name", width=420, minwidth=240)
        tree.column("category", width=160, minwidth=110)
        tree.column("replaceable", width=90, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._bind_vertical_wheel(tree, tree.yview_scroll)

        for i, entry in enumerate(ABBREVIATIONS):
            tree.insert(
                "",
                "end",
                iid=str(i),
                values=(entry.short_name, entry.full_name, entry.category, "可用" if entry.replacement_smiles else "说明"),
            )

        detail = tk.Text(
            window,
            height=8,
            wrap="word",
            bg=palette["surface"],
            fg=palette["text"],
            insertbackground=palette["text"],
            relief="flat",
            padx=14,
            pady=12,
            font=("Helvetica", 12),
        )
        detail.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 8))
        self._bind_vertical_wheel(detail, detail.yview_scroll)

        edit_row = ttk.Frame(window, padding=(18, 0, 18, 8), style="Footer.TFrame")
        edit_row.grid(row=3, column=0, sticky="ew")
        edit_row.columnconfigure(1, weight=1)
        replacement_var = tk.StringVar()
        ttk.Label(edit_row, text="替换片段 SMILES:", style="Footer.TLabel").grid(row=0, column=0, sticky="w")
        replacement_entry = ttk.Entry(edit_row, textvariable=replacement_var)
        replacement_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        def selected_entry() -> AbbreviationEntry | None:
            selection = tree.selection()
            if not selection:
                return None
            return ABBREVIATIONS[int(selection[0])]

        def set_detail(entry: AbbreviationEntry | None) -> None:
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            if entry is not None:
                detail.insert("end", self._format_abbreviation_detail(entry))
                replacement_var.set(entry.replacement_smiles or "")
            detail.configure(state="disabled")

        def on_select(_event: tk.Event | None = None) -> None:
            set_detail(selected_entry())

        def set_active_replacement(entry: AbbreviationEntry | None) -> bool:
            replacement = replacement_var.get().strip()
            if replacement:
                try:
                    validate_replacement_fragment(replacement)
                except ConversionError as exc:
                    messagebox.showerror(APP_NAME, str(exc), parent=window)
                    return False
            self.selected_abbreviation = entry
            self.active_replacement_smiles = replacement or None
            self.active_replacement_label = entry.short_name if entry is not None else "手动片段"
            if self.active_replacement_smiles:
                self.status_var.set(f"已选择 {self.active_replacement_label}；转换和替换时会展开 *")
            elif entry is not None:
                self.status_var.set(f"已选择缩写说明：{entry.short_name}（该条目不能自动替换）")
            return True

        def choose_current() -> None:
            entry = selected_entry()
            if entry is None:
                return
            if set_active_replacement(entry):
                window.destroy()

        def apply_current() -> None:
            entry = selected_entry()
            if set_active_replacement(entry):
                self.apply_selected_abbreviation_to_results(parent=window)

        def copy_current() -> None:
            entry = selected_entry()
            if entry is None:
                return
            self.clipboard_clear()
            self.clipboard_append(self._format_abbreviation_detail(entry))
            self.status_var.set(f"已复制缩写说明：{entry.short_name}")

        tree.bind("<<TreeviewSelect>>", on_select)
        tree.bind("<Double-1>", lambda _event: choose_current())
        tree.selection_set("0")
        tree.focus("0")
        set_detail(ABBREVIATIONS[0])

        button_row = ttk.Frame(window, padding=(18, 4, 18, 16), style="Footer.TFrame")
        button_row.grid(row=4, column=0, sticky="ew")
        button_row.columnconfigure(0, weight=1)
        ttk.Button(button_row, text="复制说明", command=copy_current, style="Secondary.TButton").grid(
            row=0, column=1, padx=(0, 10)
        )
        ttk.Button(button_row, text="选择此片段", command=choose_current, style="Primary.TButton").grid(
            row=0, column=2, padx=(0, 10)
        )
        ttk.Button(button_row, text="应用到结果", command=apply_current, style="Secondary.TButton").grid(
            row=0, column=3, padx=(0, 10)
        )
        ttk.Button(button_row, text="关闭", command=window.destroy, style="Secondary.TButton").grid(row=0, column=4)

    def _format_abbreviation_detail(self, entry: AbbreviationEntry) -> str:
        return (
            f"缩写：{entry.short_name}\n"
            f"可能含义：{entry.full_name}\n"
            f"类别：{entry.category}\n"
            f"结构提示：{entry.structure_hint}\n\n"
            f"可替换片段：{entry.replacement_smiles or '无唯一片段，需人工确认'}\n\n"
            f"注意：{entry.note}\n\n"
            "使用建议：如果识别结果里出现 *，可以选择一个带可替换片段的缩写并点击“替换 *”。"
            "如果条目没有可替换片段，请先手动填写一个含 [*:1] 的片段 SMILES。"
        )

    def show_smiles_guide(self) -> None:
        palette = self.palette
        window = tk.Toplevel(self)
        window.title("SMILES 符号说明")
        window.geometry("760x620")
        window.minsize(620, 480)
        window.configure(bg=palette["app_bg"])
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

        frame = ttk.Frame(window, padding=18, style="App.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        text = tk.Text(
            frame,
            wrap="word",
            bg=palette["surface"],
            fg=palette["text"],
            insertbackground=palette["text"],
            relief="flat",
            padx=16,
            pady=16,
            font=("Helvetica", 12),
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._bind_vertical_wheel(text, text.yview_scroll)
        text.insert("1.0", SMILES_GUIDE)
        text.configure(state="disabled")

        ttk.Button(frame, text="关闭", command=window.destroy, style="Secondary.TButton").grid(
            row=1, column=0, columnspan=2, sticky="e", pady=(12, 0)
        )

    def choose_files(self) -> None:
        filetypes = [
            ("Supported files", "*.cdxml *.cdx *.mol *.sdf *.smi *.smiles *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.pdf"),
            ("ChemDraw", "*.cdxml *.cdx"),
            ("Molecule files", "*.mol *.sdf *.smi *.smiles"),
            ("Images/PDF", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.pdf"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="选择分子结构文件", filetypes=filetypes)
        if not paths:
            return
        self.selected_paths = [Path(p) for p in paths]
        count = len(self.selected_paths)
        self.selection_var.set(f"已选择 {count} 个文件")
        self.status_var.set("准备转换")

    def convert_selected(self) -> None:
        if not self.selected_paths:
            messagebox.showinfo(APP_NAME, "请先选择文件。")
            return

        replacement_smiles = self.active_replacement_smiles
        replacement_label = self.active_replacement_label
        self._set_busy(True)
        self._clear_table()
        thread = threading.Thread(
            target=self._convert_in_background,
            args=(replacement_smiles, replacement_label),
            daemon=True,
        )
        thread.start()

    def _convert_in_background(
        self,
        replacement_smiles: str | None,
        replacement_label: str | None,
    ) -> None:
        try:
            records = convert_files(
                self.selected_paths,
                dummy_replacement_smiles=replacement_smiles,
                dummy_replacement_label=replacement_label,
            )
        except (ConversionError, OCSRError) as exc:
            self.after(0, lambda: self._show_error(str(exc)))
            return
        self.after(0, lambda: self._set_records(records))

    def _set_records(self, records: list[SmilesRecord]) -> None:
        self._set_busy(False)
        self.records = records
        self._clear_table()
        self._render_records()
        warning_count = sum(1 for record in records if record.status == "warning")
        error_count = sum(1 for record in records if record.status == "error")
        if error_count:
            self.status_var.set(f"转换完成：{len(records)} 条结果，{error_count} 条失败，{warning_count} 条需检查")
        elif warning_count:
            self.status_var.set(f"转换完成：{len(records)} 条结果，{warning_count} 条需检查")
        else:
            self.status_var.set(f"转换完成：{len(records)} 条结果")

    def _render_records(self) -> None:
        for row_number, record in enumerate(self.records):
            if record.status == "error":
                tag = "error"
            elif record.status == "warning":
                tag = "warning"
            else:
                tag = "even" if row_number % 2 else "odd"
            self.table.insert(
                "",
                "end",
                tags=(tag,),
                values=(
                    record.smiles,
                    Path(record.source).name,
                    record.index,
                    record.input_type,
                    self._status_label(record.status),
                    record.message,
                ),
            )
        self._autosize_table_columns()

    def _autosize_table_columns(self) -> None:
        if not self.records:
            return

        font = tkfont.Font(font=("Helvetica", 11))
        bold_font = tkfont.Font(font=("Helvetica", 11, "bold"))
        headings = {
            "smiles": "RDKit SMILES",
            "source": "来源文件",
            "index": "序号",
            "type": "类型",
            "status": "状态",
            "message": "信息",
        }
        min_widths = {
            "smiles": 520,
            "source": 270,
            "index": 60,
            "type": 80,
            "status": 80,
            "message": 420,
        }
        max_widths = {
            "smiles": 10000,
            "source": 900,
            "index": 90,
            "type": 120,
            "status": 120,
            "message": 3000,
        }
        values_by_column = {
            "smiles": [record.smiles for record in self.records],
            "source": [Path(record.source).name for record in self.records],
            "index": [str(record.index) for record in self.records],
            "type": [record.input_type for record in self.records],
            "status": [self._status_label(record.status) for record in self.records],
            "message": [record.message for record in self.records],
        }

        for column, values in values_by_column.items():
            measured = [font.measure(value) for value in values if value]
            heading_width = bold_font.measure(headings[column])
            width = max([heading_width, min_widths[column], *measured]) + 28
            self.table.column(column, width=min(width, max_widths[column]), stretch=False)

    def _scroll_table_horizontally(self, event: tk.Event) -> str:
        self.table.xview_scroll(self._scroll_units_from_event(event), "units")
        return "break"

    def _scroll_table_vertically(self, event: tk.Event) -> str:
        self.table.yview_scroll(self._scroll_units_from_event(event), "units")
        return "break"

    def _bind_vertical_wheel(self, widget: tk.Widget, scroll_command) -> None:
        def on_wheel(event: tk.Event) -> str:
            scroll_command(self._scroll_units_from_event(event), "units")
            return "break"

        widget.bind("<MouseWheel>", on_wheel)
        widget.bind("<Button-4>", on_wheel)
        widget.bind("<Button-5>", on_wheel)

    def _scroll_units_from_event(self, event: tk.Event) -> int:
        button = getattr(event, "num", None)
        if button == 4:
            return -1
        if button == 5:
            return 1

        delta = getattr(event, "delta", 0)
        if abs(delta) >= 120:
            return -int(delta / 120)
        return -1 if delta > 0 else 1

    def _status_label(self, status: str) -> str:
        return {
            "ok": "完成",
            "warning": "需检查",
            "error": "失败",
        }.get(status, status)

    def apply_selected_abbreviation_to_results(self, parent: tk.Misc | None = None) -> None:
        if not self.records:
            messagebox.showinfo(APP_NAME, "没有可替换的结果。", parent=parent or self)
            return
        if not self.active_replacement_smiles:
            messagebox.showinfo(APP_NAME, "请先在“缩写基团”里选择或填写一个可替换片段。", parent=parent or self)
            return

        selected_items = self.table.selection()
        if selected_items:
            target_indexes = [self.table.index(item) for item in selected_items]
        else:
            target_indexes = [i for i, record in enumerate(self.records) if "*" in record.smiles]

        if not target_indexes:
            messagebox.showinfo(APP_NAME, "没有找到包含 * 的结果。", parent=parent or self)
            return

        updated = list(self.records)
        changed = 0
        failed = 0
        for index in target_indexes:
            record = self.records[index]
            if "*" not in record.smiles:
                continue
            expanded = smiles_to_record(
                record.smiles,
                source=record.source,
                index=record.index,
                input_type=record.input_type,
                dummy_replacement_smiles=self.active_replacement_smiles,
                dummy_replacement_label=self.active_replacement_label,
            )
            updated[index] = expanded
            if expanded.status == "error":
                failed += 1
            else:
                changed += 1

        self.records = updated
        self._clear_table()
        self._render_records()
        self.status_var.set(f"已替换 {changed} 条含 * 的结果" + (f"，{failed} 条失败" if failed else ""))

    def _show_error(self, text: str) -> None:
        self._set_busy(False)
        self.status_var.set("转换失败")
        messagebox.showerror(APP_NAME, text)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.choose_button.configure(state=state)
        self.convert_button.configure(state=state)
        self.export_button.configure(state=state)
        self.copy_button.configure(state=state)
        self.abbrev_button.configure(state=state)
        self.apply_abbrev_button.configure(state=state)
        if busy:
            self.status_var.set("正在转换...")
            self.progress.grid()
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def _clear_table(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)

    def copy_smiles(self) -> None:
        if not self.records:
            return
        selected = self.table.selection()
        if selected:
            smiles = [self.table.item(item, "values")[0] for item in selected]
        else:
            smiles = [record.smiles for record in self.records if record.status != "error"]
        self.clipboard_clear()
        self.clipboard_append("\n".join(smiles))
        self.status_var.set(f"已复制 {len(smiles)} 条 SMILES")

    def export_csv(self) -> None:
        if not self.records:
            messagebox.showinfo(APP_NAME, "没有可导出的结果。")
            return
        output = filedialog.asksaveasfilename(
            title="导出 CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not output:
            return
        write_csv(self.records, output)
        self.status_var.set(f"已导出：{output}")


def main() -> None:
    app = LCSmilesApp()
    app.mainloop()


if __name__ == "__main__":
    main()
