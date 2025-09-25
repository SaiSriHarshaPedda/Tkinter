import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.colorchooser import askcolor
import serial
import serial.tools.list_ports
import threading
import json
import os


class ProcessVisualizationSettings:
    def __init__(self, root):
        self.root = root
        root.title("Process Visualization Settings")

        self.ANIMATION_MAP = {"Progress": 0, "Two Color Fade": 1, "Fade": 2, "Loading": 3}
        self.DIRECTION_MAP = {"Left": 1, "Right": -1}
        self.STATE_MAP = ["State-1", "State-2", "State-3", "State-4"]
        self.inputs = ["Output 1", "Output 2", "Output 3", "Output 4"]
        self.animations_default = ["Progress", "Two Color Fade", "Fade", "Loading"]
        self.states_default = ["State-1", "State-2", "State-3", "State-4"]
        self.directions_default = ["Left", "Left", "Left", "Left"]
        self.bg_color = "#FFFFFF"
        self.serial_connection = None
        self.reading_serial = False

        self.color1_values = [None] * 4
        self.color2_values = [None] * 4
        self.color1_btns = []
        self.color2_btns = []
        self.color1_entries = []
        self.color2_entries = []
        self.animation_cbs = []
        self.state_cbs = []
        self.num_leds_entries = []
        self.intensity1_cbs = []
        self.direction_cbs = []
        self.bg_color_enabled_vars = []
        self.speed_scales = []
        self.effect_scales = []  # New list for Effect %
        self.selected_port = tk.StringVar()
        self.available_ports = []
        self.machine_name_var = tk.StringVar(value="")
        self.baud_rate_var = tk.StringVar(value="115200")

        # Config file dropdown
        self.config_dropdown_var = tk.StringVar(value="")
        self.config_dropdown = None

        self._create_widgets()
        self._initial_toggle_all()
        self.refresh_ports()
        self.update_config_dropdown()

        for col in range(3, 8):
            self.root.grid_columnconfigure(col, minsize=80)

    def _create_widgets(self):
        self._create_presets_section()
        self._create_headers()
        for i in range(4):
            self._create_row(i)
        self._create_bg_color_button()
        self._create_output_textbox()
        self._create_read_write_buttons()
        self._create_settings_tab_button()
        self._create_settings_window()
        self._create_config_management_buttons()

    def _create_presets_section(self):
        frame = ttk.Frame(self.root)
        frame.grid(row=0, column=0, columnspan=3, pady=10, sticky='w')
        ttk.Label(frame, text="Presets:").grid(row=0, column=0, padx=10)

    def _create_config_management_buttons(self):
        ttk.Label(self.root, text="").grid(row=0, column=2, padx=60)
        self.config_dropdown = ttk.Combobox(self.root, textvariable=self.config_dropdown_var, state="readonly", width=25)
        self.config_dropdown.grid(row=0, column=2, padx=5)
        ttk.Button(self.root, text="Load", command=self.load_config).grid(row=0, column=3, padx=0)
        ttk.Button(self.root, text="Save As", command=self.save_config_as).grid(row=0, column=4, padx=0,sticky='w')
        ttk.Button(self.root, text="Overwrite", command=self.overwrite_config).grid(row=0, column=5, padx=0,sticky='w')

    def _create_headers(self):
        headers = [
            "Output", "Animation", "States", "No of LEDs", "Intensity (1-255)",
            "Color 1", "  Hex", "Color 2", "  Hex",
            "BG Color", "Speed (1-10)", "Direction", "Effect %", "Preview"
        ]
        for col, text in enumerate(headers):
            ttk.Label(self.root, text=text, font=("Arial", 15, "bold")).grid(row=1, column=col, padx=5, pady=2)

    def _choose_color(self, idx, which):
        color = askcolor()[1]
        if color:
            if which == 1:
                self.color1_btns[idx].config(bg=color)
                self.color1_values[idx] = color
                self.color1_entries[idx].delete(0, tk.END)
                self.color1_entries[idx].insert(0, color)
            else:
                self.color2_btns[idx].config(bg=color)
                self.color2_values[idx] = color
                self.color2_entries[idx].delete(0, tk.END)
                self.color2_entries[idx].insert(0, color)
            self._update_preview(idx)

    def _validate_leds_entry(self, P):
        if P.isdigit() and 1 <= int(P) <= 99:
            return True
        elif P == "":
            return True
        else:
            return False

    def _create_row(self, row):
        ttk.Label(self.root, text=self.inputs[row]).grid(row=row + 2, column=0)

        anim_cb = ttk.Combobox(self.root, values=list(self.ANIMATION_MAP.keys()), state="readonly")
        anim_cb.set(self.animations_default[row])
        anim_cb.grid(row=row + 2, column=1)
        anim_cb.bind("<<ComboboxSelected>>", lambda e, r=row: self.toggle_controls(r))
        self.animation_cbs.append(anim_cb)

        state_cb = ttk.Combobox(self.root, values=self.STATE_MAP, state="readonly")
        state_cb.set(self.states_default[row])
        state_cb.grid(row=row + 2, column=2)
        self.state_cbs.append(state_cb)

        vcmd = (self.root.register(self._validate_leds_entry), '%P')
        num_leds_entry = ttk.Entry(self.root, validate='key', validatecommand=vcmd, width=6)
        num_leds_entry.insert(0, "55")
        num_leds_entry.grid(row=row + 2, column=3)
        self.num_leds_entries.append(num_leds_entry)

        intensity_scale = tk.Scale(self.root, from_=1, to=255, orient='horizontal', length=120)
        intensity_scale.set(128)
        intensity_scale.grid(row=row + 2, column=4)
        self.intensity1_cbs.append(intensity_scale)

        # Color 1 button
        c1_btn = tk.Button(self.root, text="Select", bg="white", width=10,
                           command=lambda idx=row: self._choose_color(idx, 1))
        c1_btn.grid(row=row + 2, column=5)
        self.color1_btns.append(c1_btn)
        self.color1_values[row] = None

        # Color 1 hex entry
        color1_entry = ttk.Entry(self.root, width=9)
        color1_entry.grid(row=row + 2, column=6, padx=10, sticky='e')
        color1_entry.bind("<Return>", lambda e, idx=row: self._set_color_from_entry(idx, 1))
        color1_entry.bind("<FocusOut>", lambda e, idx=row: self._set_color_from_entry(idx, 1))
        self.color1_entries.append(color1_entry)

        # Color 2 button
        c2_btn = tk.Button(self.root, text="Select", bg="white", width=10,
                           command=lambda idx=row: self._choose_color(idx, 2))
        c2_btn.grid(row=row + 2, column=7)
        self.color2_btns.append(c2_btn)
        self.color2_values[row] = None

        # Color 2 hex entry
        color2_entry = ttk.Entry(self.root, width=9)
        color2_entry.grid(row=row + 2, column=8, sticky='e')
        color2_entry.bind("<Return>", lambda e, idx=row: self._set_color_from_entry(idx, 2))
        color2_entry.bind("<FocusOut>", lambda e, idx=row: self._set_color_from_entry(idx, 2))
        self.color2_entries.append(color2_entry)

        bg_enabled_var = tk.BooleanVar(value=False)
        bg_enabled_chk = ttk.Checkbutton(self.root, variable=bg_enabled_var,
                                         command=lambda r=row: self._update_preview(r))
        bg_enabled_chk.grid(row=row + 2, column=9)
        self.bg_color_enabled_vars.append(bg_enabled_var)

        speed_scale = tk.Scale(self.root, from_=1, to=10, orient='horizontal', length=80)
        speed_scale.set(5)
        speed_scale.grid(row=row + 2, column=10)
        self.speed_scales.append(speed_scale)

        direction_cb = ttk.Combobox(self.root, values=list(self.DIRECTION_MAP.keys()), state="readonly")
        direction_cb.set(self.directions_default[row])
        direction_cb.grid(row=row + 2, column=11)
        self.direction_cbs.append(direction_cb)

        # New Effect % scale from 1 to 100
        effect_scale = tk.Scale(self.root, from_=1, to=100, orient='horizontal', length=80)
        effect_scale.set(50)  # default 50%
        effect_scale.grid(row=row + 2, column=12)
        self.effect_scales.append(effect_scale)

        preview_lbl = tk.Label(self.root, text="", width=40, anchor="w")
        preview_lbl.grid(row=row + 2, column=13, padx=5, pady=5)
        self._update_preview(row)

    def _set_color_from_entry(self, idx, which):
        entry = self.color1_entries[idx] if which == 1 else self.color2_entries[idx]
        val = entry.get()
        if val.startswith("#") and len(val) == 7:
            btn = self.color1_btns[idx] if which == 1 else self.color2_btns[idx]
            btn.config(bg=val)
            if which == 1:
                self.color1_values[idx] = val
            else:
                self.color2_values[idx] = val
            self._update_preview(idx)

    def _update_preview(self, idx):
        anim_num = self.ANIMATION_MAP[self.animation_cbs[idx].get()]
        state_val = self.state_cbs[idx].get()
        leds_val = self.num_leds_entries[idx].get()
        c1 = self.color1_values[idx] if self.color1_values[idx] else "None"
        c2 = self.color2_values[idx] if self.color2_values[idx] else "None"
        intensity_num = self.intensity1_cbs[idx].get()
        speed_val = self.speed_scales[idx].get()
        direction_val = self.direction_cbs[idx].get()
        effect_val = self.effect_scales[idx].get()

        preview_text = (f"Color1={c1}, Color2={c2}")
        if self.bg_color_enabled_vars[idx].get():
            preview_text += f", bg_color={self.bg_color}"
        preview_text += f", Effect%={effect_val}"

        preview_lbls = [w for w in self.root.grid_slaves(row=idx + 2, column=13) if isinstance(w, tk.Label)]
        if preview_lbls:
            preview_lbls[0].config(text=preview_text)

    def toggle_controls(self, row):
        anim_value = self.animation_cbs[row].get()
        if anim_value == "Fade":
            self.direction_cbs[row].config(state="readonly")
        else:
            self.direction_cbs[row].config(state="disabled")
        self._update_preview(row)

    def _initial_toggle_all(self):
        for row in range(4):
            self.toggle_controls(row)

    def _create_bg_color_button(self):
        self.bg_color_btn = tk.Button(self.root, text="BG Color", bg=self.bg_color, width=7,
                                      command=self.choose_bg_color)
        self.bg_color_btn.grid(row=0, column=7, padx=10, pady=10, sticky="w")

    def choose_bg_color(self):
        color = askcolor(initialcolor=self.bg_color)[1]
        if color:
            self.bg_color = color
            self.bg_color_btn.config(bg=color)
            for i in range(4):
                if self.bg_color_enabled_vars[i].get():
                    self._update_preview(i)

    def _create_settings_tab_button(self):
        self.settings_btn = ttk.Button(self.root, text="Serial Settings", command=self._open_settings_window)
        self.settings_btn.grid(row=0, column=1, sticky="w")

    def _create_settings_window(self):
        self.settings_window = None

    def _open_settings_window(self):
        if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
            self.settings_window.focus()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")

        ttk.Label(self.settings_window, text="Machine Name:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.machine_name_entry = ttk.Entry(self.settings_window, textvariable=self.machine_name_var, width=30)
        self.machine_name_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(self.settings_window, text="Serial Port:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.settings_port_menu = ttk.Combobox(self.settings_window, textvariable=self.selected_port, width=30, state="readonly")
        self.settings_port_menu.grid(row=1, column=1, padx=10, pady=10)

        ttk.Label(self.settings_window, text="Baud Rate:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.settings_baud_rate_entry = ttk.Entry(self.settings_window, textvariable=self.baud_rate_var, width=30)
        self.settings_baud_rate_entry.grid(row=2, column=1, padx=10, pady=10)

        btn_frame = ttk.Frame(self.settings_window)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Connect", command=self.connect_serial).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Disconnect", command=self.disconnect_serial).pack(side=tk.LEFT, padx=5)

        self.refresh_ports()

    def refresh_ports(self):
        ports = list(serial.tools.list_ports.comports())
        names = []
        for p in ports:
            name = f"{p.device} - {p.description}"
            names.append(name)
        self.available_ports = names
        if hasattr(self, 'port_menu') and self.port_menu:
            self.port_menu["values"] = names
        if hasattr(self, 'settings_port_menu') and self.settings_port_menu:
            self.settings_port_menu["values"] = names
        if names:
            self.selected_port.set(names[0])
        else:
            self.selected_port.set("")

    def disconnect_serial(self):
        if self.serial_connection:
            self.reading_serial = False
            try:
                self.serial_connection.close()
                self.output_text.insert(tk.END, "Serial connection closed.\n")
            except Exception as e:
                self.output_text.insert(tk.END, f"Error closing serial connection: {e}\n")
            self.serial_connection = None

    def connect_serial(self):
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, "Connecting...\n")
        self.root.update_idletasks()
        port_str = self.selected_port.get()
        port_device = ""
        if port_str and "-" in port_str:
            port_device = port_str.split(" - ")[0].strip()
        else:
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                desc = p.description.lower() if p.description else ""
                device = p.device.lower() if p.device else ""
                if ("arduino" in desc or "ch340" in desc or "usbserial" in desc or "usb-serial" in desc
                        or "acm" in device or "rp2040" in desc or "raspberry" in desc):
                    port_device = p.device
                    break
        if not port_device:
            self.output_text.insert(tk.END, "Error: Serial port not found. Try manual selection or refresh.\n")
            return
        try:
            baud_rate = int(self.baud_rate_var.get())
        except ValueError:
            baud_rate = 115200

        self.output_text.insert(tk.END, f"Trying to connect to {port_device} at {baud_rate} baud\n")
        try:
            self.serial_connection = serial.Serial(port_device, baud_rate, timeout=1)
            self.output_text.insert(tk.END, f"Serial connected on {port_device}\n")
            self.reading_serial = True
            self.read_serial_data()
        except Exception as e:
            self.output_text.insert(tk.END, f"Failed to connect: {str(e)}\n")

    def read_serial_data(self):
        if self.reading_serial and self.serial_connection:
            try:
                while self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.readline().decode('utf-8', errors='replace').strip()
                    if data:
                        self.output_text.insert(tk.END, f"Received: {data}\n")
                        self.output_text.see(tk.END)
            except Exception as e:
                self.output_text.insert(tk.END, f"Serial read error: {str(e)}\n")
        self.root.after(100, self.read_serial_data)

    def _create_read_write_buttons(self):
        ttk.Button(self.root, text="Read", command=self.read_serial_data).grid(row=6, column=6, pady=10)
        ttk.Button(self.root, text="Write", command=self.on_write).grid(row=6, column=4, pady=10)
        ttk.Button(self.root, text="RESET", command=self.unload_config).grid(row=0, column=6, pady=10)

    def _create_output_textbox(self):
        self.output_text = tk.Text(self.root, width=170, height=5)
        self.output_text.grid(row=7, column=0, columnspan=13, padx=10, pady=10)

    def on_write(self):
        parts = []
        # Compose the existing main output string with effect percentage included if needed
        for i in range(4):
            output_num = i
            anim_num = self.ANIMATION_MAP[self.animation_cbs[i].get()]
            state_val = self.state_cbs[i].get()
            leds_val = self.num_leds_entries[i].get()
            c1 = self.color1_values[i][1:] if self.color1_values[i] else "000000"
            c2 = self.color2_values[i][1:] if self.color2_values[i] else "000000"
            speed_val = self.speed_scales[i].get()
            direction_str = self.direction_cbs[i].get() if self.direction_cbs[i]['state'] != 'disabled' else "Left"
            direction_num = self.DIRECTION_MAP.get(direction_str, 1)
            intensity_num = self.intensity1_cbs[i].get()
            effect_percent = self.effect_scales[i].get()

            segment = f"{output_num},{anim_num},{intensity_num},{c1},{c2},{speed_val},{direction_num}"
            parts.append(segment)

        output_string = "$" + "#".join(parts) + "$"

        # Additional serial writes formatted as requested (examples; customize the values as per your need)
        example_led_number = ""
        example_effect_percentage = ""
        example_state = ""

        # Generate example command strings for all four channels (you can modify per your app logic)
        led_number_cmds = []
        effect_percentage_cmds = []
        state_cmds = []
        for i in range(4):
            led_number_cmds.append(f"${i},LED,{self.num_leds_entries[i].get()}$")                  # LED number example: number=123
            effect_percentage_cmds.append(f"${i},EFFECT,{self.effect_scales[i].get()}$")  # Using actual effect value
            state_cmds.append(f"${i},{self.state_cbs[i].get()}$")     # Using current state string

        example_led_number = "\n".join(led_number_cmds)
        example_effect_percentage = "\n".join(effect_percentage_cmds)
        example_state = "\n".join(state_cmds)

        # Show all in output textbox
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END,output_string + "\n\n")
        self.output_text.insert(tk.END,example_led_number + "\n\n")
        self.output_text.insert(tk.END,example_effect_percentage + "\n\n")
        self.output_text.insert(tk.END,example_state + "\n")

        

        def serial_writer():
            try:
                if self.serial_connection and self.serial_connection.is_open:
                    self.serial_connection.write((output_string + "\n").encode('utf-8'))
                    self.serial_connection.flush()
                    self.root.after(0, lambda: self.output_text.insert(tk.END, "\nData sent to serial port.\n"))
                else:
                    self.root.after(0, lambda: self.output_text.insert(tk.END, "\nSerial connection not open.\n"))
            except Exception as e:
                self.root.after(0, lambda: self.output_text.insert(tk.END,
                                                                 f"\nError writing to serial port: {e}\n"))
        threading.Thread(target=serial_writer, daemon=True).start()

    # New serial write commands

    def write_led_number(self, channel_no, led, number):
        cmd = f"${channel_no},{led},{number}$"
        self._send_serial_command(cmd)

    def write_effect_percentage(self, channel_no, effect, percentage):
        cmd = f"${channel_no},{effect},{percentage}$"
        self._send_serial_command(cmd)

    def write_state(self, channel_no, state):
        cmd = f"${channel_no},{state}$"
        self._send_serial_command(cmd)

    def _send_serial_command(self, command):
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.write((command + "\n").encode('utf-8'))
                self.serial_connection.flush()
                self.output_text.insert(tk.END, f"\nSent command: {command}\n")
            else:
                self.output_text.insert(tk.END, "\nSerial connection not open.\n")
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError writing to serial port: {e}\n")

    # Unload button functionality
    def unload_config(self):
        for i in range(4):
            self.animation_cbs[i].set(self.animations_default[i])
            self.state_cbs[i].set(self.states_default[i])
            self.num_leds_entries[i].delete(0, tk.END)
            self.num_leds_entries[i].insert(0, "1")
            self.intensity1_cbs[i].set(128)
            self.color1_values[i] = None
            self.color2_values[i] = None
            self.color1_entries[i].delete(0, tk.END)  # Clear color1 hex entry
            self.color2_entries[i].delete(0, tk.END)
            self.color1_btns[i].config(bg='white')
            self.color2_btns[i].config(bg='white')
            self.speed_scales[i].set(5)
            self.direction_cbs[i].set(self.directions_default[i])
            self.effect_scales[i].set(50)
            self.bg_color_enabled_vars[i].set(False)
            self._update_preview(i)
        self.output_text.insert(tk.END, "Configuration unloaded and reset.\n")

    # ---- CONFIG MANAGEMENT ----
    def get_config_folder(self):
        folder = "configs"
        os.makedirs(folder, exist_ok=True)
        return folder

    def get_all_json_configs(self):
        folder = self.get_config_folder()
        return [f for f in os.listdir(folder) if f.endswith(".json")]

    def update_config_dropdown(self):
        configs = self.get_all_json_configs()
        self.config_dropdown['values'] = configs
        if configs:
            self.config_dropdown_var.set(configs[0])

    def save_config_as(self):
        folder = self.get_config_folder()
        file_path = filedialog.asksaveasfilename(initialdir=folder, defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            self.save_config_to_path(file_path)
            self.update_config_dropdown()

    def overwrite_config(self):
        folder = self.get_config_folder()
        filename = self.config_dropdown_var.get()
        if not filename:
            messagebox.showerror("Overwrite Error", "No config selected.")
            return
        file_path = os.path.join(folder, filename)
        self.save_config_to_path(file_path)
        messagebox.showinfo("Overwrite", f"Configuration overwritten: {filename}")

    def save_config_to_path(self, path):
        config = {
            "machine_name": self.machine_name_var.get(),
            "serial_port": self.selected_port.get(),
            "baud_rate": self.baud_rate_var.get(),
            "outputs": []
        }
        for i in range(4):
            output = {
                "animation": self.animation_cbs[i].get(),
                "state": self.state_cbs[i].get(),
                "num_leds": self.num_leds_entries[i].get(),
                "intensity": self.intensity1_cbs[i].get(),
                "color1": self.color1_values[i],
                "color2": self.color2_values[i],
                "bg_color_enabled": self.bg_color_enabled_vars[i].get(),
                "speed": self.speed_scales[i].get(),
                "direction": self.direction_cbs[i].get(),
                "effect_percent": self.effect_scales[i].get()  # Save new column value
            }
            config["outputs"].append(output)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def load_config(self):
        folder = self.get_config_folder()
        filename = self.config_dropdown_var.get()
        if not filename:
            messagebox.showerror("Load Error", "No config selected.")
            return
        file_path = os.path.join(folder, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.machine_name_var.set(config.get("machine_name", ""))
        self.selected_port.set(config.get("serial_port", ""))
        self.baud_rate_var.set(config.get("baud_rate", "115200"))
        outputs = config.get("outputs", [])
        for i, output in enumerate(outputs):
            self.animation_cbs[i].set(output.get("animation", "Progress"))
            self.state_cbs[i].set(output.get("state", "State-1"))
            self.num_leds_entries[i].delete(0, tk.END)
            self.num_leds_entries[i].insert(0, output.get("num_leds", "1"))
            self.intensity1_cbs[i].set(output.get("intensity", 128))
            color1 = output.get("color1", "#ffffff") or "000000"
            color2 = output.get("color2", "#ffffff") or "000000"
            self.color1_values[i] = color1
            self.color2_values[i] = color2
            self.color1_btns[i].config(bg=color1)
            self.color2_btns[i].config(bg=color2)
            self.color1_entries[i].delete(0, tk.END)
            self.color1_entries[i].insert(0, color1)
            self.color2_entries[i].delete(0, tk.END)
            self.color2_entries[i].insert(0, color2)
            self.bg_color_enabled_vars[i].set(output.get("bg_color_enabled", False))
            self.speed_scales[i].set(output.get("speed", 5))
            self.direction_cbs[i].set(output.get("direction", "Left"))
            self.effect_scales[i].set(output.get("effect_percent", 50))
            self._update_preview(i)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1750x470")
    app = ProcessVisualizationSettings(root)
    root.mainloop()
