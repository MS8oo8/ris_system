import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import os
import re

def extract_id_from_filename(filename):
    """Wyciąga ID z nazwy pliku w formacie ID_{id}.png."""
    match = re.search(r'ID_(\d+)', filename)
    return match.group(1) if match else "Unknown"

def display_images(paths, save_path=None):
    num_images = len(paths)
    rows = 3  # Liczba wierszy
    cols = 3  # Liczba kolumn (dynamiczna w zależności od liczby obrazów)

    fig, axs = plt.subplots(rows, cols, figsize=(17, 10))

    if rows == 1 and cols == 1:
        axs = [[axs]]
    elif rows == 1:
        axs = [axs]

    for i in range(rows):
        for j in range(cols):
            img_index = i * cols + j
            if img_index < num_images:
                img_path = paths[img_index]
                img = mpimg.imread(img_path)

                # Wyciąganie ID z nazwy pliku
                filename = os.path.basename(img_path)
                pattern_id = extract_id_from_filename(filename)

                axs[i][j].imshow(img)
                axs[i][j].axis('off')
                axs[i][j].set_title(f"Pattern {pattern_id}", fontsize=14)  # Dodanie tytułu na podstawie ID
            else:
                axs[i][j].axis('off')  # Ukrycie pustych osi

    # Dodanie legendy na dole
    legend_labels = {"ON": "black", "OFF": "gray"}
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=color, edgecolor='black', linewidth=1) for color in legend_labels.values()]
    legend_texts = list(legend_labels.keys())

    fig.legend(
        legend_handles,
        legend_texts,
        loc='lower center',
        ncol=2,
        fontsize='large',
        title='Legend'
    )

    # Dostosowanie odstępów między obrazami
    plt.subplots_adjust(wspace=0.01, hspace=0.01, bottom=0.01)

    if save_path:
        plt.savefig(save_path, format='png', bbox_inches='tight')

    plt.show()

image_paths = [
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_3.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_8.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_9.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_4.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_21.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_26.png"
]

save_path = r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_3X3.png"
display_images(image_paths, save_path=save_path)
