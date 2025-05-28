import os
import shutil
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
assets_table = Table('assets', metadata, autoload_with=engine, schema='public')
users_table = Table('users', metadata, autoload_with=engine, schema='public')
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

# Query to select required fields
def get_assets(session):
    query = session.query(
        assets_table.c.fileCreatedAt,
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
        original_path = asset.originalPath
        original_file_name = asset.originalFileName
        asset_type = asset.type.upper()  # Ensure type is uppercase for consistency
        modified_time = file_created_at.timestamp()
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
            print(f'Skipping {original_file_name} as it already exists in {target_folder}')
            # os.utime(target_path, (modified_time, modified_time))
            continue

        # Copy the file to the target folder
        try:
            source_file_path = os.path.join(SOURCE_BASE_PATH, original_path.lstrip('upload/'))
            shutil.copy(source_file_path, target_path)
            # Set the modification and access times to fileCreatedAt
            os.utime(target_path, (modified_time, modified_time))
            print(f'Copied {original_file_name} to {target_folder}')
        except FileNotFoundError:
            print(f'File not found: {original_path}')
        except Exception as e:
            print(f'Error copying file {original_file_name}: {e}')

# Run the copy files function
if __name__ == '__main__':
    copy_files()