import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import csv
import os
import pygame # For music playback
from collections import defaultdict # For grouping logs

# Define the application data directory and log file path
APP_NAME = "WorkLoggerApp"
# Try to use My Documents, fall back to script directory if it fails for some reason
try:
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), 'Documents', APP_NAME)
except Exception:
    APP_DATA_DIR = os.path.dirname(os.path.abspath(__file__)) # Fallback to script's directory

if not os.path.exists(APP_DATA_DIR):
    try:
        os.makedirs(APP_DATA_DIR)
    except OSError as e:
        # If we can't create the directory in Documents, try to use the script's current directory
        print(f"Warning: Could not create directory {APP_DATA_DIR}. Error: {e}. Using script directory for logs.")
        APP_DATA_DIR = os.path.dirname(os.path.abspath(__file__)) # Fallback
        # Try to create a subfolder in the script directory if it's different from original APP_DATA_DIR
        if APP_NAME not in APP_DATA_DIR:
             fallback_subdir = os.path.join(APP_DATA_DIR, APP_NAME)
             if not os.path.exists(fallback_subdir):
                 try:
                     os.makedirs(fallback_subdir)
                     APP_DATA_DIR = fallback_subdir
                 except OSError as e_subdir:
                     print(f"Warning: Could not create fallback subdirectory {fallback_subdir}. Error: {e_subdir}. Using script directory root.")
                     # If all fails, just use the script's immediate directory, hoping it's writable.
                     # LOG_FILE will be defined just in this directory.

LOG_FILE = os.path.join(APP_DATA_DIR, 'work_logs.csv')
print(f"Log file will be saved to: {LOG_FILE}") # For debugging

class WorkLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Work Session Logger")
        self.root.geometry("800x750") # Increased window size

        self.is_session_active = False
        self.session_start_time = None
        self.timer_id = None
        self.is_pomodoro_session = False
        self.pomodoro_duration_seconds = 25 * 60
        self.selected_music_track = None

        # Initialize Pygame Mixer
        try:
            pygame.mixer.init()
        except pygame.error as e:
            messagebox.showerror("Mixer Error", f"Could not initialize audio mixer: {e}\nMusic playback will be disabled.")
            # Optionally disable music features if mixer fails

        # Style configuration - Larger fonts
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Arial", 12, "bold"))
        style.configure("Date.Treeview", font=("Arial", 11, "bold"), rowheight=28) 
        style.configure("Session.Treeview", font=("Arial", 10), rowheight=25)
        style.configure("TButton", font=("Arial", 11), padding=6)
        style.configure("TLabel", font=("Arial", 11), padding=5)
        style.configure("TLabelframe.Label", font=("Arial", 12, "bold"))
        style.configure("TCheckbutton", font=("Arial", 11), padding=5)

        # UI Elements
        self.main_frame = ttk.Frame(self.root, padding="15 15 15 15")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(self.main_frame, text="No session active.", font=("Arial", 14, "italic"))
        self.status_label.pack(pady=(10,15))

        self.timer_label = ttk.Label(self.main_frame, text="", font=("Arial", 13, "bold"))
        self.timer_label.pack(pady=(0,10))

        # Pomodoro Checkbox
        self.pomodoro_var = tk.BooleanVar()
        self.pomodoro_checkbox = ttk.Checkbutton(self.main_frame, text="Pomodoro Mode (25 min)", variable=self.pomodoro_var, style="TCheckbutton")
        self.pomodoro_checkbox.pack(pady=(0,10))

        # Music Controls Frame
        self.music_frame = ttk.LabelFrame(self.main_frame, text="Pomodoro Music", padding="15 15 15 15")
        self.music_frame.pack(fill=tk.X, pady=(10,10))

        self.select_music_button = ttk.Button(self.music_frame, text="Select Music Track", command=self.select_music_track)
        self.select_music_button.pack(side=tk.LEFT, padx=(0,10))

        self.selected_music_label = ttk.Label(self.music_frame, text="No track selected.", width=35, anchor=tk.W)
        self.selected_music_label.pack(side=tk.LEFT, padx=(0,10))

        self.volume_label = ttk.Label(self.music_frame, text="Volume:")
        self.volume_label.pack(side=tk.LEFT, padx=(10,0))

        self.volume_var = tk.DoubleVar(value=0.5) # Default volume 50%
        self.volume_scale = ttk.Scale(self.music_frame, from_=0, to=1, variable=self.volume_var, orient=tk.HORIZONTAL, command=self.set_volume)
        self.volume_scale.pack(side=tk.LEFT, padx=(5,10), fill=tk.X, expand=True)

        self.test_volume_button = ttk.Button(self.music_frame, text="Test", command=self.test_volume)
        self.test_volume_button.pack(side=tk.LEFT, padx=(10,0))

        self.toggle_button = ttk.Button(self.main_frame, text="Start Session", command=self.toggle_session)
        self.toggle_button.pack(pady=(20,20))

        # Log display - Modified for hierarchical view
        self.log_frame = ttk.LabelFrame(self.main_frame, text="Session Logs", padding="15 15 15 15")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Columns: Date/Session Info, Start Time, End Time, Duration
        self.log_tree = ttk.Treeview(self.log_frame, columns=("Info", "Start", "End", "Duration"), show="headings")
        self.log_tree.heading("Info", text="Date / Session Details")
        self.log_tree.heading("Start", text="Start Time")
        self.log_tree.heading("End", text="End Time")
        self.log_tree.heading("Duration", text="Duration")

        self.log_tree.column("Info", width=350, anchor=tk.W)
        self.log_tree.column("Start", width=120, anchor=tk.CENTER)
        self.log_tree.column("End", width=120, anchor=tk.CENTER)
        self.log_tree.column("Duration", width=120, anchor=tk.CENTER)

        self.log_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.load_logs()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window close

    def select_music_track(self):
        filepath = filedialog.askopenfilename(
            title="Select Music Track",
            filetypes=(("Audio Files", "*.mp3 *.wav *.ogg"), ("All files", "*.*"))
        )
        if filepath:
            self.selected_music_track = filepath
            track_name = os.path.basename(filepath)
            self.selected_music_label.config(text=track_name if len(track_name) < 33 else track_name[:30] + "...")
            try:
                pygame.mixer.music.load(self.selected_music_track)
                pygame.mixer.music.set_volume(self.volume_var.get())
            except pygame.error as e:
                messagebox.showerror("Music Error", f"Could not load music track: {e}")
                self.selected_music_track = None
                self.selected_music_label.config(text="No track selected.")

    def set_volume(self, value):
        # Value from scale is already 0.0 to 1.0
        if pygame.mixer.get_init(): # Check if mixer is initialized
            pygame.mixer.music.set_volume(float(value))

    def test_volume(self):
        if pygame.mixer.get_init() and self.selected_music_track:
            try:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                    self.test_volume_button.config(text="Test")
                else:
                    pygame.mixer.music.play(loops=0) # Play once
                    self.test_volume_button.config(text="Stop")
                    # After 5 seconds, stop the test and reset button if still playing (and was started by test)
                    self.root.after(5000, self.stop_test_sound_if_playing)
            except pygame.error as e:
                messagebox.showerror("Playback Error", f"Could not play test sound: {e}")
        elif not self.selected_music_track:
            messagebox.showinfo("No Music", "Please select a music track first.")

    def stop_test_sound_if_playing(self):
        # This function ensures that only a test play is stopped, not a continuous pomodoro play.
        # For now, it stops any sound and resets button. More sophisticated logic might be needed
        # if we want to distinguish between test play and actual pomodoro play for the 'Test' button.
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy() and self.test_volume_button.cget('text') == "Stop":
            pygame.mixer.music.stop()
            self.test_volume_button.config(text="Test") 

    def toggle_session(self):
        if not self.is_session_active:
            self.is_session_active = True
            self.session_start_time = datetime.datetime.now()
            
            if self.pomodoro_var.get():
                self.is_pomodoro_session = True
                self.status_label.config(text=f"Pomodoro started at: {self.session_start_time.strftime('%I:%M:%S %p')}")
                if self.selected_music_track and pygame.mixer.get_init():
                    try:
                        pygame.mixer.music.play(loops=-1) # Loop indefinitely
                        self.test_volume_button.config(state=tk.DISABLED) # Disable test button during pomodoro
                    except pygame.error as e:
                        messagebox.showerror("Music Playback Error", f"Could not play music: {e}")
            else:
                self.is_pomodoro_session = False
                self.status_label.config(text=f"Session started at: {self.session_start_time.strftime('%I:%M:%S %p')}")
            
            self.toggle_button.config(text="Stop Session")
            self.pomodoro_checkbox.config(state=tk.DISABLED)
            self.select_music_button.config(state=tk.DISABLED)
            self.volume_scale.config(state=tk.DISABLED)
            self.timer_label.config(text="Time: 00:00:00")
            self.update_timer()
        else:
            if self.timer_id:
                self.root.after_cancel(self.timer_id)
                self.timer_id = None
            
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()

            self.is_session_active = False
            session_end_time = datetime.datetime.now()
            
            if self.session_start_time:
                duration = session_end_time - self.session_start_time
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                duration_str = f"{hours:02}:{minutes:02}:{seconds:02}"
                date_str = self.session_start_time.strftime("%Y-%m-%d")
                start_time_str_24hr = self.session_start_time.strftime("%H:%M:%S")
                end_time_str_24hr = session_end_time.strftime("%H:%M:%S")
                self.save_log(date_str, start_time_str_24hr, end_time_str_24hr, duration_str)
                self.load_logs()
            
            self.status_label.config(text="No session active.")
            self.timer_label.config(text="")
            self.toggle_button.config(text="Start Session")
            self.pomodoro_checkbox.config(state=tk.NORMAL)
            self.select_music_button.config(state=tk.NORMAL)
            self.volume_scale.config(state=tk.NORMAL)
            self.test_volume_button.config(state=tk.NORMAL)
            self.test_volume_button.config(text="Test") # Reset test button text
            self.session_start_time = None
            if self.is_pomodoro_session:
                 self.is_pomodoro_session = False

    def update_timer(self):
        if self.is_session_active and self.session_start_time:
            elapsed_time = datetime.datetime.now() - self.session_start_time
            total_seconds_elapsed = int(elapsed_time.total_seconds())
            hours = total_seconds_elapsed // 3600
            minutes = (total_seconds_elapsed % 3600) // 60
            seconds = total_seconds_elapsed % 60
            time_str = f"Time: {hours:02}:{minutes:02}:{seconds:02}"
            self.timer_label.config(text=time_str)

            if self.is_pomodoro_session and total_seconds_elapsed >= self.pomodoro_duration_seconds:
                if pygame.mixer.get_init(): pygame.mixer.music.stop()
                messagebox.showinfo("Pomodoro Finished", "25-minute Pomodoro session complete!")
                self.toggle_session() 
            else:
                self.timer_id = self.root.after(1000, self.update_timer)
    
    def on_closing(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        self.root.destroy()

    def save_log(self, date, start_time_str, end_time_str, duration_str):
        file_exists = os.path.isfile(LOG_FILE)
        log_dir = os.path.dirname(LOG_FILE)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
                print(f"Created log directory at: {log_dir}") # For debugging
            except OSError as e:
                messagebox.showerror("Directory Error", f"Could not create directory for log file: {log_dir}\nDetails: {e}")
                return
        try:
            with open(LOG_FILE, 'a', newline='') as csvfile:
                fieldnames = ['Date', 'Start Time', 'End Time', 'Duration']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if not file_exists or os.path.getsize(LOG_FILE) == 0:
                    writer.writeheader()
                writer.writerow({'Date': date, 
                                 'Start Time': start_time_str, 
                                 'End Time': end_time_str, 
                                 'Duration': duration_str})
                print(f"Log saved to {LOG_FILE}")
        except IOError as e:
            messagebox.showerror("File Write Error", f"Could not write to log file: {LOG_FILE}\nDetails: {e}")
        except csv.Error as e:
            messagebox.showerror("CSV Error", f"Error writing CSV data to {LOG_FILE}\nDetails: {e}")
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"An unexpected error occurred while saving the log:\n{e}")

    def parse_duration(self, duration_str):
        """Helper to parse HH:MM:SS into total seconds."""
        parts = list(map(int, duration_str.split(':')))
        return parts[0] * 3600 + parts[1] * 60 + parts[2]

    def format_duration_seconds(self, total_seconds):
        """Helper to format total seconds into HH:MM:SS string."""
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def load_logs(self):
        for i in self.log_tree.get_children():
            self.log_tree.delete(i)

        logs_by_date = defaultdict(list)
        if not (os.path.isfile(LOG_FILE) and os.path.getsize(LOG_FILE) > 0):
            return # No file or empty file

        try:
            with open(LOG_FILE, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if all(key in row for key in ['Date', 'Start Time', 'End Time', 'Duration']):
                        logs_by_date[row['Date']].append(row)
                    else:
                        print(f"Skipping malformed row: {row}")
            
            # Sort dates for consistent display order (e.g., most recent first or oldest first)
            # Sorting by date string YYYY-MM-DD works directly.
            sorted_dates = sorted(logs_by_date.keys(), reverse=True) # Most recent dates first

            for date_str in sorted_dates:
                sessions_for_day = logs_by_date[date_str]
                total_day_seconds = 0
                for session in sessions_for_day:
                    try:
                        total_day_seconds += self.parse_duration(session['Duration'])
                    except ValueError: # Handle potential errors in duration format in CSV
                        print(f"Warning: Could not parse duration '{session['Duration']}' for date {date_str}")
                        continue # Skip this session's duration for total calculation
                
                formatted_total_duration = self.format_duration_seconds(total_day_seconds)
                session_count = len(sessions_for_day)

                # Insert date summary row (parent)
                date_info = f"{date_str} ({session_count} session{'s' if session_count != 1 else ''})"
                parent_id = self.log_tree.insert("", tk.END, 
                                                 values=(date_info, "", "", formatted_total_duration),
                                                 tags=('Date',))

                # Insert individual session rows (children)
                for i, session_row in enumerate(sessions_for_day):
                    try:
                        start_time_obj = datetime.datetime.strptime(session_row['Start Time'], '%H:%M:%S')
                        end_time_obj = datetime.datetime.strptime(session_row['End Time'], '%H:%M:%S')
                        start_time_display = start_time_obj.strftime('%I:%M:%S %p')
                        end_time_display = end_time_obj.strftime('%I:%M:%S %p')
                    except ValueError:
                        start_time_display = session_row['Start Time'] + " (Err)"
                        end_time_display = session_row['End Time'] + " (Err)"
                    
                    session_info = f"  └─ Session {i+1}" # Indent for child
                    self.log_tree.insert(parent_id, tk.END, 
                                         values=(session_info, start_time_display, end_time_display, session_row['Duration']),
                                         tags=('Session',))
                                         
        except IOError:
            messagebox.showerror("Error", f"Could not read log file: {LOG_FILE}")
        except csv.Error as e:
             messagebox.showerror("CSV Error", f"Error reading CSV file: {e}")
        except Exception as e:
            messagebox.showerror("Load Error", f"An unexpected error occurred while loading logs: {e}")
            import traceback
            traceback.print_exc() # For more detailed debugging in console

if __name__ == "__main__":
    app_root = tk.Tk()
    app = WorkLoggerApp(app_root)
    app_root.mainloop() 