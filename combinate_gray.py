import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import os
import re
import numpy as np
import math

def extract_id_from_filename(filename):
    match = re.search(r'ID_(\d+)', filename)
    return match.group(1) if match else "Unknown"

def display_images(paths, save_path=None):
    num_images = len(paths)
    rows = 3
    cols = 3  # Automatyczna liczba kolumn

    fig, axs = plt.subplots(rows, cols, figsize=(18, 18))  # Większe okienka


    axs = axs.flatten() if rows > 1 or cols > 1 else [axs]

    for idx, ax in enumerate(axs):
        if idx < num_images:
            img_path = paths[idx]
            img = mpimg.imread(img_path)

            # Konwersja do skali szarości, jeśli obraz jest RGB
            if img.ndim == 3:
                img = np.mean(img, axis=2)

            pattern_id = extract_id_from_filename(os.path.basename(img_path))

            ax.imshow(img, cmap='gray')  # Skala szarości
            ax.axis('off')
            ax.set_title(f"Wzorzec {pattern_id}", fontsize=25)
        else:
            ax.axis('off')

    # Legenda (ON = czarny, OFF = szary)
    # legend_labels = {"ON": "black", "OFF": "gray"}
    # legend_handles = [
    #     plt.Rectangle((0, 0), 1, 1, color=color, edgecolor='black', linewidth=1)
    #     for color in legend_labels.values()
    # ]

    # fig.legend(
    #     legend_handles,
    #     legend_labels.keys(),
    #     loc='lower center',
    #     ncol=2,
    #     fontsize='large',
    #     title='Legend'
    # )

    plt.subplots_adjust(wspace=0.01, hspace=0.15, bottom=0.1)

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, format='png', bbox_inches='tight')

    plt.show()

image_paths = [
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_3.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_2.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_4.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_5.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_8.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_9.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_19.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_21.png",
    r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_26.png",
]   

save_path = r"C:\Users\marsieradzka\Desktop\Isopien studia\wszytskie_inz\Pattern\ID_3X3_kk_pl.png"
display_images(image_paths, save_path=save_path)
