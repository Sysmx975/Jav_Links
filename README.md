# PostGrid 🖋️

A personal dashboard that fetches posts from various websites, stores them as a JSON database, and displays them as a clean, personal GitHub Pages gallery.

[![GitHub last commit](https.img.shields.io/github/last-commit/[Your-GitHub-Username]/[Your-Repo-Name])](https://github.com/[Your-GitHub-Username]/[Your-Repo-Name]/commits/main)
[![Made with Python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![Hosted on GitHub Pages](https://img.shields.io/badge/Hosted%20on-GitHub%20Pages-blueviolet)](https://[Your-GitHub-Username].github.io/[Your-Repo-Name]/)

---

## ✨ Key Features

* **Multi-Source Aggregation**: Scripts to fetch content from sites like [Site 1], [Site 2], etc.
* **JSON Database**: All posts are standardized and stored in simple, easy-to-use JSON files.
* **Static Site Display**: A clean, responsive web interface to browse all aggregated posts.
* **GitHub Pages Deployment**: Automatically deployed and hosted for free on GitHub Pages.
* **Extensible**: Easily add new scrapers to include more websites.

## 🚀 Live Demo

You can view the live, running version of the gallery here:

**[https://[Your-GitHub-Username].github.io/[Your-Repo-Name]/](https://[Your-GitHub-Username].github.io/[Your-Repo-Name]/)**

## ⚙️ How It Works

This project works in two main stages:

1.  **Data Fetching**: Python scripts in the `/scripts` directory are run to scrape post information (like titles, images, and links) from various websites. The collected data is then saved into `.json` files within the `/data` directory.
2.  **Static Site Generation**: The `index.html` file in the `/docs` directory uses JavaScript to read the `.json` data files. It then dynamically generates a grid or list of all the posts, creating a browsable gallery. This means the website content is always as fresh as the last data fetch.

This process can be automated using GitHub Actions to run the scripts on a schedule, ensuring the gallery is always up-to-date.

## 🛠️ Setup and Installation

To run this project locally, you'll need Python 3. Follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/](https://github.com/)[Your-GitHub-Username]/[Your-Repo-Name].git
    cd [Your-Repo-Name]
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## 🏃‍♀️ Usage

To fetch the latest posts, run the main Python script:

```bash
# This will update the JSON files in the /data directory
bash start.sh