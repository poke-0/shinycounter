import sys
import os
import glob
import yaml
import json
import csv
import requests
import time
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QWidget, QDialog, QScrollArea,
    QGridLayout, QInputDialog, QTabWidget, QMenuBar, QMenu, QAction,
    QLineEdit, QComboBox, QFrame, QProgressBar, QCompleter, QMessageBox,
    QSlider
)
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence
from PyQt5.QtCore import Qt, QEvent, QTimer
from pynput import keyboard
from pygame import mixer
from io import BytesIO


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS2
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# Application Constants
APP_NAME = "ShinyCounter"
WINDOW_SIZE = (200, 270)
MINIMUM_WINDOW_SIZE = (200, 270)
MAXIMUM_WINDOW_SIZE = (350, 345)
WINDOW_POSITION = (1200, -460)

# Double Hunting Window Sizes
DOUBLE_WINDOW_SIZE = (300, 270)
DOUBLE_MINIMUM_WINDOW_SIZE = (300, 270)
DOUBLE_MAXIMUM_WINDOW_SIZE = (700, 345)
DOUBLE_WINDOW_POSITION = (1200, -460)  # Adjusted for wider window

HOTKEY_ADD = keyboard.Key.ctrl_r

# Directory Paths
CONFIG_DIR = "config/"
ICONS_DIR = "icons/"
SOUNDS_DIR = "sounds/"
BACKUPS_DIR = "backups/"  # If you plan to add backup functionality

# File Paths
ICON_PATH = f"{ICONS_DIR}shinypy.ico"
STYLESHEET_PATH = f"{CONFIG_DIR}qstyle.qss"
PROGRESS_FILE = f"{CONFIG_DIR}progress.csv"
STATE_FILE = f"{CONFIG_DIR}last_state.txt"
SOUND_FILE = f"{SOUNDS_DIR}click.wav"
HOTKEY_FILE = f"{CONFIG_DIR}hotkeys.csv"
PKMN_FILE = f"{CONFIG_DIR}pkmn.yaml"

# UI Dimensions
POKEMON_IMAGE_SIZE = (100, 100)
MINIMUM_LABEL_WIDTH = 100

# Counter Settings
DEFAULT_COUNTER = 0
MIN_COUNTER = 0
MAX_COUNTER = 999999

# Dialog Settings
SET_COUNTER_DIALOG_TITLE = "Set Counter"
SET_COUNTER_PROMPT = "Enter new count:"

# UI Text
DEFAULT_IMAGE_TEXT = "No Pokémon Selected"
INCREMENT_BUTTON_TEXT = "+"
DECREMENT_BUTTON_TEXT = "-"
SET_BUTTON_TEXT = "Set"

# Audio Settings
DEFAULT_SOUND_VOLUME = 0.4

# Pokemon Select Dialog Constants
DIALOG_TITLE = "Select Pokémon"
# DIALOG_SIZE = (800, 600)
# GENERATIONS_CONFIG_PATH = f"{CONFIG_DIR}generations.yml"
# POKEMON_GRID_COLUMNS = 6
# POKEMON_THUMBNAIL_SIZE = 100
# POKEMON_DISPLAY_SIZE = 90
# GRID_SPACING = 10
# POKEMON_FILE_PATTERN = "*.png"
SPRITE_URI = "https://pokemondb.net/sprites"

# CSS Classes
COUNTER_LABEL_CLASS = "CounterLabel"
IMAGE_LABEL_CLASS = "ImageLabel"

# -- Options Window Constants --
class OptionsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Options")
        self.setModal(True)
        self.resize(300, 200)
        self.init_ui()
        self.load_hotkeys()

    def get_available_keys(self):
        """Get all available keyboard.Key attributes"""
        return [attr for attr in dir(keyboard.Key)
                if not attr.startswith('_') and attr != 'from_char']

    def save_hotkeys(self):
        main_hotkey = self.main_hotkey_combo.currentText()
        secondary_hotkey = self.secondary_hotkey_combo.currentText()

        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)

        with open(os.path.join(HOTKEY_FILE), 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Main HOTKEY", main_hotkey])
            writer.writerow(["Secondary HOTKEY", secondary_hotkey])

        # Update parent's hotkeys immediately
        if self.parent:
            self.parent.main_hotkey = getattr(keyboard.Key, main_hotkey)
            self.parent.secondary_hotkey = None if secondary_hotkey == 'None' else getattr(keyboard.Key,
                                                                                           secondary_hotkey)
            self.parent.restart_listener()

        self.accept()

    def load_hotkeys(self):
        try:
            if os.path.exists(HOTKEY_FILE):
                with open(HOTKEY_FILE, 'r') as file:
                    reader = csv.reader(file)
                    hotkeys = {rows[0]: rows[1] for rows in reader}

                    # Set current dropdown selections
                    main_hotkey = hotkeys.get("Main HOTKEY", "ctrl_r")
                    self.main_hotkey_combo.setCurrentText(main_hotkey)

                    secondary_hotkey = hotkeys.get("Secondary HOTKEY", "None")
                    self.secondary_hotkey_combo.setCurrentText(secondary_hotkey)
        except Exception as e:
            print(f"Error loading hotkeys: {e}")

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Main hotkey dropdown
        self.main_hotkey_label = QLabel("Main Hotkey:")
        self.main_hotkey_combo = QComboBox()
        self.main_hotkey_combo.addItems(self.get_available_keys())

        # Secondary hotkey dropdown
        self.secondary_hotkey_label = QLabel("Secondary Hotkey:")
        self.secondary_hotkey_combo = QComboBox()
        self.secondary_hotkey_combo.addItems(['None'] + self.get_available_keys())

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_hotkeys)

        layout.addWidget(self.main_hotkey_label)
        layout.addWidget(self.main_hotkey_combo)
        layout.addWidget(self.secondary_hotkey_label)
        layout.addWidget(self.secondary_hotkey_combo)
        layout.addWidget(save_button)

# -- HuntFrame Class --
class HuntFrame(QFrame):
    def __init__(self, parent=None, frame_number=1, pkmn_data=None):
        super().__init__(parent)
        self.parent = parent
        self.frame_number = frame_number
        self.pkmn_data = pkmn_data
        self.last_api_call_time = 0

        # Initialize variables
        self.counter = DEFAULT_COUNTER
        self.current_image = None
        self.current_pokemon = None
        self.progress_data = {}
        self.spritedict = {}
        self.free_api_call = 2
        self.current_sound_volume = DEFAULT_SOUND_VOLUME

        # Initialize pygame mixer for this frame
        self.add_sound = mixer.Sound(resource_path(SOUND_FILE))
        self.add_sound.set_volume(self.current_sound_volume)

        self.init_ui()
        self.load_progress()
        self.load_last_state()

    def init_ui(self):
        # Main vertical layout for the frame
        layout = QVBoxLayout()

        # Reduce margins inside the frame
        layout.setContentsMargins(2, 2, 2, 2)  # Left, Top, Right, Bottom
        # Reduce spacing between elements inside the frame
        layout.setSpacing(5)  # or any small number you prefer

        # Counter Display
        self.counter_label = QLabel(str(self.counter))
        self.counter_label.setAlignment(Qt.AlignCenter)
        self.counter_label.setObjectName("CounterLabel")
        font = self.counter_label.font()
        font.setPointSize(20)
        self.counter_label.setFont(font)
        layout.addWidget(self.counter_label)

        # Button Panel
        button_layout = QHBoxLayout()

        # Increment button
        increment_btn = QPushButton(INCREMENT_BUTTON_TEXT)
        increment_btn.clicked.connect(self.increment_count)
        increment_btn.setToolTip("Increment the counter by 1")
        increment_btn.setObjectName("IncrementButton")
        button_layout.addWidget(increment_btn)

        # Decrement button
        decrement_btn = QPushButton(DECREMENT_BUTTON_TEXT)
        decrement_btn.clicked.connect(self.decrement_count)
        decrement_btn.setToolTip("Decrement the counter by 1")
        decrement_btn.setObjectName("DecrementButton")
        button_layout.addWidget(decrement_btn)

        # Set button
        set_btn = QPushButton(SET_BUTTON_TEXT)
        set_btn.clicked.connect(self.set_count)
        set_btn.setToolTip("Set the counter to a specific value")
        set_btn.setObjectName("SetButton")
        button_layout.addWidget(set_btn)

        layout.addLayout(button_layout)

        # Pokemon Image Display
        self.image_label = QLabel(DEFAULT_IMAGE_TEXT)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setObjectName("ImageLabel")
        self.image_label.setMinimumSize(*POKEMON_IMAGE_SIZE)
        layout.addWidget(self.image_label)

        # Pokemon Dropdown Menu
        self.pkmn_combobox = QComboBox()
        self.pkmn_combobox.setEditable(True)
        completer = QCompleter(self.pkmn_data.keys(), self.pkmn_combobox)
        self.pkmn_combobox.setCompleter(completer)
        self.pkmn_combobox.addItems(self.pkmn_data.keys())
        layout.addWidget(self.pkmn_combobox)
        self.pkmn_combobox.currentTextChanged.connect(self.fetch_forms)

        # Pokemon Form Dropdown Menu
        self.form_combobox = QComboBox()
        self.form_combobox.setEditable(False)
        self.form_combobox.addItem("Select a Pokémon first")
        layout.addWidget(self.form_combobox)
        self.form_combobox.currentTextChanged.connect(self.load_image)

        self.setLayout(layout)
  
  
    def increment_count(self):
        self.counter += 1
        self.update_counter()
        self.save_progress()
        self.add_sound.play()

    def decrement_count(self):
        if self.counter > 0:
            self.counter -= 1
            self.update_counter()
            self.save_progress()

    def set_count(self):
        number, ok = QInputDialog.getInt(
            self,
            SET_COUNTER_DIALOG_TITLE,
            SET_COUNTER_PROMPT,
            value=self.counter,
            min=MIN_COUNTER,
            max=MAX_COUNTER
        )
        if ok:
            self.counter = number
            self.update_counter()
            self.save_progress()

    def update_counter(self):
        self.counter_label.setText(str(self.counter))

    def fetch_forms(self, selected_pokemon):

        now = time.time()

        if now - self.last_api_call_time < 0.5:
            time.sleep(0.5)  # Wait for 0.5 seconds before allowing another API call
            self.form_combobox.clear()
            self.form_combobox.addItem("Please wait before fetching forms again")


        self.last_api_call_time = now

        if not selected_pokemon:
            return

        if selected_pokemon not in list(self.pkmn_data.keys()):
            return

        try:
            # Fetch Pokémon species data from the API
            # print(f"Fetching forms for {selected_pokemon}...")
            response = requests.get(f"https://pokemondb.net/sprites/{selected_pokemon}")
            response.raise_for_status()
            data = response.text

            # Clear the form combobox
            self.form_combobox.clear()

            pngs = re.findall(r'(?<=href=\")https://[^"]+\.png', data)

            for png in pngs:
                if "/shiny/" in png:
                    trash = png.split("https://img.pokemondb.net/sprites/")[1].split(".png")[0]
                    game, name = trash.split("/shiny/")
                    formname = f"{game}: {name}"
                    self.spritedict[formname] = png                    
                    self.form_combobox.addItem(formname)


        except requests.exceptions.RequestException as e:
            print(f"Error fetching forms for {selected_pokemon}: {e}")    

    def load_image(self, pokemon_name):

        if not pokemon_name:
            print("load_image(): No Pokémon selected.")
            self.image_label.setText(DEFAULT_IMAGE_TEXT)
            self.current_image = None
            return
        
        if not self.spritedict:
            print("load_image(): No forms available for the selected Pokémon.")
            self.image_label.setText("No forms available")
            self.current_image = None
            return

        if self.free_api_call <= 0:
            now = time.time()

            if now - self.last_api_call_time < 0.5:
                time.sleep(1.5)  # Wait for 1.5 seconds before allowing another API call
                print("API call rate limit exceeded. Please wait before loading an image again.")
                self.image_label.setText("Please wait before loading an image again")
                self.current_image = None
                # return
            
            self.last_api_call_time = now
        
        image_url = self.spritedict.get(pokemon_name)

        self.free_api_call -= 1

        response = requests.get(image_url)
        response.raise_for_status()

        image_data = BytesIO(response.content)
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data.read()):
            print("Failed to load image from data.")
            return

        self.current_image = pixmap
        self.image_label.setPixmap(
            self.current_image.scaled(
                POKEMON_IMAGE_SIZE[0],
                POKEMON_IMAGE_SIZE[1],
                Qt.KeepAspectRatio
            )
        )

        self.current_pokemon = self.pkmn_combobox.currentText()
        self.load_pokemon_count()

        self.save_progress()
        self.save_last_state()

    def load_progress(self):
        try:
            if os.path.exists(resource_path(PROGRESS_FILE)):
                with open(resource_path(PROGRESS_FILE), 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    self.progress_data = {row[0]: row[1] for row in reader if len(row) == 2}
        except Exception as e:
            print(f"Error loading progress: {e}")
            self.progress_data = {}

    def load_pokemon_count(self):
        if self.current_pokemon and self.current_pokemon in self.progress_data:
            self.counter = int(self.progress_data[self.current_pokemon])
            self.update_counter()
        else:
            self.counter = DEFAULT_COUNTER
            self.update_counter()

    def load_last_state(self):
        try:
            if os.path.exists(resource_path(STATE_FILE)):
                with open(resource_path(STATE_FILE), 'r', encoding='utf-8') as file:
                    last_pokemon = file.read().strip()

                    if last_pokemon:
                        species, form = last_pokemon.split(',-,')
                        self.current_pokemon = species
                        self.pkmn_combobox.setCurrentText(species)
                        self.form_combobox.setCurrentText(form)
                        # self.load_image(form)

                        if self.current_pokemon in self.progress_data:
                            self.counter = int(self.progress_data[self.current_pokemon])
                            self.update_counter()

        except Exception as e:
            print(f"Error loading last state: {e}")

    def save_progress(self):
        if self.current_pokemon:

            try:
                # Load existing data
                all_progress = {}
                if os.path.exists(resource_path(PROGRESS_FILE)):
                    with open(resource_path(PROGRESS_FILE), 'r', newline='', encoding='utf-8') as file:
                        reader = csv.reader(file)
                        all_progress = {row[0]: row[1] for row in reader if len(row) == 2}

                # Update current Pokémon's data
                all_progress[self.current_pokemon] = str(self.counter)

                # Save all data back to file
                os.makedirs(os.path.dirname(resource_path(PROGRESS_FILE)), exist_ok=True)
                with open(resource_path(PROGRESS_FILE), 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    for pokemon, count in all_progress.items():
                        writer.writerow([pokemon, count])
            except Exception as e:
                print(f"Error saving progress: {e}")

    def save_last_state(self):
        if self.current_pokemon:
            try:
                os.makedirs(os.path.dirname(resource_path(STATE_FILE)), exist_ok=True)
                with open(resource_path(STATE_FILE), 'w', encoding='utf-8') as file:
                    file.write(f"{self.current_pokemon},-,{self.form_combobox.currentText()}")
            except Exception as e:
                print(f"Error saving last state: {e}")

# -- Main Application Class --
class ShinyCounter(QMainWindow):
    def __init__(self):
        super().__init__()

        # Main Window Configuration
        self.setWindowTitle(APP_NAME)
        self.setGeometry(
            WINDOW_POSITION[0],
            WINDOW_POSITION[1],
            WINDOW_SIZE[0],
            WINDOW_SIZE[1]
        )
        self.setMinimumSize(*MINIMUM_WINDOW_SIZE)
        self.setMaximumSize(*MAXIMUM_WINDOW_SIZE)
        self.setWindowIcon(QIcon(resource_path(ICON_PATH)))

        self.setWindowOpacity(0.7)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()  # Changed to horizontal for side-by-side frames
        self.main_layout.setSpacing(1)
        self.central_widget.setLayout(self.main_layout)

        # Initialize pygame mixer
        mixer.init()

        # Load Pokemon YAML data
        self.pkmn_data = self.load_pkmn_data()

        # Initialize hunt frames
        self.hunt_frame_1 = HuntFrame(self, frame_number=1, pkmn_data=self.pkmn_data)
        self.hunt_frame_2 = None

        # Add first frame to layout
        self.main_layout.addWidget(self.hunt_frame_1)

        # Setup global hotkey listener
        self.main_hotkey = HOTKEY_ADD
        self.secondary_hotkey = None
        self.load_hotkeys()
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

        # Setup menu bar
        self.init_menu_bar()

        # Load stylesheet
        self.load_stylesheet()

    def init_menu_bar(self):
        menu_bar = self.menuBar()
        options_menu = menu_bar.addMenu("Options")

        # Add Transparency Toggle
        transparency_action = QAction("Toggle Transparency", self)
        transparency_action.setCheckable(True)
        transparency_action.setChecked(True)
        transparency_action.triggered.connect(self.toggle_transparency)
        options_menu.addAction(transparency_action)

        # Add Sound option window
        sound_action = QAction("Sound Settings", self)
        sound_action.triggered.connect(self.show_sound_config)
        options_menu.addAction(sound_action)

        # Add Hotkey Settings option
        hotkey_action = QAction("Hotkey Settings", self)
        hotkey_action.triggered.connect(self.show_hotkey_config)
        options_menu.addAction(hotkey_action)

        # Add hunt mode toggle
        self.hunt_mode_action = QAction("Double-Hunting", self)
        self.hunt_mode_action.setCheckable(True)
        self.hunt_mode_action.triggered.connect(self.toggle_hunt_mode)
        options_menu.addAction(self.hunt_mode_action)

        # Add Update PKMN JSON option
        load_progress_action = QAction("Update Pokemon", self)
        load_progress_action.triggered.connect(self.update_pkmn_json)
        options_menu.addAction(load_progress_action)

    def show_sound_config(self):
        self.sound_dialog = QDialog(self)
        self.sound_dialog.setWindowTitle("Sound Settings")
        self.sound_dialog.setModal(True)
        self.sound_dialog.resize(249, 75)

        layout = QVBoxLayout(self.sound_dialog)

        # Sound volume control
        self.volume_label = QLabel("Sound Volume:    %")
        self.volume_label.setText(f"Sound Volume: {int(self.hunt_frame_1.current_sound_volume * 100)}%")
        self.volume_label.setAlignment(Qt.AlignCenter)
        self.volume_label.setObjectName("VolumeLabel")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.hunt_frame_1.current_sound_volume * 100))
        self.volume_slider.setTickInterval(10)
        self.volume_slider.valueChanged.connect(self.update_sound_volume)

        layout.addWidget(self.volume_label)
        layout.addWidget(self.volume_slider)

        self.sound_dialog.exec_()

    def update_sound_volume(self, value):
        self.hunt_frame_1.add_sound.set_volume(value / 100.0)
        self.volume_label.setText(f"Sound Volume: {value}%")
        self.hunt_frame_1.current_sound_volume = value / 100.0

    def show_hotkey_config(self):
        self.options_window = OptionsWindow(self)
        self.options_window.show()

    def on_press(self, key):
        try:
            if key == self.main_hotkey:
                if self.hunt_mode_action.isChecked() and self.hunt_frame_2:
                    QTimer.singleShot(0, self.hunt_frame_2.increment_count)
                else:
                    QTimer.singleShot(0, self.hunt_frame_1.increment_count)
            elif key == self.secondary_hotkey:
                QTimer.singleShot(0, self.hunt_frame_1.increment_count)
        except AttributeError:
            pass

    def load_hotkeys(self):
        try:
            if os.path.exists(HOTKEY_FILE):
                with open(resource_path(HOTKEY_FILE), 'r') as file:
                    reader = csv.reader(file)
                    hotkeys = {rows[0]: rows[1] for rows in reader}
                    main_hotkey = hotkeys.get("Main HOTKEY", "ctrl_r")
                    secondary_hotkey = hotkeys.get("Secondary HOTKEY", "None")

                    self.main_hotkey = getattr(keyboard.Key, main_hotkey, HOTKEY_ADD)
                    self.secondary_hotkey = None if secondary_hotkey == 'None' else getattr(keyboard.Key,
                                                                                            secondary_hotkey)
        except Exception as e:
            print(f"Error loading hotkeys: {e}")
            self.main_hotkey = HOTKEY_ADD
            self.secondary_hotkey = None

    def restart_listener(self):
        if hasattr(self, 'listener'):
            self.listener.stop()
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def load_stylesheet(self):
        try:
            with open(resource_path(STYLESHEET_PATH), "r") as file:
                self.setStyleSheet(file.read())
        except FileNotFoundError:
            print("Stylesheet not found. Using default styles.")

    def toggle_transparency(self):
        current_opacity = self.windowOpacity()
        if current_opacity == 1.0:
            self.setWindowOpacity(0.7)
        else:
            self.setWindowOpacity(1.0)

    def toggle_hunt_mode(self):
        current_position = self.pos()  # Store the current position of the window

        if self.hunt_mode_action.isChecked():
            # Switch to double hunting
            if not self.hunt_frame_2:
                self.hunt_frame_2 = HuntFrame(self, frame_number=2, pkmn_data=self.pkmn_data)
            self.hunt_frame_2.show()
            self.main_layout.addWidget(self.hunt_frame_2)
            self.hunt_mode_action.setText("Single-Hunting")

            # Update window constraints for double hunting
            self.setMinimumSize(*DOUBLE_MINIMUM_WINDOW_SIZE)
            self.setMaximumSize(*DOUBLE_MAXIMUM_WINDOW_SIZE)
            self.resize(*DOUBLE_WINDOW_SIZE)
        else:
            # Switch to single hunting
            if self.hunt_frame_2:
                self.hunt_frame_2.hide()
                self.main_layout.removeWidget(self.hunt_frame_2)
                self.hunt_frame_2.deleteLater()
                self.hunt_frame_2 = None
            self.hunt_mode_action.setText("Double-Hunting")

            # Restore original window constraints
            self.setMinimumSize(*MINIMUM_WINDOW_SIZE)
            self.setMaximumSize(*MAXIMUM_WINDOW_SIZE)
            self.resize(*WINDOW_SIZE)

        self.move(current_position)  # Restore the window to its original position

    def load_pkmn_data(self):
        try:
            with open(resource_path(PKMN_FILE), "r") as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            self.show_messagebox("Error", "Pokémon data file not found. Please update Pokémon data.")
            return {}

    def update_pkmn_json(self):
        try:
            BASE = "https://pokeapi.co/api/v2/"
            pkmn_dict = {}

            def fetch_json(endpoint):
                r = requests.get(f"{BASE}{endpoint}?limit=10000")
                r.raise_for_status()
                return r.json()

            generations = fetch_json("generation")

            for gen in generations["results"]:
                gen_id = gen["url"].split("/")[-2]  # Extract generation number from URL

                genpkmn = fetch_json(f"generation/{gen_id}")

                for species in genpkmn["pokemon_species"]:
                    species_name = species["name"]
                    pkmn_dict[species_name] = [gen_id]

            with open(resource_path(PKMN_FILE), "w") as f:
                yaml.dump(pkmn_dict, f, default_flow_style=False)
        except Exception as e:
            self.show_messagebox("Error", f"Failed to update Pokémon data: {e}")
            return

    def show_messagebox(self, title, message):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def closeEvent(self, event):
        # Save state for both frames
        self.hunt_frame_1.save_progress()
        self.hunt_frame_1.save_last_state()
        if self.hunt_frame_2:
            self.hunt_frame_2.save_progress()
            self.hunt_frame_2.save_last_state()
        event.accept()

# -- Main Loop --
def main():
    app = QApplication(sys.argv)
    window = ShinyCounter()
    window.show()

    sys.exit(app.exec_())

# -- Entry Point --
if __name__ == "__main__":
    main()
