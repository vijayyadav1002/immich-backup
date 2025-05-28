# Immich Backup Tool

A Python utility for backing up media files from an Immich server instance while preserving the original file structure and metadata.

## Features

- Connects to Immich's PostgreSQL database directly
- Preserves original file creation dates and metadata
- Organizes backups by user and date
- Supports both images and videos
- Maintains folder structure by year and month
- Skips existing files to avoid duplicates
- Handles large collections efficiently

## Prerequisites

- Python 3.12 or higher
- PostgreSQL database access to Immich instance
- Sufficient storage space for backups
- Access to Immich's upload directory
- Read permissions for the source files

## Installation

1. Clone the repository:
```shell
git clone https://github.com/vijayyadav1002/immich-backup.git
cd immich-backup
```

2. Create virtual environment:
```shell
python3.12 -m venv venv
```
Or use `python -m venv venv` if Python 3.12 is your default version.

3. Activate virtual environment:
```shell
source venv/bin/activate
```

4. Install dependencies:
```shell
pip install -r requirements.txt
```

## Configuration

Copy the `.env.example` file to `.env` and configure the following variables:

```ini
DBNAME=immich          # Database name
DBUSER=postgres        # Database username
DBPASS=yourpassword    # Database password
DBHOST=localhost       # Database host
DBPORT=5432           # Database port

# Backup paths
BASE_TARGET_PATH_IMAGES=/path/to/backup/folder/{}/images
BASE_TARGET_PATH_VIDEOS=/path/to/backup/folder/{}/videos
SOURCE_BASE_PATH=/path/to/immich/upload/folder
```

## Usage

Run the backup tool:
```shell
python main.py
```

The tool will:
1. Connect to your Immich database
2. Scan for all media assets
3. Create backup folders by user and date
4. Copy files while preserving metadata
5. Skip existing files automatically

## Backup Structure

```
backup-folder/
├── user1/
│   ├── images/
│   │   ├── 2024-01/
│   │   └── 2024-02/
│   └── videos/
│       ├── 2024-01/
│       └── 2024-02/
└── user2/
    ├── images/
    │   └── ...
    └── videos/
        └── ...
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- Open an issue for bug reports or feature requests
- Create a discussion for questions or support

## Acknowledgments

- [Immich](https://github.com/immich-app/immich) - The awesome self-hosted photo and video backup solution
- SQLAlchemy team for the excellent ORM
- All contributors and users of this tool

---
For more information about Immich, visit [Immich's official repository](https://github.com/immich-app/immich).