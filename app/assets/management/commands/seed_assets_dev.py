from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from app.assets.control_layer.asset_context import AssetContext
from app.assets.control_layer.asset_model_context import AssetModelContext
from app.assets.models import Asset, AssetModel

User = get_user_model()

ASSET_IMAGE_MAP = {
    "BL-300": "BL-300.png",
    "CAR-400": "CAR-400.png",
    "EX-200": "EX-200.png",
    "EX-201": "EX-201.png",
    "TRK-500": "TRK-500.png",
    "TRK-600": "TRK-600.png",
    "TRK-601": "TRK-601.png",
    "FL-100": "FL-100.png",
    "FL-101": "FL-101.png",
}

MODEL_IMAGE_MAP = {
    "Z-45": "BL-300.png",
    "Corolla": "CAR-400.png",
    "320 Excavator": "EX-200.png",
    "F-150": "TRK-500.png",
    "F-250": "TRK-600.png",
    "8FGCU25": "FL-100.png",
}


class Command(BaseCommand):
    help = "Seed dev asset and asset model primary pictures from seed_images."

    def handle(self, *args, **options):
        actor = (
            User.objects.filter(username="generic_admin").first()
            or User.objects.first()
        )
        if not actor:
            self.stdout.write(self.style.WARNING("No user found for seed_assets_dev."))
            return

        seed_images_dir = Path(settings.BASE_DIR) / "assets" / "fixtures" / "seed_images"
        if not seed_images_dir.is_dir():
            seed_images_dir = Path(settings.BASE_DIR) / "app" / "assets" / "fixtures" / "seed_images"

        if not seed_images_dir.is_dir():
            self.stdout.write(
                self.style.WARNING(
                    f"Seed images directory not found: {seed_images_dir}"
                )
            )
            return

        self.stdout.write("Seeding asset primary pictures...")
        for serial_number, filename in ASSET_IMAGE_MAP.items():
            asset = Asset.objects.filter(serial_number=serial_number).first()
            if not asset:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Asset with serial '{serial_number}' not found."
                    )
                )
                continue

            if asset.primary_image_id:
                self.stdout.write(
                    f"  Asset '{asset.name}' already has a primary image, skipping."
                )
                continue

            image_path = seed_images_dir / filename
            if not image_path.exists():
                self.stdout.write(
                    self.style.WARNING(f"  Image file not found: {image_path}")
                )
                continue

            with open(image_path, "rb") as f:
                uploaded = SimpleUploadedFile(
                    name=filename,
                    content=f.read(),
                    content_type="image/png",
                )

            ctx = AssetContext(asset.id, actor=actor)
            ctx.images.add_image(uploaded, caption=f"{asset.name} Primary Picture")
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Added primary picture for asset '{asset.name}' ({serial_number})."
                )
            )

        self.stdout.write("Seeding asset model primary pictures...")
        for model_name, filename in MODEL_IMAGE_MAP.items():
            models = AssetModel.objects.filter(model_name=model_name)
            if not models.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"  Model with name '{model_name}' not found."
                    )
                )
                continue

            image_path = seed_images_dir / filename
            if not image_path.exists():
                self.stdout.write(
                    self.style.WARNING(f"  Image file not found: {image_path}")
                )
                continue

            for model in models:
                if model.primary_image_id:
                    self.stdout.write(
                        f"  Model '{model}' already has a primary image, skipping."
                    )
                    continue

                with open(image_path, "rb") as f:
                    uploaded = SimpleUploadedFile(
                        name=filename,
                        content=f.read(),
                        content_type="image/png",
                    )

                ctx = AssetModelContext(model.id, actor=actor)
                ctx.images.add_image(uploaded, caption=f"{model} Hero Picture")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Added hero picture for model '{model}'."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS("Finished seeding asset & model primary pictures.")
        )
