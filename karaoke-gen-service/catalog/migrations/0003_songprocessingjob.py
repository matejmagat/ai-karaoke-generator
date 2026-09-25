import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SongProcessingJob",
            fields=[
                (
                    "job_id",
                    models.CharField(max_length=64, primary_key=True, serialize=False),
                ),
                ("title", models.CharField(max_length=255)),
                ("artist", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="song_processing_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "song",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="processing_job",
                        to="catalog.song",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="songprocessingjob",
            index=models.Index(
                fields=["owner", "status"],
                name="catalog_son_owner_i_073d6f_idx",
            ),
        ),
    ]
