import os
from django.conf import settings
from django.http import JsonResponse
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# Google Drive folder for student photos
STUDENT_FOLDER_ID = "1K-q2A3c9gkFynEaXv3BWjDg-Z9sDQgZo"  # replace with actual ID

def authenticate_drive():
    """Handles Google Drive authentication with token.json."""
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_path = os.path.join(PROJECT_ROOT, "token.json")

    gauth = GoogleAuth()
    gauth.LoadCredentialsFile(token_path)
    if gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    return GoogleDrive(gauth)

def get_or_create_drive_folder(drive, parent_id, folder_name):
    """Find existing folder or create a new one under parent_id."""
    query = (
        f"'{parent_id}' in parents and trashed=false "
        f"and title='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
    )
    file_list = drive.ListFile({'q': query}).GetList()
    if file_list:
        return file_list[0]['id']

    folder = drive.CreateFile({
        'title': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [{'id': parent_id}]
    })
    folder.Upload()
    return folder['id']

def backup_student_images_to_drive(request=None):
    """
    Upload student images (_left, _right, _extraX, _addX) to Google Drive.
    Each student gets their own folder.
    Can be called from generate_encodings.py or a view.
    """
    try:
        drive = authenticate_drive()
        uploaded, deleted, errors = [], [], []

        student_path = os.path.join(settings.MEDIA_ROOT, "student_photos")

        if os.path.exists(student_path):
            for filename in os.listdir(student_path):
                file_path = os.path.join(student_path, filename)

                # Only upload relevant student images
                if os.path.isfile(file_path) and (
                    "_left" in filename
                    or "_right" in filename
                    or "_extra" in filename
                    or "_add" in filename
                ):
                    try:
                        parts = filename.split("_")
                        if len(parts) >= 2:
                            student_folder_name = f"{parts[0]}_{parts[1]}"
                        else:
                            student_folder_name = "unknown_student"

                        student_folder_id = get_or_create_drive_folder(
                            drive, STUDENT_FOLDER_ID, student_folder_name
                        )

                        gfile = drive.CreateFile({
                            'title': filename,
                            'parents': [{'id': student_folder_id}]
                        })
                        gfile.SetContentFile(file_path)
                        gfile.Upload()
                        uploaded.append(f"{student_folder_name}/{filename}")

                        # Close & cleanup
                        if hasattr(gfile, "content") and gfile.content:
                            gfile.content.close()
                        del gfile

                        # Remove local file after successful upload
                        os.remove(file_path)
                        deleted.append(filename)

                    except Exception as inner_e:
                        errors.append(f"{filename}: {str(inner_e)}")

        return JsonResponse({
            "status": "success",
            "uploaded": uploaded,
            "deleted": deleted,
            "errors": errors
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})
