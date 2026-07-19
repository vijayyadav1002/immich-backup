import os
import platform
import shutil
import struct
import subprocess
from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DBUSER = os.getenv('DBUSER')
DBPASS = os.getenv('DBPASS')
DBHOST = os.getenv('DBHOST')
DBPORT = os.getenv('DBPORT')
DBNAME = os.getenv('DBNAME')
BASE_TARGET_PATH_IMAGES = os.getenv('BASE_TARGET_PATH_IMAGES')
BASE_TARGET_PATH_VIDEOS = os.getenv('BASE_TARGET_PATH_VIDEOS')
SOURCE_BASE_PATH = os.getenv('SOURCE_BASE_PATH')
STRIP_STRING = os.getenv('STRIP_STRING')


# Ensure environment variables are set
if not all([DBUSER, DBPASS, DBHOST, DBPORT, DBNAME, BASE_TARGET_PATH_IMAGES, BASE_TARGET_PATH_VIDEOS, SOURCE_BASE_PATH]):
    raise EnvironmentError("Database environment variables are not set properly.")


# Database configuration
DATABASE_URI = f"postgresql+psycopg2://{DBUSER}:{DBPASS}@{DBHOST}:{DBPORT}/{DBNAME}"


# Connect to PostgreSQL database
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

# Reflect the existing table in the database
metadata = MetaData()
assets_table = Table('asset', metadata, autoload_with=engine, schema='public')
users_table = Table('user', metadata, autoload_with=engine, schema='public')
users = dict()

def get_user(id: str) -> object:
    user =  users.get(id)
    if user:
        return user

    res = session.query(users_table).where(users_table.c.id == id).all()
    users.update({id: res[0]})
    return res[0]

def get_user_folder_name(name: str) -> str:
    return name.lower().replace(' ', '-')

# exFAT/FAT store modification times with up to 2-second resolution
TIMESTAMP_TOLERANCE_SECONDS = 2

IS_MACOS = platform.system() == 'Darwin'
IS_LINUX = platform.system() == 'Linux'

# macOS: SetFile (Xcode Command Line Tools) sets the creation date
SETFILE = shutil.which('SetFile') if IS_MACOS else None
if IS_MACOS and not SETFILE:
    print('Warning: SetFile not found. Run "xcode-select --install" to enable setting '
          'creation dates; without it only modification times will be fixed.')

# Linux: there is no standard API to change a file's creation (birth) time.
# The one exception is NTFS mounted via ntfs-3g, which exposes it as an
# extended attribute holding a Windows FILETIME (100ns ticks since 1601-01-01).
_FILETIME_EPOCH_OFFSET = 11644473600  # seconds between 1601-01-01 and 1970-01-01
_linux_crtime_supported = IS_LINUX  # optimistic until the filesystem says otherwise

def can_set_creation_date() -> bool:
    if IS_MACOS:
        return SETFILE is not None
    return _linux_crtime_supported

def set_creation_date(path: str, created_at) -> None:
    """Best-effort set of the file's creation (birth) date.

    os.utime can only change access/modification times. The creation date
    needs SetFile on macOS, or the ntfs-3g extended attribute on Linux
    (NTFS drives only -- ext4/exFAT offer no way to change it after creation).
    """
    global _linux_crtime_supported
    if IS_MACOS and SETFILE:
        local_dt = created_at.astimezone()  # SetFile expects local time
        subprocess.run(
            [SETFILE, '-d', local_dt.strftime('%m/%d/%Y %H:%M:%S'), path],
            check=False, capture_output=True,
        )
    elif IS_LINUX and _linux_crtime_supported:
        try:
            filetime = int((created_at.timestamp() + _FILETIME_EPOCH_OFFSET) * 10_000_000)
            os.setxattr(path, 'system.ntfs_crtime_be', struct.pack('>Q', filetime))
        except OSError:
            _linux_crtime_supported = False
            print('Note: this filesystem does not support setting creation dates on Linux; '
                  'modification times will still be set correctly.')

def apply_timestamps(path: str, created_at, modified_time: float) -> None:
    """Stamp the real metadata from the database onto the file."""
    # Set modification/access times to the original file's modified time
    os.utime(path, (modified_time, modified_time))
    # Set the creation date to the original capture/creation time
    set_creation_date(path, created_at)

def timestamps_match(path: str, created_time: float, modified_time: float) -> bool:
    """Check whether an existing file already carries the expected timestamps."""
    st = os.stat(path)
    if abs(st.st_mtime - modified_time) > TIMESTAMP_TOLERANCE_SECONDS:
        return False
    birth_time = getattr(st, 'st_birthtime', None)  # only exposed on macOS/BSD
    if birth_time is not None and can_set_creation_date() and abs(birth_time - created_time) > TIMESTAMP_TOLERANCE_SECONDS:
        return False
    return True

# Query to select required fields
def get_assets(session):
    query = session.query(
        assets_table.c.fileCreatedAt,
        assets_table.c.fileModifiedAt,
        assets_table.c.originalPath,
        assets_table.c.originalFileName,
        assets_table.c.type,
        assets_table.c.ownerId
    ).order_by(assets_table.c.fileCreatedAt)
    return query.all()

# Function to copy files based on 'fileCreatedAt' date and type
def copy_files():
    assets = get_assets(session)

    for asset in assets:
        file_created_at = asset.fileCreatedAt
        file_modified_at = asset.fileModifiedAt or file_created_at
        original_path = asset.originalPath
        original_file_name = asset.originalFileName
        asset_type = asset.type.upper()  # Ensure type is uppercase for consistency
        created_time = file_created_at.timestamp()
        modified_time = file_modified_at.timestamp()
        owner_id = asset.ownerId
        user = get_user(owner_id)
        owner_folder_name = get_user_folder_name(user.name)

        # Determine the base target path based on type
        if asset_type == 'IMAGE':
            base_target_path = BASE_TARGET_PATH_IMAGES.format(owner_folder_name)
        elif asset_type == 'VIDEO':
            base_target_path = BASE_TARGET_PATH_VIDEOS.format(owner_folder_name)
        else:
            print(f'Unknown asset type "{asset_type}" for file {original_file_name}. Skipping.')
            continue

        # Format the date to create folder as "YYYY-MM"
        folder_name = file_created_at.strftime('%Y-%m')
        target_folder = os.path.join(base_target_path, folder_name)

        # Ensure the target folder exists
        os.makedirs(target_folder, exist_ok=True)

        # Define the target file path
        target_path = os.path.join(target_folder, original_file_name)

        # Check if the file already exists in the target folder
        if os.path.exists(target_path):
            # Repair metadata on files copied by earlier runs
            if not timestamps_match(target_path, created_time, modified_time):
                apply_timestamps(target_path, file_created_at, modified_time)
                print(f'Repaired timestamps for {original_file_name} in {target_folder}')
            else:
                print(f'Skipping {original_file_name} as it already exists in {target_folder}')
            continue

        # Copy the file to the target folder
        try:
            source_file_path = os.path.join(SOURCE_BASE_PATH, original_path.lstrip(STRIP_STRING))
            shutil.copy(source_file_path, target_path)
            # Stamp the file with its real metadata from the database
            apply_timestamps(target_path, file_created_at, modified_time)
            print(f'Copied {original_file_name} to {target_folder}')
        except FileNotFoundError:
            print(f'File not found: {original_path}')
        except Exception as e:
            print(f'Error copying file {original_file_name}: {e}')

# Run the copy files function
if __name__ == '__main__':
    copy_files()
