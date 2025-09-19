# NodeFlow

**A powerful, node-based automation and data acquisition tool with OPC-UA connectivity.**

NodeFlow is a versatile desktop application designed for engineers, technicians, and researchers who need to automate processes, acquire data, and interact with industrial devices. At its core, NodeFlow provides a graphical, node-based editor that allows users to build complex sequences and workflows without writing extensive code.

With built-in support for the OPC-UA protocol, NodeFlow can seamlessly communicate with a wide range of industrial hardware and software, from PLCs and sensors to SCADA systems and databases. Its rich feature set, including data processing, visualization, and even computer vision capabilities, makes it an all-in-one solution for test automation, industrial data logging, and process control.

## Key Features

*   **Intuitive Node-Based Editor:** Drag, drop, and connect nodes to create custom automation sequences and logic flows.
*   **OPC-UA Connectivity:** A first-class OPC-UA client to browse server address spaces, read/write variables, and call methods.
*   **Rich Data Processing:** Leverage the power of `numpy` and `pandas` for complex numerical and data analysis tasks within your workflows.
*   **Integrated Visualization:** Use `matplotlib` nodes to plot data in real-time, helping you visualize signals, trends, and results.
*   **Computer Vision & AI:** Incorporate image processing (`OpenCV`), OCR (`easyocr`), and machine learning (`PyTorch`) directly into your automation flows for advanced inspection and analysis tasks.
*   **Customizable UI:** Switch between light and dark themes for a comfortable user experience.
*   **Cross-Platform:** Built with Python and PyQt6, allowing it to run on various operating systems.
*   **Standalone Export:** Package your project and its dependencies into a single executable using PyInstaller.

## Getting Started

Follow these instructions to get a local copy up and running for development or use.

### Prerequisites

You will need Python installed on your system. It is recommended to use Python 3.8 or newer.

*   **Python 3.8+**

You can check your Python version by running:
```bash
python --version
```

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required packages:**
    The `requirements.txt` file contains all the necessary Python packages. Install them using pip:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: The `requirements.txt` file is extensive due to the inclusion of libraries like PyTorch and OpenCV. The installation may take some time.*

## Usage

Once the dependencies are installed, you can run the application from the root directory of the project:

```bash
python main.py
```

This will launch the NodeFlow main window, where you can start creating new workflows or loading existing ones.

## Building from Source

To create a standalone executable for distribution, this project uses PyInstaller. A `.spec` file (`main.spec`) is already configured for this purpose.

1.  **Ensure all dependencies, including `pyinstaller`, are installed.**

2.  **Run the PyInstaller build command:**
    ```bash
    pyinstaller main.spec
    ```

3.  **Find the executable:**
    The bundled application will be located in the `dist/main` directory.

## License

This project is currently not under a specific license. All rights are reserved.
