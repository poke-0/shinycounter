import sys
import os
import glob
import yaml
import csv
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QWidget, QDialog, QScrollArea,
    QGridLayout, QInputDialog, QTabWidget, QMenuBar, QMenu, QAction,
    QLineEdit, QComboBox
)
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence
from PyQt5.QtCore import Qt, QEvent
from pynput import keyboard
from pygame import mixer


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS2
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# Application Constants
APP_NAME = "ShinyCounter"
WINDOW_SIZE = (200, 230)
MINIMUM_WINDOW_SIZE = (200, 230)
MAXIMUM_WINDOW_SIZE = (350, 345)
WINDOW_POSITION = (1200, -460)

HOTKEY_ADD = keyboard.Key.ctrl_r

# Directory Paths
CONFIG_DIR = "config/"
ICONS_DIR = "icons/"
SOUNDS_DIR = "sounds/"
BACKUPS_DIR = "backups/"  # If you plan to add backup functionality

# File Paths
ICON_PATH = f"{ICONS_DIR}shinypy.ico"
IMAGE_PATH = "spngs/"
STYLESHEET_PATH = f"{CONFIG_DIR}qstyle.qss"
PROGRESS_FILE = f"{CONFIG_DIR}progress.csv"
STATE_FILE = f"{CONFIG_DIR}last_state.txt"
SOUND_FILE = f"{SOUNDS_DIR}click.wav"
HOTKEY_FILE = f"{CONFIG_DIR}hotkeys.csv"

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
FILE_DIALOG_TITLE = "Select Pokémon Image"
FILE_DIALOG_FILTER = "Images (*.png *.jpg *.bmp)"

# UI Text
DEFAULT_IMAGE_TEXT = "No Pokémon Selected"
INCREMENT_BUTTON_TEXT = "+"
DECREMENT_BUTTON_TEXT = "-"
SET_BUTTON_TEXT = "Set"
LOAD_BUTTON_TEXT = "Load"

# Audio Settings
SOUND_VOLUME = 0.2

# Pokemon Select Dialog Constants
DIALOG_TITLE = "Select Pokémon"
DIALOG_SIZE = (800, 600)
GENERATIONS_CONFIG_PATH = f"{CONFIG_DIR}generations.yml"
POKEMON_GRID_COLUMNS = 6
POKEMON_THUMBNAIL_SIZE = 100
POKEMON_DISPLAY_SIZE = 90
GRID_SPACING = 10
POKEMON_FILE_PATTERN = "*.png"

# CSS Classes
COUNTER_LABEL_CLASS = "CounterLabel"
IMAGE_LABEL_CLASS = "ImageLabel"


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


class PokemonSelectDialog(QDialog):
    def __init__(self, parent=None, image_path=None):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE)
        self.setModal(True)
        self.image_path = image_path
        self.selected_pokemon = None
        self.generations = self.load_generations()
        self.current_loaded_tab = None

        self.resize(*DIALOG_SIZE)
        self.init_ui()

    def load_generations(self):
        try:
            with open(resource_path(GENERATIONS_CONFIG_PATH), 'r') as file:
                config = yaml.safe_load(file)
                return config['generations']
        except Exception as e:
            print(f"Error loading generations config: {e}")
            return {}

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        for gen_name in self.generations:
            gen_tab = QWidget()
            gen_layout = QVBoxLayout(gen_tab)
            gen_layout.setAlignment(Qt.AlignCenter)
            formatted_gen_name = gen_name.capitalize()

            self.tab_widget.addTab(gen_tab, formatted_gen_name)

        layout.addWidget(self.tab_widget)

    def on_tab_changed(self, index):
        if self.current_loaded_tab is not None:
            self.unload_generation_images(self.current_loaded_tab)

        selected_tab = self.tab_widget.widget(index)
        gen_name = self.tab_widget.tabText(index).lower()

        self.load_generation_images(gen_name, selected_tab)
        self.current_loaded_tab = selected_tab

    def unload_generation_images(self, gen_tab):
        layout = gen_tab.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def load_generation_images(self, gen_name, gen_tab):
        gen_data = self.generations[gen_name]

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(GRID_SPACING)
        grid_layout.setAlignment(Qt.AlignCenter)

        image_files = glob.glob(os.path.join(self.image_path, POKEMON_FILE_PATTERN))
        gen_files = []
        for image_path in image_files:
            try:
                dex_num = int(os.path.basename(image_path).split('-')[0])
                if gen_data['start'] <= dex_num <= gen_data['end']:
                    gen_files.append(image_path)
            except (ValueError, IndexError):
                continue

        gen_files.sort(key=lambda x: int(os.path.basename(x).split('-')[0]))

        for index, image_path in enumerate(gen_files):
            label = QLabel()
            label.setFixedSize(POKEMON_THUMBNAIL_SIZE, POKEMON_THUMBNAIL_SIZE)
            label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(
                POKEMON_DISPLAY_SIZE,
                POKEMON_DISPLAY_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            label.setPixmap(scaled_pixmap)

            pokemon_name = os.path.basename(image_path).split('-')[1].split('.')[0]
            label.setToolTip(pokemon_name.capitalize())

            # Set a unique object name for styling
            label.setObjectName(f"PokemonImage_{dex_num}")

            label.mousePressEvent = lambda e, path=image_path: self.on_pokemon_selected(path)

            row = index // POKEMON_GRID_COLUMNS
            col = index % POKEMON_GRID_COLUMNS
            grid_layout.addWidget(label, row, col, Qt.AlignCenter)

        scroll_area.setWidget(container)
        layout = gen_tab.layout()
        layout.addWidget(scroll_area)

    def on_pokemon_selected(self, image_path):
        self.selected_pokemon = image_path
        self.accept()


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

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        # Initialize pygame mixer
        mixer.init()
        self.add_sound = mixer.Sound(SOUND_FILE)
        self.add_sound.set_volume(SOUND_VOLUME)

        # Initialize variables
        self.counter = DEFAULT_COUNTER
        self.current_image = None
        self.current_pokemon = None
        self.progress_data = {}

        self.load_progress()
        self.init_ui()
        self.load_last_state()
        self.load_hotkeys()

        # Setup global hotkey listener
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

        # Setup menu bar
        self.init_menu_bar()

    def init_menu_bar(self):
        menu_bar = self.menuBar()
        options_menu = menu_bar.addMenu("Options")

        options_action = QAction("Options", self)
        options_action.triggered.connect(self.show_options_window)
        options_menu.addAction(options_action)

    def show_options_window(self):
        self.options_window = OptionsWindow(self)
        self.options_window.show()

    def load_hotkeys(self):
        try:
            if os.path.exists(HOTKEY_FILE):
                with open(HOTKEY_FILE, 'r') as file:
                    reader = csv.reader(file)
                    hotkeys = {rows[0]: rows[1] for rows in reader}
                    self.main_hotkey = KEY_MAP.get(hotkeys.get("Main HOTKEY"), HOTKEY_ADD)
                    self.secondary_hotkey = KEY_MAP.get(hotkeys.get("Secondary HOTKEY"), None)
        except Exception as e:
            print(f"Error loading hotkeys: {e}")
            self.main_hotkey = HOTKEY_ADD
            self.secondary_hotkey = None

    def restart_listener(self):
        """Restart the keyboard listener with new hotkeys"""
        if hasattr(self, 'listener'):
            self.listener.stop()  # Stop the current listener
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def on_press(self, key):
        if key == self.main_hotkey:
            self.increment_count()
        elif key == self.secondary_hotkey:
            # Handle secondary hotkey action here
            pass

    def init_ui(self):
        # Load external stylesheet
        self.load_stylesheet()

        # Main vertical layout
        main_layout = QVBoxLayout()
        self.central_widget.setLayout(main_layout)

        # Display for the counter
        self.counter_label = QLabel(str(self.counter))
        self.counter_label.setAlignment(Qt.AlignCenter)
        self.counter_label.setObjectName("CounterLabel")
        main_layout.addWidget(self.counter_label)

        # Button Panel
        button_layout = QHBoxLayout()

        # Increment button
        increment_btn = QPushButton(INCREMENT_BUTTON_TEXT)
        increment_btn.clicked.connect(self.increment_count)
        button_layout.addWidget(increment_btn)

        # Decrement button
        decrement_btn = QPushButton(DECREMENT_BUTTON_TEXT)
        decrement_btn.clicked.connect(self.decrement_count)
        button_layout.addWidget(decrement_btn)

        # Set button
        set_btn = QPushButton(SET_BUTTON_TEXT)
        set_btn.clicked.connect(self.set_count)
        button_layout.addWidget(set_btn)

        main_layout.addLayout(button_layout)

        # Pokemon Image Display
        self.image_label = QLabel(DEFAULT_IMAGE_TEXT)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setObjectName("ImageLabel")
        self.image_label.setMinimumSize(*POKEMON_IMAGE_SIZE)
        main_layout.addWidget(self.image_label)

        # Load Button
        load_btn = QPushButton(LOAD_BUTTON_TEXT)
        load_btn.clicked.connect(self.show_pokemon_selector)
        main_layout.addWidget(load_btn)

    def show_pokemon_selector(self):
        dialog = PokemonSelectDialog(self, IMAGE_PATH)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_pokemon:
            self.current_image = QPixmap(dialog.selected_pokemon)
            self.image_label.setPixmap(
                self.current_image.scaled(
                    POKEMON_IMAGE_SIZE[0],
                    POKEMON_IMAGE_SIZE[1],
                    Qt.KeepAspectRatio
                )
            )
            # Extract Pokemon name from file path
            self.current_pokemon = os.path.splitext(os.path.basename(dialog.selected_pokemon))[0].split('-')[1]
            self.load_pokemon_count()
            self.save_progress()

    def load_specific_image(self, image_path):
        """Load a specific image file"""
        if os.path.exists(image_path):
            self.current_image = QPixmap(image_path)
            self.image_label.setPixmap(
                self.current_image.scaled(
                    POKEMON_IMAGE_SIZE[0],
                    POKEMON_IMAGE_SIZE[1],
                    Qt.KeepAspectRatio
                )
            )

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

    def load_progress(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            if os.path.exists(PROGRESS_FILE):
                with open(resource_path(PROGRESS_FILE), 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    self.progress_data = {row[0]: row[1] for row in reader if len(row) == 2}
        except Exception as e:
            print(f"Error loading progress: {e}")
            self.progress_data = {}

    def save_progress(self):
        if self.current_pokemon:
            try:
                self.progress_data[self.current_pokemon] = str(self.counter)
                os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
                with open(resource_path(PROGRESS_FILE), 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    for pokemon, count in self.progress_data.items():
                        writer.writerow([pokemon, count])
            except Exception as e:
                print(f"Error saving progress: {e}")

    def load_pokemon_count(self):
        if self.current_pokemon and self.current_pokemon in self.progress_data:
            self.counter = int(self.progress_data[self.current_pokemon])
            self.update_counter()
        else:
            self.counter = DEFAULT_COUNTER
            self.update_counter()

    def load_last_state(self):
        """Load the last used Pokemon"""
        try:
            if os.path.exists(STATE_FILE):
                with open(resource_path(STATE_FILE), 'r', encoding='utf-8') as file:
                    last_pokemon = file.read().strip()
                    if last_pokemon:
                        # Find the corresponding image file
                        pokemon_files = glob.glob(os.path.join(IMAGE_PATH, POKEMON_FILE_PATTERN))
                        for file_path in pokemon_files:
                            if last_pokemon in os.path.basename(file_path):
                                self.current_pokemon = last_pokemon
                                self.load_specific_image(file_path)
                                if self.current_pokemon in self.progress_data:
                                    self.counter = int(self.progress_data[self.current_pokemon])
                                    self.update_counter()
                                break
        except Exception as e:
            print(f"Error loading last state: {e}")

    def save_last_state(self):
        """Save the current Pokemon as last used"""
        if self.current_pokemon:
            try:
                os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
                with open(resource_path(STATE_FILE), 'w', encoding='utf-8') as file:
                    file.write(self.current_pokemon)
            except Exception as e:
                print(f"Error saving last state: {e}")

    def load_stylesheet(self):
        try:
            with open(resource_path(STYLESHEET_PATH), "r") as file:
                self.setStyleSheet(file.read())
        except FileNotFoundError:
            print("Stylesheet not found. Using default styles.")

    def closeEvent(self, event):
        """Override closeEvent to save progress when closing the window"""
        self.save_progress()
        self.save_last_state()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = ShinyCounter()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
