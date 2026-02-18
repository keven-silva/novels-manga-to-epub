# Novels Manager

## Getting Started

### Prerequisites
- Python 3.12+
- pip or uv
- Git

### Installation Steps

1. **Clone the repository**
    ```bash
    git clone <repository-url>
    cd novels-manga-to-epub
    ```

2. **Create a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **Configure environment variables**
    ```bash
    cp .env.example .env
    ```

5. **Run the project**
    ```bash
    python main.py
    ```

6. **Verify installation**
    - Check if all modules load correctly
    - Test basic functionality
    ## Usage

    ### Configuration

    Before running the project, configure the following settings in your `.env` file:

    - **novel_title**: Change to set the work's name
    - **CHAPTER_LINKS_SELECTOR**: Update based on the target website's HTML structure

    Configure the cover:
        - `COVER_MODE`: Set to `"local"` (local file) or `"auto"` (automatic download)
        - `COVER_FILE_PATH`: Path to the cover image file (use `r""` on Windows to avoid path errors)
        
        Example:
        ```
        COVER_FILE_PATH = r"./novels_output/Jujutsu Kaisen/jujutsu-kaisen.jpeg"
        ```
    ### Manga

    To create an `.epub` file from a manga:

    1. Set `is_manga` to `True`
    2. Define `MANGA_INDEX_URL` with the manga site URL
    3. Set the manga slug in the configuration

    ### Novel

    To create an `.epub` file from a novel:

    1. Set `is_manga` to `False`
    2. Update `INDEX_URL` with the novel's URL
