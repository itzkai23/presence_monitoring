from django.core.management.base import BaseCommand
from django.conf import settings
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Delete all guest snapshots older than today'

    def handle(self, *args, **kwargs):
        snapshot_dir = os.path.join(settings.MEDIA_ROOT, 'guest_snapshots')
        today = datetime.now().date()

        deleted = 0
        if os.path.exists(snapshot_dir):
            for filename in os.listdir(snapshot_dir):
                filepath = os.path.join(snapshot_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        modified_date = datetime.fromtimestamp(os.path.getmtime(filepath)).date()
                        if modified_date < today:
                            os.remove(filepath)
                            deleted += 1
                except Exception as e:
                    self.stderr.write(f"Failed to delete {filename}: {e}")

        self.stdout.write(self.style.SUCCESS(f"✅ Deleted {deleted} old guest snapshots."))
