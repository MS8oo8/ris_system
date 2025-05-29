import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageDraw
import json

def get_hex_pattern_by_id(pattern_id):
    json_file = "RIS_patterns.json"  # Nazwa pliku JSON
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    for pattern in data["PATTERNS"]:
        if pattern["ID"] == pattern_id:
            return pattern["HEX"]
    
    return None  # return None if pattern_id not found

def get_id_pattern_by_hex(hex_pattern):
    json_file = "RIS_patterns.json"  # Nazwa pliku JSON
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    for pattern in data["PATTERNS"]:
        if pattern["HEX"] == hex_pattern:
            return pattern["ID"]
    
    return None  # return None if hex_pattern not found

def hex_to_bin(hex_string):
    # Usuwamy prefix 0x
    hex_string = hex_string.replace("0x", "") 
    # Konwersja hex na binarną z usunięciem prefixu binarnego '0b' i dopełnieniem zerami
    bin_string = ''.join(format(int(c, 16),'04b') for c in hex_string)
    return bin_string

def save_image(image):
    # Otwórz okno dialogowe do wyboru miejsca zapisu
    file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
    if file_path:
        image.save(file_path)
        print(f"Obraz zapisano jako: {file_path}")

# Funkcja rysująca GUI na podstawie ciągu binarnego i zapisująca obraz
def generate_image(binary_string):
    grid_size = 16
    cell_size = 30
    outer_margin = 10
    inner_margin = 4

    # Tworzenie obrazu
    img_size = (
        grid_size * cell_size * 2 + 2 * (outer_margin + inner_margin),
        grid_size * cell_size + 2 * (outer_margin + inner_margin)
    )
    image = Image.new("RGB", img_size, "white")
    draw = ImageDraw.Draw(image)

    # Rysowanie czarnej otoczki
    black_rect_start = (outer_margin, outer_margin)
    black_rect_end = (
        img_size[0] - outer_margin,
        img_size[1] - outer_margin
    )
    draw.rectangle([black_rect_start, black_rect_end], fill="black")

    # Rysowanie siatki na białym tle
    grid_start_x = outer_margin + inner_margin
    grid_start_y = outer_margin + inner_margin

    for i in range(256):
        row = i // grid_size
        col = i % grid_size
        color = "blue" if binary_string[i] == '1' else "lightblue"

        # Współrzędne komórki w obrazie
        x1 = grid_start_x + col * cell_size * 2
        y1 = grid_start_y + row * cell_size
        x2 = x1 + cell_size * 2
        y2 = y1 + cell_size
        draw.rectangle([x1, y1, x2, y2], fill=color, outline="black")

    # Tworzenie okna GUI
    window = tk.Tk()
    window.title("Hex to Binary Grid")

    outer_frame = tk.Frame(window, bg="white", padx=outer_margin, pady=outer_margin)
    outer_frame.pack()

    inner_frame = tk.Frame(outer_frame, bg="black", padx=inner_margin, pady=inner_margin)
    inner_frame.pack()

    for i in range(256):
        row = i // grid_size
        col = i % grid_size
        color = "blue" if binary_string[i] == '1' else "lightblue"

        # Rysowanie w GUI
        cell = tk.Frame(inner_frame, width=cell_size*2, height=cell_size, bg=color, highlightbackground="black", highlightthickness=1)
        cell.grid(row=row, column=col)

    # Dodanie przycisku zapisu obrazu
    save_button = ttk.Button(window, text="Zapisz obraz jako PNG", command=lambda: save_image(image))
    save_button.pack(pady=(10, 0))

    window.mainloop()

def on_convert():
    pattern_id_or_hex = entry.get()
    if pattern_id_or_hex.startswith("0x"): # If the input is HEX
        bin_string = hex_to_bin(pattern_id_or_hex)
        generate_image(bin_string)
    else: # If the input is ID
        hex_pattern = get_hex_pattern_by_id(pattern_id_or_hex)
        if hex_pattern:
            bin_string = hex_to_bin(hex_pattern)
            generate_image(bin_string)
        else:
            print("Pattern o podanym ID nie został znaleziony.")

# Ustawienia GUI
root = tk.Tk()
root.title("Hex to Bin Image Converter")

# Etykieta i pole wprowadzania
label = ttk.Label(root, text="Podaj ID patternu lub HEX:")
label.pack(pady=(10, 5))
entry = ttk.Entry(root)
entry.pack(pady=(0, 5))

# Przycisk do konwersji
convert_button = ttk.Button(root, text="Konwertuj i pokaż obraz", command=on_convert)
convert_button.pack(pady=(0, 10))

root.mainloop()