"""
File watcher for automatic image processing.

Watches the post_images folder and automatically processes new images,
then moves them to a 'done' folder after processing.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

if TYPE_CHECKING:
    from application.use_cases import ProcessSingleImage

logger = logging.getLogger(__name__)


class ImageFileHandler(FileSystemEventHandler):
    """Handles file system events for new images."""

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

    def __init__(
        self,
        process_single: ProcessSingleImage,
        done_folder: Path,
        csv_storage=None,
        processing_delay: float = 1.0,
    ):
        """
        Args:
            process_single: Use case to process individual images
            done_folder: Directory to move processed images to
            csv_storage: CSV storage adapter for saving results
            processing_delay: Seconds to wait before processing (ensures file is fully written)
        """
        self.process_single = process_single
        self.done_folder = done_folder
        self.csv_storage = csv_storage
        self.processing_delay = processing_delay
        self.processing = set()
        
        # Create done folder if it doesn't exist
        self.done_folder.mkdir(parents=True, exist_ok=True)

    def on_created(self, event: FileCreatedEvent) -> None:
        """Called when a new file is created."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        
        # Check if it's an image file
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return

        # Check if already processing
        if file_path in self.processing:
            return

        # Process in a separate thread to avoid blocking the watcher
        import threading
        thread = threading.Thread(
            target=self._process_and_move_sync,
            args=(file_path,),
            daemon=True
        )
        thread.start()

    def _process_and_move_sync(self, file_path: Path) -> None:
        """Synchronous wrapper for processing and moving files."""
        if file_path in self.processing:
            return
        
        self.processing.add(file_path)
        start_time = time.time()
        
        try:
            # Wait to ensure file is fully written
            time.sleep(self.processing_delay)
            
            # Check if file still exists (might have been deleted)
            if not file_path.exists():
                logger.warning("File no longer exists: %s", file_path.name)
                return

            logger.info("📸 Processing: %s", file_path.name)
            logger.info("⏱️  Timer started...")
            
            # Parse filename to create metadata
            from application.filename_parser import parse_image_filename
            from domain.entities import ImageJob
            
            meta = parse_image_filename(file_path)
            if meta is None:
                logger.warning("Skipping '%s' — filename does not match convention", file_path.name)
                # Still move to done folder to avoid reprocessing
                done_path = self.done_folder / file_path.name
                shutil.move(str(file_path), str(done_path))
                logger.info("📁 Moved to done (skipped): %s", done_path.name)
                return
            
            # Create job
            job = ImageJob(image_path=file_path, metadata=meta)
            
            # Process the image
            result = self.process_single.execute(job)
            
            # Save to CSV if storage adapter is available
            if self.csv_storage and result:
                try:
                    self.csv_storage.save_vlm_complete([result], overwrite=False)
                    logger.info("💾 Saved to CSV: vlm_complete_analysis.csv")
                except Exception as csv_error:
                    logger.error("Failed to save CSV: %s", csv_error)
            
            elapsed = time.time() - start_time
            if result and not result.has_error:
                logger.info("✅ Processed successfully: %s", file_path.name)
                logger.info("⏱️  Total time: %.2f seconds", elapsed)
            else:
                error_msg = result.error_msg if result else "Unknown error"
                logger.error("❌ Processing failed: %s - %s", file_path.name, error_msg)
                logger.info("⏱️  Total time: %.2f seconds (failed)", elapsed)
            
            # Move to done folder regardless of success/failure
            if file_path.exists():
                done_path = self.done_folder / file_path.name
                
                # If file exists in done folder, add timestamp to avoid overwrite
                if done_path.exists():
                    timestamp = int(time.time())
                    stem = done_path.stem
                    suffix = done_path.suffix
                    done_path = self.done_folder / f"{stem}_{timestamp}{suffix}"
                
                shutil.move(str(file_path), str(done_path))
                logger.info("📁 Moved to done: %s", done_path.name)
        
        except Exception as e:
            logger.error("Error processing %s: %s", file_path.name, e, exc_info=True)
            
            # Try to move to done folder anyway to avoid reprocessing
            try:
                if file_path.exists():
                    done_path = self.done_folder / f"ERROR_{file_path.name}"
                    shutil.move(str(file_path), str(done_path))
                    logger.info("📁 Moved to done (with error): %s", done_path.name)
            except Exception as move_error:
                logger.error("Could not move file: %s", move_error)
        
        finally:
            self.processing.discard(file_path)


def process_existing_images(
    watch_folder: Path,
    done_folder: Path,
    process_single: ProcessSingleImage,
    csv_storage=None,
) -> int:
    """
    Process all existing images in the watch folder on startup.

    Args:
        watch_folder: Directory containing images to process
        done_folder: Directory to move processed images to
        process_single: Use case to process individual images
        csv_storage: CSV storage adapter for saving results

    Returns:
        Number of images processed
    """
    from application.filename_parser import parse_image_filename
    from domain.entities import ImageJob
    
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    # Find all existing images
    existing_images = [
        f for f in watch_folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    
    if not existing_images:
        logger.info("No existing images found in %s", watch_folder)
        return 0
    
    logger.info("🔍 Found %d existing image(s) to process", len(existing_images))
    
    processed_count = 0
    for idx, file_path in enumerate(existing_images, 1):
        start_time = time.time()
        try:
            logger.info("📸 [%d/%d] Processing: %s", idx, len(existing_images), file_path.name)
            logger.info("⏱️  Timer started...")
            
            # Parse filename to create metadata
            meta = parse_image_filename(file_path)
            if meta is None:
                logger.warning("Skipping '%s' — filename does not match convention", file_path.name)
                # Still move to done folder to avoid reprocessing
                done_path = done_folder / file_path.name
                if done_path.exists():
                    timestamp = int(time.time())
                    done_path = done_folder / f"{file_path.stem}_{timestamp}{file_path.suffix}"
                shutil.move(str(file_path), str(done_path))
                logger.info("📁 Moved to done (skipped): %s", done_path.name)
                continue
            
            # Create job and process
            job = ImageJob(image_path=file_path, metadata=meta)
            result = process_single.execute(job)
            
            # Save to CSV if storage adapter is available
            if csv_storage and result:
                try:
                    csv_storage.save_vlm_complete([result], overwrite=False)
                    logger.info("💾 Saved to CSV: vlm_complete_analysis.csv")
                except Exception as csv_error:
                    logger.error("Failed to save CSV: %s", csv_error)
            
            elapsed = time.time() - start_time
            if result and not result.has_error:
                logger.info("✅ Processed successfully: %s", file_path.name)
                logger.info("⏱️  Total time: %.2f seconds", elapsed)
                processed_count += 1
            else:
                error_msg = result.error_msg if result else "Unknown error"
                logger.error("❌ Processing failed: %s - %s", file_path.name, error_msg)
                logger.info("⏱️  Total time: %.2f seconds (failed)", elapsed)
            
            # Move to done folder
            if file_path.exists():
                done_path = done_folder / file_path.name
                if done_path.exists():
                    timestamp = int(time.time())
                    done_path = done_folder / f"{file_path.stem}_{timestamp}{file_path.suffix}"
                shutil.move(str(file_path), str(done_path))
                logger.info("📁 Moved to done: %s", done_path.name)
        
        except Exception as e:
            logger.error("Error processing %s: %s", file_path.name, e, exc_info=True)
            # Try to move to done folder anyway
            try:
                if file_path.exists():
                    done_path = done_folder / f"ERROR_{file_path.name}"
                    shutil.move(str(file_path), str(done_path))
                    logger.info("📁 Moved to done (with error): %s", done_path.name)
            except Exception as move_error:
                logger.error("Could not move file: %s", move_error)
    
    logger.info("✨ Finished processing %d existing image(s)", processed_count)
    return processed_count


def start_file_watcher(
    watch_folder: Path,
    done_folder: Path,
    process_single: ProcessSingleImage,
    csv_storage=None,
    processing_delay: float = 1.0,
    process_existing: bool = True,
):
    """
    Start watching for new images in the specified folder.

    Args:
        watch_folder: Directory to watch for new images
        done_folder: Directory to move processed images to
        process_single: Use case to process individual images
        processing_delay: Seconds to wait before processing new files
        process_existing: Whether to process existing images on startup

    Returns:
        Observer instance that can be stopped later
    """
    # Ensure folders exist
    watch_folder.mkdir(parents=True, exist_ok=True)
    done_folder.mkdir(parents=True, exist_ok=True)

    # Process any existing images in a background thread (non-blocking)
    if process_existing:
        logger.info("🔄 Starting background processing of existing images in %s...", watch_folder)
        import threading
        thread = threading.Thread(
            target=process_existing_images,
            args=(watch_folder, done_folder, process_single, csv_storage),
            daemon=True,
            name="ExistingImageProcessor"
        )
        thread.start()
        logger.info("✅ Background processing thread started")
    
    # Start watching for new images
    event_handler = ImageFileHandler(
        process_single=process_single,
        done_folder=done_folder,
        csv_storage=csv_storage,
        processing_delay=processing_delay,
    )
    
    observer = Observer()
    observer.schedule(event_handler, str(watch_folder), recursive=False)
    observer.start()
    
    logger.info("👀 File watcher started")
    logger.info("   Watching: %s", watch_folder)
    logger.info("   Done folder: %s", done_folder)
    logger.info("   Processing delay: %.1fs", processing_delay)
    
    return observer
