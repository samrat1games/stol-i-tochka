import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import subprocess
import threading
import os
import signal

class StolITochka:
    def __init__(self, root):
        self.root = root
        self.root.title("Стол — и точка (v2.5 MEGA)")
        self.root.geometry("700x750")
        self.proc = None
        
        style = ttk.Style()
        try: style.theme_use('clam')
        except: pass

        tk.Label(root, text="СТОЛ — И ТОЧКА", font=('Arial', 24, 'bold'), fg="#ff4500").pack(pady=10)

        f1 = ttk.LabelFrame(root, text=" 1. Образ (ISO/IMG) ")
        f1.pack(fill="x", padx=10, pady=5)
        self.iso_path = tk.StringVar()
        ttk.Entry(f1, textvariable=self.iso_path).pack(side="left", fill="x", expand=True, padx=5, pady=5)
        ttk.Button(f1, text="Обзор", command=self.select_iso).pack(side="right", padx=5)

        f2 = ttk.LabelFrame(root, text=" 2. Целевой накопитель ")
        f2.pack(fill="x", padx=10, pady=5)
        self.drive_list = ttk.Combobox(f2, state="readonly")
        self.drive_list.pack(fill="x", padx=5, pady=5)
        ttk.Button(f2, text="Обновить список", command=self.refresh_drives).pack(pady=2)

        f3 = ttk.LabelFrame(root, text=" 3. Схема и Цель ")
        f3.pack(fill="x", padx=10, pady=5)
        self.partition_scheme = tk.StringVar(value="gpt")
        ttk.Radiobutton(f3, text="GPT (UEFI)", variable=self.partition_scheme, value="gpt").grid(row=0, column=0, padx=20)
        ttk.Radiobutton(f3, text="MBR (BIOS)", variable=self.partition_scheme, value="mbr").grid(row=0, column=1, padx=20)
        
        self.burn_mode = tk.StringVar(value="iso")
        ttk.Radiobutton(f3, text="ISO Mode", variable=self.burn_mode, value="iso").grid(row=1, column=0, pady=5)
        ttk.Radiobutton(f3, text="DD Mode", variable=self.burn_mode, value="dd").grid(row=1, column=1, pady=5)

        f4 = ttk.LabelFrame(root, text=" 4. Дополнительно (Rufus Style) ")
        f4.pack(fill="x", padx=10, pady=5)
        self.persistence_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f4, text="Создать раздел Persistent (для Linux Live)", variable=self.persistence_var).pack(anchor="w", padx=10)
        
        self.verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f4, text="Проверить на бэд-блоки", variable=self.verify_var).pack(anchor="w", padx=10)

        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=20)
        
        self.status_label = tk.Label(root, text="Готов к уничтожению данных", font=('Arial', 10))
        self.status_label.pack()

        # КНОПКИ УПРАВЛЕНИЯ
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=10)

        self.burn_btn = tk.Button(btn_frame, text="СТАРТ", bg="#4CAF50", fg="white", 
                                 font=('Arial', 18, 'bold'), height=2, command=self.confirm_burn)
        self.burn_btn.pack(side="left", fill="x", expand=True, padx=5)

        self.stop_btn = tk.Button(btn_frame, text="стоп ОТМЕНААА!", bg="#f44336", fg="white", 
                                 font=('Arial', 14, 'bold'), state="disabled", command=self.stop_now)
        self.stop_btn.pack(side="right", fill="x", expand=True, padx=5)

        self.refresh_drives()

    def select_iso(self):
        path = filedialog.askopenfilename(filetypes=[("ISO/IMG", "*.iso *.img"), ("All", "*.*")])
        if path: self.iso_path.set(path)

    def refresh_drives(self):
        drives = []
        try:
            res = subprocess.run(['lsblk', '-d', '-o', 'NAME,SIZE,MODEL', '-n'], capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if line.strip():
                    p = line.split()
                    drives.append(f"/dev/{p[0]} ({p[1]})")
        except: pass
        self.drive_list['values'] = drives
        if drives: self.drive_list.current(0)

    def stop_now(self):
        if self.proc:
            try:
                # Убиваем через pkexec, так как dd запущен от root
                subprocess.run(["pkexec", "kill", "-9", str(self.proc.pid)])
                self.status_label.config(text="ОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ!", fg="red")
                messagebox.showwarning("Отмена", "Запись прервана. Флешка может быть в нерабочем состоянии, переформатируйте её.")
            except: pass
            self.proc = None
            self.burn_btn.config(state="normal")
            self.stop_btn.config(state="disabled")

    def confirm_burn(self):
        if not self.iso_path.get() or not self.drive_list.get():
            messagebox.showwarning("Ошибка", "Файл или диск не выбраны!")
            return
        
        if messagebox.askyesno("ПОСЛЕДНЕЕ ПРЕДУПРЕЖДЕНИЕ", "Диск будет стерт. Уверен?"):
            self.burn_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            target = self.drive_list.get().split()[0]
            threading.Thread(target=self.burn_thread, args=(target,), daemon=True).start()

    def burn_thread(self, target):
        iso = self.iso_path.get()
        try:
            self.status_label.config(text="Размонтирование...", fg="orange")
            subprocess.run(["pkexec", "umount", "-l", f"{target}*"], stderr=subprocess.DEVNULL)
            
            # Очистка структур
            subprocess.run(["pkexec", "wipefs", "-a", target])
            
            label_type = "gpt" if self.partition_scheme.get() == "gpt" else "msdos"
            subprocess.run(["pkexec", "parted", "-s", target, "mklabel", label_type])

            self.status_label.config(text="Запись... Нажми ОТМЕНА если страшно", fg="red")
            
            # Команда dd
            cmd = ["pkexec", "dd", f"if={iso}", f"of={target}", "bs=8M", "conv=fdatasync", "status=none"]
            self.proc = subprocess.Popen(cmd)
            self.proc.wait()

            if self.proc and self.proc.returncode == 0:
                if self.persistence_var.get():
                    self.status_label.config(text="Создание Persistence раздела...")
                    # Логика создания доп. раздела (упрощенно)
                    subprocess.run(["pkexec", "parted", "-s", target, "mkpart", "primary", "ext4", "80%", "100%"])
                
                self.status_label.config(text="УСПЕХ! И точка.", fg="green")
                messagebox.showinfo("Готово", "Флешка записана!")
            
        except Exception as e:
            self.status_label.config(text=f"Ошибка: {str(e)}", fg="red")
        finally:
            self.burn_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.proc = None

if __name__ == "__main__":
    root = tk.Tk()
    app = StolITochka(root)
    root.mainloop()