import os
import sqlite3
import sys
import tempfile
import pandas as pd
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import seaborn as sns


APP_NAME = "HealthcareAnalyticsDashboard"

if getattr(sys, "frozen", False):
    APP_DATA_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        APP_NAME,
    )
else:
    APP_DATA_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(APP_DATA_DIR, exist_ok=True)

DB_NAME = os.path.join(APP_DATA_DIR, "healthcare.db")
CSV_FILE = os.path.join(APP_DATA_DIR, "healthcare.csv")
DATASET_DATABASES = {}
ROWS_PER_DATABASE = 500
RECORD_COLUMNS = (
    "patient_id",
    "description",
    "medical_specialty",
    "sample_name",
    "transcription",
    "keywords",
)
PLOT_TYPES = [
    "Bar Plot",
    "Line Plot",
    "Histogram",
    "Scatter Plot",
    "Box Plot",
    "Pie Chart",
    "Heatmap",
    "Count Plot",
    "Regression Plot",
    "Area Plot",
]
NUMERIC_FEATURES = [
    "patient_id",
    "description_length",
    "sample_name_length",
    "keyword_count",
    "transcription_length",
]


def create_database():
    global DB_NAME

    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS healthcare_records (
            patient_id INTEGER PRIMARY KEY,
            description TEXT,
            medical_specialty TEXT,
            sample_name TEXT,
            transcription TEXT,
            keywords TEXT
        )
        """)
        conn.commit()
    finally:
        conn.close()

    DATASET_DATABASES.clear()
    dataset_files = []
    for filename in os.listdir(APP_DATA_DIR):
        if not filename.startswith("data_set") or not filename.endswith(".db"):
            continue

        dataset_number = filename[len("data_set"):-len(".db")]
        if dataset_number.isdigit():
            dataset_files.append((int(dataset_number), filename))

    for dataset_number, filename in sorted(dataset_files):
        DATASET_DATABASES[f"Data {dataset_number}"] = os.path.join(
            APP_DATA_DIR, filename
        )

    if not DATASET_DATABASES:
        conn = sqlite3.connect(DB_NAME)
        try:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM healthcare_records"
            ).fetchone()[0]
        finally:
            conn.close()

        if row_count:
            DATASET_DATABASES["Healthcare"] = DB_NAME

    if DATASET_DATABASES:
        first_database = next(iter(DATASET_DATABASES.values()))
        if os.path.basename(first_database).startswith("data_set"):
            DB_NAME = first_database


def refresh_database_selector():
    database_names = list(DATASET_DATABASES)
    options = ["All Databases", *database_names]
    database_selector.configure(values=options)

    if database_filter.get() not in options:
        database_filter.set(options[0])

    load_records()


def enable_drag_and_drop(widget, callback):
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        WM_DROPFILES = 0x0233
        GWL_WNDPROC = -4

        shell32.DragQueryFileW.argtypes = (
            wintypes.HANDLE,
            wintypes.UINT,
            wintypes.LPWSTR,
            wintypes.UINT,
        )

        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        user32.CallWindowProcW.argtypes = (
            ctypes.c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        set_window_proc = getattr(
            user32,
            "SetWindowLongPtrW",
            user32.SetWindowLongW,
        )
        set_window_proc.restype = ctypes.c_void_p
        set_window_proc.argtypes = (
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_void_p,
        )

        wnd_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        class DropTarget:
            def __init__(self, hwnd):
                self.hwnd = hwnd
                self.old_proc = None

                self.proc = wnd_proc_type(self._wnd_proc)

            def hook(self):
                shell32.DragAcceptFiles(self.hwnd, True)

                self.old_proc = set_window_proc(
                    self.hwnd,
                    GWL_WNDPROC,
                    self.proc,
                )

            def _wnd_proc(self, hwnd, msg, wparam, lparam):
                if msg == WM_DROPFILES:
                    self._handle_drop(wparam)
                    return 0

                return user32.CallWindowProcW(
                    self.old_proc,
                    hwnd,
                    msg,
                    wparam,
                    lparam,
                )

            def _handle_drop(self, hdrop):
                count = shell32.DragQueryFileW(
                    hdrop, 0xFFFFFFFF, None, 0
                )

                files = []
                buffer = ctypes.create_unicode_buffer(wintypes.MAX_PATH)

                for index in range(count):
                    shell32.DragQueryFileW(
                        hdrop, index, buffer, wintypes.MAX_PATH
                    )
                    files.append(buffer.value)

                shell32.DragFinish(hdrop)

                if files:
                    callback(files)

        widget.update_idletasks()

        hwnd = widget.winfo_id()

        parent = user32.GetParent(hwnd)

        if parent:
            hwnd = parent

        drop_target = DropTarget(hwnd)
        drop_target.hook()

        widget.drop_target = drop_target

        return True

    except Exception as e:
        print(f"Drag-and-drop not available: {e}")
        return False


def browse_csv():
    filepath = filedialog.askopenfilename(
        title="Select CSV Dataset",
        filetypes=[
            ("CSV files", "*.csv"),
            ("All files", "*.*"),
        ],
    )

    if filepath:
        import_csv_from_path(filepath)


def import_csv_from_path(filepath):
    global CSV_FILE, DB_NAME

    if not filepath:
        return

    try:
        df = pd.read_csv(filepath)
        missing_columns = [
            column for column in RECORD_COLUMNS if column not in df.columns
        ]
        if missing_columns:
            raise ValueError(
                "CSV is missing required columns: "
                + ", ".join(missing_columns)
            )

        df = df.loc[:, list(RECORD_COLUMNS)]
        dataset_count = max(
            1,
            (len(df) + ROWS_PER_DATABASE - 1) // ROWS_PER_DATABASE,
        )
        imported_databases = {}

        with tempfile.TemporaryDirectory(
            dir=APP_DATA_DIR,
            prefix=".dataset-import-",
        ) as staging_dir:
            for dataset_number in range(1, dataset_count + 1):
                start = (dataset_number - 1) * ROWS_PER_DATABASE
                dataset = df.iloc[start:start + ROWS_PER_DATABASE]
                staged_path = os.path.join(
                    staging_dir,
                    f"data_set{dataset_number}.db",
                )
                conn = sqlite3.connect(staged_path)
                try:
                    dataset.to_sql(
                        "healthcare_records",
                        conn,
                        if_exists="replace",
                        index=False,
                    )
                finally:
                    conn.close()

                imported_databases[f"Data {dataset_number}"] = os.path.join(
                    APP_DATA_DIR,
                    f"data_set{dataset_number}.db",
                )

            staged_csv = os.path.join(staging_dir, "healthcare.csv")
            df.to_csv(staged_csv, index=False)

            for dataset_name, staged_name in (
                (name, f"data_set{index}.db")
                for index, name in enumerate(imported_databases, start=1)
            ):
                os.replace(
                    os.path.join(staging_dir, staged_name),
                    imported_databases[dataset_name],
                )

            for filename in os.listdir(APP_DATA_DIR):
                if not filename.startswith("data_set") or not filename.endswith(".db"):
                    continue
                dataset_number = filename[len("data_set"):-len(".db")]
                if dataset_number.isdigit() and int(dataset_number) > dataset_count:
                    os.remove(os.path.join(APP_DATA_DIR, filename))

            os.replace(staged_csv, CSV_FILE)

        DATASET_DATABASES.clear()
        DATASET_DATABASES.update(imported_databases)
        DB_NAME = next(iter(imported_databases.values()))

        messagebox.showinfo(
            "Success",
            f"Dataset imported successfully!\n\n"
            f"Source: {os.path.basename(filepath)}\n"
            f"Records: {len(df)}\n"
            f"Databases created: {dataset_count} "
            f"({ROWS_PER_DATABASE} records maximum each)"
        )

        refresh_database_selector()

    except Exception as e:
        messagebox.showerror(
            "Error",
            str(e)
        )


def handle_dropped_files(files):
    csv_files = [f for f in files if f.lower().endswith(".csv")]

    if not csv_files:
        messagebox.showwarning(
            "Unsupported File",
            "Please drop a .csv file."
        )
        return

    import_csv_from_path(csv_files[0])


def add_record():
    try:
        patient_id = int(patient_id_entry.get())
        description = description_entry.get()
        medical_specialty = specialty_entry.get()
        sample_name = sample_name_entry.get()
        transcription = transcription_text.get(
            "1.0",
            "end"
        ).strip()
        keywords = keywords_entry.get()

        for database_path in DATASET_DATABASES.values():
            conn = sqlite3.connect(database_path)
            try:
                exists = conn.execute(
                    "SELECT 1 FROM healthcare_records WHERE patient_id = ?",
                    (patient_id,),
                ).fetchone()
            finally:
                conn.close()
            if exists:
                messagebox.showwarning(
                    "Duplicate",
                    "Patient ID already exists",
                )
                return

        new_record = pd.DataFrame({
            "patient_id": [patient_id],
            "description": [description],
            "medical_specialty": [medical_specialty],
            "sample_name": [sample_name],
            "transcription": [transcription],
            "keywords": [keywords]
        })

        if os.path.exists(CSV_FILE):
            master_df = pd.read_csv(CSV_FILE)
            if "patient_id" in master_df.columns and patient_id in pd.to_numeric(
                master_df["patient_id"],
                errors="coerce",
            ).values:
                messagebox.showwarning(
                    "Duplicate",
                    "Patient ID already exists",
                )
                return
            master_df = pd.concat(
                [master_df, new_record],
                ignore_index=True
            )
        else:
            master_df = new_record

        database_path = (
            list(DATASET_DATABASES.values())[-1]
            if DATASET_DATABASES
            else DB_NAME
        )
        if os.path.basename(database_path).startswith("data_set"):
            conn = sqlite3.connect(database_path)
            try:
                row_count = conn.execute(
                    "SELECT COUNT(*) FROM healthcare_records"
                ).fetchone()[0]
            finally:
                conn.close()

            if row_count >= ROWS_PER_DATABASE:
                dataset_number = max(
                    (
                        int(name[len("Data "):])
                        for name in DATASET_DATABASES
                    ),
                    default=0,
                ) + 1
                database_path = os.path.join(
                    APP_DATA_DIR,
                    f"data_set{dataset_number}.db",
                )
                conn = sqlite3.connect(database_path)
                try:
                    conn.execute("""
                    CREATE TABLE healthcare_records (
                        patient_id INTEGER PRIMARY KEY,
                        description TEXT,
                        medical_specialty TEXT,
                        sample_name TEXT,
                        transcription TEXT,
                        keywords TEXT
                    )
                    """)
                    conn.commit()
                finally:
                    conn.close()

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".csv",
            prefix=".healthcare-",
            dir=APP_DATA_DIR,
            delete=False,
        ) as staged_csv:
            staged_csv_path = staged_csv.name
        try:
            master_df.to_csv(staged_csv_path, index=False)
            conn = sqlite3.connect(database_path)
            try:
                conn.execute(
                    """
                    INSERT INTO healthcare_records
                    (
                        patient_id,
                        description,
                        medical_specialty,
                        sample_name,
                        transcription,
                        keywords
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        patient_id,
                        description,
                        medical_specialty,
                        sample_name,
                        transcription,
                        keywords,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            os.replace(staged_csv_path, CSV_FILE)
        finally:
            if os.path.exists(staged_csv_path):
                os.remove(staged_csv_path)

        if database_path not in DATASET_DATABASES.values():
            filename = os.path.basename(database_path)
            if filename.startswith("data_set") and filename.endswith(".db"):
                dataset_number = int(filename[len("data_set"):-len(".db")])
                dataset_name = f"Data {dataset_number}"
            else:
                dataset_name = "Healthcare"
            DATASET_DATABASES[dataset_name] = database_path
            refresh_database_selector()
        else:
            load_records()

        patient_id_entry.delete(0, "end")
        description_entry.delete(0, "end")
        specialty_entry.delete(0, "end")
        sample_name_entry.delete(0, "end")
        keywords_entry.delete(0, "end")
        transcription_text.delete("1.0", "end")

        messagebox.showinfo(
            "Success",
            "Record added successfully!"
        )

    except Exception as e:
        messagebox.showerror(
            "Error",
            str(e)
        )


def load_records():
    for item in tree.get_children():
        tree.delete(item)

    selected_database = database_filter.get()
    if selected_database == "All Databases":
        databases = DATASET_DATABASES.items()
    else:
        database_path = DATASET_DATABASES.get(selected_database)
        databases = (
            [(selected_database, database_path)]
            if database_path
            else []
        )

    for database_name, database_path in databases:
        conn = sqlite3.connect(database_path)
        try:
            rows = conn.execute("""
            SELECT *
            FROM healthcare_records
            ORDER BY medical_specialty
            """).fetchall()
        except sqlite3.Error as error:
            messagebox.showerror(
                "Database Error",
                f"Could not load {database_name}:\n{error}",
            )
            return
        finally:
            conn.close()

        for row in rows:
            tree.insert("", "end", values=(*row, database_name))


def fetch_specialty_data(database_path):
    conn = sqlite3.connect(database_path)
    try:
        return pd.read_sql_query(
            """
            SELECT
                medical_specialty,
                COUNT(patient_id) AS record_count
            FROM healthcare_records
            GROUP BY medical_specialty
            ORDER BY record_count DESC
            """,
            conn,
        )
    finally:
        conn.close()


def fetch_numeric_data(database_path):
    conn = sqlite3.connect(database_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT
                patient_id,
                description,
                medical_specialty,
                sample_name,
                keywords,
                transcription
            FROM healthcare_records
            """,
            conn,
        )
    finally:
        conn.close()

    if df.empty:
        return df

    df["description_length"] = df["description"].fillna("").astype(str).str.len()
    df["sample_name_length"] = df["sample_name"].fillna("").astype(str).str.len()
    df["keyword_count"] = df["keywords"].fillna("").astype(str).apply(
        lambda text: len([keyword for keyword in text.split(",") if keyword.strip()])
    )
    df["transcription_length"] = (
        df["transcription"].fillna("").astype(str).str.len()
    )
    return df


def search_records():
    keyword = search_entry.get().strip()

    for item in tree.get_children():
        tree.delete(item)

    query = """
    SELECT *
    FROM healthcare_records
    WHERE
        CAST(patient_id AS TEXT) LIKE ?
        OR description LIKE ?
        OR medical_specialty LIKE ?
        OR sample_name LIKE ?
        OR transcription LIKE ?
        OR keywords LIKE ?
    """

    value = f"%{keyword}%"

    for database_name, database_path in DATASET_DATABASES.items():
        conn = sqlite3.connect(database_path)
        try:
            rows = conn.execute(
                query,
                (value, value, value, value, value, value),
            ).fetchall()
        except sqlite3.Error as error:
            messagebox.showerror(
                "Database Error",
                f"Could not search {database_name}:\n{error}",
            )
            return
        finally:
            conn.close()

        for row in rows:
            tree.insert("", "end", values=(*row, database_name))


def check_numeric_data(raw_df, column):
    if (
        raw_df.empty
        or column not in raw_df.columns
        or raw_df[column].dropna().nunique() < 2
    ):
        raise ValueError(f"Not enough numeric data for this plot ({column}).")


def draw_selected_plot(spec_df, raw_df, plot_type):

    if plot_type == "Bar Plot":
        fig, ax = plt.subplots(
            figsize=(8, 6)
        )

        sns.barplot(
            x="medical_specialty",
            y="record_count",
            data=spec_df,
            palette="viridis",
            ax=ax
        )

        ax.set_title(
            "Records by Medical Specialty"
        )

        ax.set_xlabel(
            "Medical Specialty"
        )

        ax.set_ylabel(
            "Number of Records"
        )

    elif plot_type == "Line Plot":
        fig, ax = plt.subplots(
            figsize=(12, 6)
        )

        ax.plot(
            spec_df["medical_specialty"],
            spec_df["record_count"],
            marker="o",
            color="steelblue"
        )

        ax.set_title(
            "Records by Medical Specialty (Ranked by Count)"
        )

        ax.set_xlabel(
            "Medical Specialty"
        )

        ax.set_ylabel(
            "Number of Records"
        )

        ax.grid(
            True,
            alpha=0.3
        )

    elif plot_type == "Histogram":
        check_numeric_data(raw_df, "transcription_length")

        fig, ax = plt.subplots(
            figsize=(10, 6)
        )

        ax.hist(
            raw_df["transcription_length"],
            bins=30,
            color="steelblue",
            edgecolor="white"
        )

        ax.set_title(
            "Distribution of Transcription Lengths"
        )

        ax.set_xlabel(
            "Characters per Transcription"
        )

        ax.set_ylabel(
            "Number of Records"
        )

    elif plot_type == "Scatter Plot":
        check_numeric_data(raw_df, "keyword_count")
        check_numeric_data(raw_df, "transcription_length")

        fig, ax = plt.subplots(
            figsize=(10, 6)
        )

        sns.scatterplot(
            x="keyword_count",
            y="transcription_length",
            data=raw_df,
            alpha=0.5,
            ax=ax
        )

        ax.set_title(
            "Keyword Count vs Transcription Length"
        )

        ax.set_xlabel(
            "Number of Keywords"
        )

        ax.set_ylabel(
            "Transcription Length"
        )

    elif plot_type == "Box Plot":
        check_numeric_data(raw_df, "transcription_length")

        top_specialties = spec_df.head(8)["medical_specialty"].tolist()

        box_df = raw_df[raw_df["medical_specialty"].isin(top_specialties)]

        fig, ax = plt.subplots(
            figsize=(12, 6)
        )

        sns.boxplot(
            x="medical_specialty",
            y="transcription_length",
            data=box_df,
            palette="viridis",
            ax=ax
        )

        ax.set_title(
            "Transcription Length by Specialty (Top 8)"
        )

        ax.set_xlabel(
            "Medical Specialty"
        )

        ax.set_ylabel(
            "Transcription Length"
        )

    elif plot_type == "Pie Chart":
        fig, ax = plt.subplots(
            figsize=(12,8)
        )

        _, label_texts, percentage_texts = ax.pie(
            spec_df["record_count"],
            labels=spec_df["medical_specialty"],
            autopct="%1.1f%%"
        )

        for label in label_texts:
            label.set_fontsize(25)

        for percentage in percentage_texts:
            percentage.set_fontsize(25)

        ax.set_title(
            "Specialty Distribution" 
        )

    elif plot_type == "Heatmap":
        numeric = raw_df[NUMERIC_FEATURES].apply(
            pd.to_numeric,
            errors="coerce"
        )

        corr = numeric.corr().dropna(
            how="all"
        ).dropna(
            axis=1,
            how="all"
        )

        if corr.empty or corr.isna().all().all():
            raise ValueError(
                "Not enough numeric data for a correlation heatmap."
            )

        fig, ax = plt.subplots(
            figsize=(9, 7)
        )

        sns.heatmap(
            corr,
            annot=True,
            annot_kws={"size": 25},
            fmt=".2f",
            cmap="coolwarm",
            ax=ax
        )

        ax.set_title(
            "Correlation Between Numeric Features"
        )

    elif plot_type == "Count Plot":
        order = spec_df.head(12)["medical_specialty"].tolist()

        fig, ax = plt.subplots(
            figsize=(10, 8)
        )

        sns.countplot(
            y="medical_specialty",
            data=raw_df,
            order=order,
            palette="viridis",
            ax=ax
        )

        ax.set_title(
            "Number of Documents per Specialty (Top 12)"
        )

        ax.set_xlabel(
            "Number of Records"
        )

        ax.set_ylabel(
            "Medical Specialty"
        )

    elif plot_type == "Regression Plot":
        check_numeric_data(raw_df, "keyword_count")
        check_numeric_data(raw_df, "transcription_length")

        fig, ax = plt.subplots(
            figsize=(10, 6)
        )

        sns.regplot(
            x="keyword_count",
            y="transcription_length",
            data=raw_df,
            scatter_kws={"alpha": 0.4, "s": 20},
            line_kws={"color": "crimson"},
            ax=ax
        )

        ax.set_title(
            "Regression: Keyword Count vs Transcription Length"
        )

        ax.set_xlabel(
            "Number of Keywords"
        )

        ax.set_ylabel(
            "Transcription Length"
        )

    else:
        cumulative = spec_df["record_count"].cumsum()

        fig, ax = plt.subplots(
            figsize=(12, 6)
        )

        ax.fill_between(
            range(len(cumulative)),
            cumulative,
            alpha=0.35,
            color="steelblue"
        )

        ax.plot(
            range(len(cumulative)),
            cumulative,
            color="steelblue",
            marker="o",
            markersize=3
        )

        ax.set_xticks(range(len(spec_df)))

        ax.set_xticklabels(
            spec_df["medical_specialty"],
            ha="right",
        )

        ax.set_title(
            "Cumulative Records by Medical Specialty"
        )

        ax.set_xlabel(
            "Medical Specialty (Ranked by Count)"
        )

        ax.set_ylabel(
            "Cumulative Records"
        )
    ax.title.set_size(25)
    ax.xaxis.label.set_size(25)
    ax.yaxis.label.set_size(25)
    ax.tick_params(axis="both", labelsize=25)
    plt.tight_layout()
    return fig


def show_visualization():
    if not DATASET_DATABASES:
        messagebox.showinfo(
            "No Data",
            "No records to visualize. Import a dataset first.",
        )
        return

    plot_window = ctk.CTkToplevel(root)
    plot_window.title("Select Dataset and Plot")
    plot_window.geometry("360x280")
    plot_window.transient(root)
    plot_window.grab_set()

    ctk.CTkLabel(
        plot_window,
        text="Choose which database and plot to show:",
        font=("Arial", 15, "bold"),
    ).pack(pady=(20, 10))

    dataset_choice = ctk.StringVar(value=next(iter(DATASET_DATABASES)))
    plot_choice = ctk.StringVar(value=PLOT_TYPES[0])

    ctk.CTkComboBox(
        plot_window,
        values=list(DATASET_DATABASES),
        variable=dataset_choice,
        width=220,
    ).pack(pady=5)

    ctk.CTkComboBox(
        plot_window,
        values=PLOT_TYPES,
        variable=plot_choice,
        width=220,
    ).pack(pady=5)

    def plot_now():
        selected_dataset = dataset_choice.get()
        if selected_dataset not in DATASET_DATABASES:
            messagebox.showwarning(
                "Invalid Selection",
                f"Unknown dataset: {selected_dataset}",
            )
            return

        try:
            database_path = DATASET_DATABASES[selected_dataset]
            specialty_df = fetch_specialty_data(database_path)
            raw_df = fetch_numeric_data(database_path)
            if specialty_df.empty:
                messagebox.showinfo(
                    "No Data",
                    f"{selected_dataset} has no records to visualize.",
                )
                return

            fig = draw_selected_plot(
                specialty_df,
                raw_df,
                plot_choice.get(),
            )
            chart_window = ctk.CTkToplevel(root)
            chart_window.title(f"{selected_dataset} - {plot_choice.get()}")
            chart_window.geometry("1100x750")
            canvas = FigureCanvasTkAgg(fig, master=chart_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)

            def close_chart():
                plt.close(fig)
                chart_window.destroy()

            chart_window.protocol("WM_DELETE_WINDOW", close_chart)
            plot_window.destroy()
        except Exception as error:
            messagebox.showerror("Visualization Error", str(error))

    ctk.CTkButton(
        plot_window,
        text="Plot",
        command=plot_now,
        width=140,
        height=36,
    ).pack(pady=20)


def show_patient_detail(values):
    detail_window = ctk.CTkToplevel(root)

    detail_window.title(f"Patient Record - ID: {values[0]}")

    detail_window.geometry("900x750")

    detail_window.grab_set()

    detail_window.transient(root)
    detail_window.focus_force()

    main_frame = ctk.CTkScrollableFrame(detail_window)

    main_frame.pack(fill="both", expand=True, padx=20, pady=20)

    labels = [

        "Patient ID",

        "Description",

        "Medical Specialty",

        "Sample Name",

        "Transcription",

        "Keywords",

        "Database",

    ]

    for i, (label, value) in enumerate(zip(labels, values)):

        label_widget = ctk.CTkLabel(

            main_frame,

            text=f"{label}:",

            font=("Arial", 16, "bold"),

            anchor="w"

        )

        label_widget.pack(fill="x", pady=(12, 0))

        if label == "Transcription":

            text_widget = ctk.CTkTextbox(main_frame, height=300, width=760, font=("Arial", 15))

            text_widget.pack(fill="both", expand=True, pady=5)

            text_widget.insert("1.0", str(value))

            text_widget.configure(state="disabled")

        else:

            value_widget = ctk.CTkLabel(

                main_frame,

                text=str(value),

                font=("Arial", 15),

                anchor="w",

                wraplength=740,

                justify="left"

            )

            value_widget.pack(fill="x", pady=5)

    close_btn = ctk.CTkButton(

        main_frame,

        text="Close",

        command=detail_window.destroy,

        width=120,
        height=36,
        font=("Arial", 14, "bold")

    )

    close_btn.pack(pady=20)


def on_tree_row_click(event=None):
    if event is not None and hasattr(event, "widget"):
        try:
            row_id = tree.identify_row(event.y)
            if not row_id:
                return
            if row_id not in tree.selection():
                tree.selection_set(row_id)
                tree.focus(row_id)
        except Exception:
            pass

    selection = tree.selection()

    if not selection:

        return

    item = tree.item(selection[0])

    values = item["values"]

    if not values:

        return

    show_patient_detail(values)


def on_tree_double_click(event):

    on_tree_row_click(event)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()

root.geometry("1500x850")
root.title("Healthcare Analytics Dashboard")

title = ctk.CTkLabel(
    root,
    text="Healthcare Dataset Management System",
    font=("Arial", 26, "bold")
)

title.pack(
    pady=10
)

button_frame = ctk.CTkFrame(root)

button_frame.pack(
    fill="x",
    padx=10,
    pady=5
)
search_frame = ctk.CTkFrame(root)

search_frame.pack(
    fill="x",
    padx=10,
    pady=5
)

search_entry = ctk.CTkEntry(
    search_frame,
    placeholder_text="Search Patient ID, Description, Specialty, Sample Name, Transcription, Keywords",
    width=500
)

search_entry.pack(
    side="left",
    padx=10,
    pady=10
)

search_entry.bind("<Return>", lambda e: search_records())

search_btn = ctk.CTkButton(
    search_frame,
    text="Search",
    command=search_records,
    width=100
)

search_btn.pack(
    side="left",
    padx=5,
    pady=10
)

clear_btn = ctk.CTkButton(
    search_frame,
    text="Clear Search",
    command=lambda: (search_entry.delete(0, "end"), load_records()),
    width=100
)

clear_btn.pack(
    side="left",
    padx=5,
    pady=10
)

database_filter = ctk.StringVar(value="All Databases")
ctk.CTkLabel(
    search_frame,
    text="Browse database:",
).pack(
    side="left",
    padx=(15, 5),
    pady=10,
)

database_selector = ctk.CTkComboBox(
    search_frame,
    values=["All Databases"],
    variable=database_filter,
    command=lambda _choice: load_records(),
    width=180,
)
database_selector.pack(
    side="left",
    padx=5,
    pady=10,
)

import_btn = ctk.CTkButton(
    button_frame,
    text="Import CSV Dataset",
    command=browse_csv
)

import_btn.pack(
    side="left",
    padx=10
)

drop_hint = ctk.CTkLabel(
    button_frame,
    text="...or drag & drop a .csv file anywhere on this window",
    font=("Arial", 12, "italic")
)

drop_hint.pack(
    side="left",
    padx=10
)

load_btn = ctk.CTkButton(
    button_frame,
    text="Load Records",
    command=load_records
)

load_btn.pack(
    side="left",
    padx=10
)

visual_btn = ctk.CTkButton(
    button_frame,
    text="Visualize Data",
    command=show_visualization
)

visual_btn.pack(
    side="left",
    padx=10
)

entry_frame = ctk.CTkFrame(root)

entry_frame.pack(
    fill="x",
    padx=10,
    pady=10
)

patient_id_entry = ctk.CTkEntry(
    entry_frame,
    placeholder_text="Patient ID",
    width=120
)

patient_id_entry.grid(
    row=0,
    column=0,
    padx=5,
    pady=5
)

description_entry = ctk.CTkEntry(
    entry_frame,
    placeholder_text="Description",
    width=250
)

description_entry.grid(
    row=0,
    column=1,
    padx=5
)

specialty_entry = ctk.CTkEntry(
    entry_frame,
    placeholder_text="Medical Specialty",
    width=180
)

specialty_entry.grid(
    row=0,
    column=2,
    padx=5
)

sample_name_entry = ctk.CTkEntry(
    entry_frame,
    placeholder_text="Sample Name",
    width=180
)

sample_name_entry.grid(
    row=0,
    column=3,
    padx=5
)

keywords_entry = ctk.CTkEntry(
    entry_frame,
    placeholder_text="Keywords",
    width=180
)

keywords_entry.grid(
    row=0,
    column=4,
    padx=5
)

add_btn = ctk.CTkButton(
    entry_frame,
    text="Add Record",
    command=add_record
)

add_btn.grid(
    row=0,
    column=5,
    padx=10
)

transcription_label = ctk.CTkLabel(
    root,
    text="Transcription"
)

transcription_label.pack()

transcription_text = ctk.CTkTextbox(
    root,
    width=1300,
    height=120
)

transcription_text.pack(
    padx=10,
    pady=10
)

columns = (
    "Patient ID",
    "Description",
    "Medical Specialty",
    "Sample Name",
    "Transcription",
    "Keywords",
    "Database",
)

hint_label = ctk.CTkLabel(
    root,
    text="Tip: Click any patient row to enlarge / view the full record",
    font=("Arial", 13, "italic")
)

hint_label.pack(pady=(5, 0))

tree_frame = ctk.CTkFrame(root)
tree_frame.pack(
    fill="both",
    expand=True,
    padx=10,
    pady=10
)

tree_scroll = ttk.Scrollbar(
    tree_frame,
    orient="vertical"
)

tree = ttk.Treeview(
    tree_frame,
    columns=columns,
    show="headings",
    yscrollcommand=tree_scroll.set
)

tree_scroll.config(
    command=tree.yview
)

for col in columns:
    tree.heading(
        col,
        text=col
    )

    tree.column(
        col,
        width=130 if col == "Database" else 220,
        anchor="center"
    )

tree_scroll.pack(
    side="right",
    fill="y"
)

tree.pack(
    fill="both",
    expand=True
)

tree.bind("<ButtonRelease-1>", on_tree_row_click)
tree.bind("<Double-1>", on_tree_double_click)
tree.bind("<Return>", on_tree_row_click)

create_database()
refresh_database_selector()

if not enable_drag_and_drop(root, handle_dropped_files):
    print("Drag-and-drop is only supported on Windows.")

root.mainloop()